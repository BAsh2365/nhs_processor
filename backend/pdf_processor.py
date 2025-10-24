# backend/pdf_processor.py - UPDATED

import os
from pypdf import PdfReader  # CHANGED FROM PyPDF2
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import io

class PDFProcessor:
    """Process PDF files for text extraction with OCR fallback"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_path: str) -> str:
        """
        Extract text from PDF using multiple methods
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text as string
        """
        text = ""
        
        try:
            # Method 1: Try pypdf first (fast, works for text PDFs)
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            
            # If we got substantial text, return it
            if len(text.strip()) > 100:
                return text
                
        except Exception as e:
            print(f"pypdf extraction failed: {e}")
        
        try:
            # Method 2: Try PyMuPDF (handles more PDF types)
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            
            # If we got substantial text, return it
            if len(text.strip()) > 100:
                return text
                
        except Exception as e:
            print(f"PyMuPDF extraction failed: {e}")
        
        try:
            # Method 3: OCR as fallback (for scanned PDFs)
            print("Attempting OCR extraction...")
            text = PDFProcessor.extract_with_ocr(pdf_path)
            
        except Exception as e:
            print(f"OCR extraction failed: {e}")
            raise Exception("All PDF text extraction methods failed")
        
        return text
    
    @staticmethod
    def extract_with_ocr(pdf_path: str) -> str:
        """
        Extract text using OCR (for scanned PDFs)
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text as string
        """
        # Convert PDF to images
        images = convert_from_path(pdf_path)
        
        text = ""
        for i, image in enumerate(images):
            # Use pytesseract to extract text from image
            page_text = pytesseract.image_to_string(image)
            text += f"\n--- Page {i+1} ---\n{page_text}"
        
        return text
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 2200, overlap: int = 200) -> list:
        """
        Split text into overlapping chunks
        
        Args:
            text: Input text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to end at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                boundary = max(last_period, last_newline)
                
                if boundary > chunk_size * 0.8:  # At least 80% through
                    end = start + boundary + 1
                    chunk = text[start:end]
            
            chunks.append(chunk)
            start = end - overlap
        
        return chunks