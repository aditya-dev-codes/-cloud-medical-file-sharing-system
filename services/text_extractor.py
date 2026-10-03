from pathlib import Path
import pypdf

class TextExtractor:
    """Extracts plain text content from uploaded medical documents (PDF and TXT)."""

    @classmethod
    def extract_text(cls, file_path, file_type):
        """
        Extracts clean text from a document on disk.
        Returns the extracted string or raises ValueError on empty/corrupted file.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found on storage: {file_path}")

        file_type = file_type.upper()

        if file_type == 'TXT':
            return cls._extract_from_txt(path)
        elif file_type == 'PDF':
            return cls._extract_from_pdf(path)
        else:
            raise ValueError(f"Unsupported document type for text extraction: {file_type}")

    @staticmethod
    def _extract_from_txt(path):
        """Read plain text files with UTF-8 and fallback encoding."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()

        cleaned = content.strip()
        if not cleaned:
            raise ValueError("The text document is empty.")
        return cleaned

    @staticmethod
    def _extract_from_pdf(path):
        """Extract text from all pages of a PDF document using pypdf."""
        extracted_pages = []
        try:
            reader = pypdf.PdfReader(str(path))
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    extracted_pages.append(text.strip())
        except Exception as e:
            raise ValueError(f"Failed to read PDF document: {str(e)}")

        full_text = "\n\n".join(extracted_pages).strip()
        if not full_text:
            raise ValueError("No extractable text found in the PDF document (file may contain scanned images without OCR).")
        return full_text
