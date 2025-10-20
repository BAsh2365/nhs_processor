# kb_chroma.py
import os, warnings
from typing import List, Dict, Optional

# Ensure transformers never tries TensorFlow on your box
# Force Transformers to ignore TensorFlow/Flax completely
import os as _os
_os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
_os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")


_client = _col = _embed_model = None
_chroma_available = False

def _ensure():
    global _client, _col, _embed_model, _chroma_available
    if _chroma_available:
        return _client, _col, _embed_model
    try:
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer
        store_path = os.path.join(os.path.dirname(__file__), "kb_chroma_store")
        _client = chromadb.PersistentClient(path=store_path, settings=Settings(anonymized_telemetry=False))
        _col = _client.get_or_create_collection("nhs_kb", metadata={"hnsw:space": "cosine"})
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
        _chroma_available = True
    except Exception as e:
        warnings.warn(f"kb_chroma: running in NO-INDEX mode ({e}).")
        _client = _col = _embed_model = None
        _chroma_available = False
    return _client, _col, _embed_model

def query(q: str, k: int = 3):
    """
    Retrieve top-k snippets for a free-text query.
    Returns a list of {text, meta, distance}. Returns [] if the store isn't available.
    """
    if not q:
        return []
    client, col, emb = _ensure()
    if not col or not emb:
        return []  # safe no-op when vector store or model isn't available

    # Compute embedding for the query
    try:
        q_vec = emb.encode([q])[0]
        res = col.query(
            query_embeddings=[q_vec.tolist() if hasattr(q_vec, "tolist") else list(q_vec)],
            n_results=int(k),
            include=["documents", "metadatas", "distances"],
        )
        out = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i in range(len(docs)):
            out.append({
                "text": docs[i],
                "meta": metas[i] if i < len(metas) else {},
                "distance": dists[i] if i < len(dists) else None
            })
        return out
    except Exception:
        return []


def ingest_folder_chunked(folder: str, *, batch_size: int = 256, sbert_batch: int = 64,
                          chunk_size: int = 2200, overlap: int = 200,
                          max_mb: Optional[int] = None) -> None:
    """
    Ingest all PDFs/.txt/.md in a folder.
    - batch_size: how many chunks to send to Chroma per add()
    - sbert_batch: batch size for SentenceTransformer.encode (controls RAM/speed)
    - chunk_size/overlap: chunking parameters
    - max_mb: skip files larger than this (None = no limit)
    """
    client, col, emb = _ensure()
    if not col or not emb:
        warnings.warn("kb_chroma: vector store unavailable; skipping ingest.")
        return

    from .pdf_processor import PDFProcessor

    def _already_indexed(doc_id_prefix: str) -> bool:
        # quick heuristic: check if any id starting with prefix exists (cheap metadata scan)
        try:
            res = col.get(where={"source": {"$contains": doc_id_prefix}}, limit=1)
            return bool(res and res.get("ids"))
        except Exception:
            return False

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
                # Extract
                if lower.endswith(".pdf"):
                    text = PDFProcessor.extract_text_from_pdf(path)
                else:
                    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                        text = fh.read()

                from .pdf_processor import PDFProcessor as PP
                chunks = PP.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
                if not chunks:
                    continue

                ids_batch, metas_batch, docs_batch = [], [], []
                prefix = os.path.basename(path)
                # Optional: skip if we already have entries for this source
                # (comment out if you prefer re-indexing every time)
                # if _already_indexed(prefix):
                #     print(f"Already indexed: {fname} (skipping)")
                #     continue

                # Stream encode in sbert-sized batches so we don’t blow RAM
                def flush_batch(embeddings=None):
                    nonlocal ids_batch, metas_batch, docs_batch
                    if not ids_batch:
                        return
                    if embeddings is None:
                        embeddings = emb.encode(docs_batch, batch_size=sbert_batch, show_progress_bar=False)
                    col.add(
                        ids=ids_batch,
                        metadatas=metas_batch,
                        documents=docs_batch,
                        embeddings=[v.tolist() for v in embeddings],
                    )
                    ids_batch, metas_batch, docs_batch = [], [], []

                # Build ids/meta and flush to Chroma in batches
                pending_for_encode: List[str] = []
                pending_ids, pending_meta = [], []
                def flush_encode_batch():
                    nonlocal pending_for_encode, pending_ids, pending_meta
                    if not pending_for_encode:
                        return
                    embs = emb.encode(pending_for_encode, batch_size=sbert_batch, show_progress_bar=False)
                    # send to Chroma also in chunks of `batch_size` in case sbert_batch is large
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

                    # Control the encode batch (for RAM)
                    if len(pending_for_encode) >= max(sbert_batch, batch_size):
                        flush_encode_batch()

                # flush tail
                flush_encode_batch()
                try:
                    client.persist()
                except Exception:
                    pass
                print(f"Indexed (chunked): {fname} -> {len(chunks)} chunks")
            except Exception as e:
                warnings.warn(f"kb_chroma: failed ingest for {fname}: {e}")
