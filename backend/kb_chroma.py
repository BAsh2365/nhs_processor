# kb_chroma.py
import os
import warnings
from typing import List, Dict, Optional

# Ensure transformers never tries TensorFlow on your box
import os as _os
_os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
_os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")


_client = None
_collections: Dict[str, object] = {}
_embed_model = None
_embed_model_id = "all-MiniLM-L6-v2"
_chroma_available = False


def _ensure(collection_name: str = "nhs_kb", embed_model_id: Optional[str] = None):
    global _client, _collections, _embed_model, _embed_model_id, _chroma_available

    # Update embedding model if a different one is requested
    if embed_model_id and embed_model_id != _embed_model_id:
        _embed_model = None
        _embed_model_id = embed_model_id

    if _client is None:
        try:
            import chromadb
            from chromadb.config import Settings
            store_path = os.path.join(os.path.dirname(__file__), "kb_chroma_store")
            _client = chromadb.PersistentClient(path=store_path, settings=Settings(anonymized_telemetry=False))
            _chroma_available = True
        except Exception as e:
            warnings.warn(f"kb_chroma: running in NO-INDEX mode ({e}).")
            _client = None
            _chroma_available = False
            return None, None, None

    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _embed_model = SentenceTransformer(_embed_model_id, device=device)
        except Exception as e:
            warnings.warn(f"kb_chroma: embedding model failed ({e}).")
            return _client, None, None

    if collection_name not in _collections:
        try:
            _collections[collection_name] = _client.get_or_create_collection(
                collection_name, metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            warnings.warn(f"kb_chroma: collection '{collection_name}' failed ({e}).")
            return _client, None, _embed_model

    return _client, _collections.get(collection_name), _embed_model


def query(q: str, k: int = 3, collections: Optional[List[str]] = None,
          embed_model_id: Optional[str] = None):
    """
    Retrieve top-k snippets for a free-text query.
    Queries across specified collections and merges results by distance.
    Returns a list of {text, meta, distance}. Returns [] if the store isn't available.
    """
    if not q:
        return []

    collection_names = collections or ["nhs_kb"]
    all_results = []

    for col_name in collection_names:
        client, col, emb = _ensure(col_name, embed_model_id)
        if not col or not emb:
            continue

        try:
            q_vec = emb.encode([q])[0]
            res = col.query(
                query_embeddings=[q_vec.tolist() if hasattr(q_vec, "tolist") else list(q_vec)],
                n_results=int(k),
                include=["documents", "metadatas", "distances"],
            )
            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            dists = res.get("distances", [[]])[0]
            for i in range(len(docs)):
                all_results.append({
                    "text": docs[i],
                    "meta": metas[i] if i < len(metas) else {},
                    "distance": dists[i] if i < len(dists) else float('inf')
                })
        except Exception:
            continue

    # Sort by distance and return top k
    all_results.sort(key=lambda x: x.get("distance", float('inf')))
    return all_results[:k]


def ingest_folder_chunked(folder: str, *, collection_name: str = "nhs_kb",
                          batch_size: int = 256, sbert_batch: int = 64,
                          chunk_size: int = 2200, overlap: int = 200,
                          max_mb: Optional[int] = None,
                          embed_model_id: Optional[str] = None) -> None:
    """
    Ingest all PDFs/.txt/.md in a folder into a specified collection.
    """
    client, col, emb = _ensure(collection_name, embed_model_id)
    if not col or not emb:
        warnings.warn("kb_chroma: vector store unavailable; skipping ingest.")
        return

    from .pdf_processor import PDFProcessor

    for root, _, files in os.walk(folder):
        for fname in files:
            path = os.path.join(root, fname)
            lower = fname.lower()
            if not (lower.endswith(".pdf") or lower.endswith(".txt") or lower.endswith(".md")):
                continue
            if max_mb and os.path.getsize(path) > max_mb * 1024 * 1024:
                print(f"Skipping large file (>{max_mb} MB): {fname}")
                continue

            try:
                if lower.endswith(".pdf"):
                    text = PDFProcessor.extract_text_from_pdf(path)
                else:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        text = fh.read()

                from .pdf_processor import PDFProcessor as PP
                chunks = PP.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
                if not chunks:
                    continue

                prefix = os.path.basename(path)

                pending_for_encode: List[str] = []
                pending_ids, pending_meta = [], []

                def flush_encode_batch():
                    nonlocal pending_for_encode, pending_ids, pending_meta
                    if not pending_for_encode:
                        return
                    embs = emb.encode(pending_for_encode, batch_size=sbert_batch, show_progress_bar=False)
                    start = 0
                    while start < len(embs):
                        end = min(start + batch_size, len(embs))
                        col.add(
                            ids=pending_ids[start:end],
                            metadatas=pending_meta[start:end],
                            documents=pending_for_encode[start:end],
                            embeddings=[v.tolist() for v in embs[start:end]],
                        )
                        start = end
                    pending_for_encode, pending_ids, pending_meta = [], [], []

                for idx, ch in enumerate(chunks):
                    cid = f"{prefix}_{idx}"
                    meta = {"title": fname, "source": path, "chunk": idx}
                    pending_for_encode.append(ch)
                    pending_ids.append(cid)
                    pending_meta.append(meta)

                    if len(pending_for_encode) >= max(sbert_batch, batch_size):
                        flush_encode_batch()

                flush_encode_batch()
                print(f"Indexed (chunked) [{collection_name}]: {fname} -> {len(chunks)} chunks")
            except Exception as e:
                warnings.warn(f"kb_chroma: failed ingest for {fname}: {e}")
