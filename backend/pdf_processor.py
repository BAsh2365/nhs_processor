# backend/pdf_processor.py
from typing import List, IO
import os

try:
    import fitz  # PyMuPDF (fast)
except Exception:
    fitz = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

# Optional OCR
try:
    from pdf2image import convert_from_bytes
    import pytesseract
except Exception:
    convert_from_bytes = None
    pytesseract = None

def _ensure_tesseract():
    # Set TESSERACT_PATH in Windows if needed, e.g. C:\Program Files\Tesseract-OCR\tesseract.exe
    p = os.environ.get("TESSERACT_PATH")
    if p and pytesseract:
        pytesseract.pytesseract.tesseract_cmd = p

class PDFProcessor:
    @staticmethod
    def _extract_from_bytes(data: bytes, use_ocr: bool = True) -> str:
        # 1) Fast path: PyMuPDF
        if fitz is not None:
            with fitz.open(stream=data, filetype="pdf") as doc:
                text = "\n".join((pg.get_text("text") or "") for pg in doc)
            if text.strip():
                return text
        # 2) PyPDF2 fallback
        if PyPDF2 is not None:
            try:
                import io
                reader = PyPDF2.PdfReader(io.BytesIO(data))
                text = "\n".join((p.extract_text() or "") for p in reader.pages)
                if text.strip():
                    return text
            except Exception:
                pass
        # 3) OCR fallback
        if use_ocr and convert_from_bytes and pytesseract:
            _ensure_tesseract()
            try:
                images = convert_from_bytes(data, dpi=300)
                ocr_text = "\n".join(pytesseract.image_to_string(im, lang="eng") for im in images)
                return ocr_text or ""
            except Exception:
                return ""
        return ""

    @staticmethod
    def extract_text_from_uploaded_file(file_obj: IO[bytes], use_ocr: bool = True) -> str:
        data = file_obj.read()
        return PDFProcessor._extract_from_bytes(data, use_ocr=use_ocr)

    @staticmethod
    def extract_text_from_pdf(path: str, use_ocr: bool = True) -> str:
        with open(path, "rb") as fh:
            return PDFProcessor._extract_from_bytes(fh.read(), use_ocr=use_ocr)

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 2200, overlap: int = 200) -> List[str]:
        if not text:
            return []
        t = " ".join(text.split())
        out: List[str] = []
        i, n = 0, len(t)
        while i < n:
            j = min(i + chunk_size, n)
            window = t[i:j]
            cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            if cut != -1 and cut > int(0.7 * len(window)):
                j = i + cut + 1
            out.append(t[i:j].strip())
            if j == n:
                break
            i = max(j - overlap, 0)
        return [c for c in out if c]
