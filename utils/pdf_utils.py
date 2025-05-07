# utils/pdf_utils.py

from pdf2image import convert_from_path
import pytesseract
import pdfplumber
from PIL import Image

def extract_text_from_pdf(pdf_path: str, lang: str = 'eng+kor') -> str:
    """
    텍스트 기반 PDF는 pdfplumber로, 이미지 기반은 OCR로 처리
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        if text.strip():
            return text
    except Exception as e:
        print(f"[PDFPlumber 오류] {e}")

    return extract_text_via_ocr(pdf_path, lang=lang)

def extract_text_via_ocr(pdf_path: str, lang: str = 'eng+kor') -> str:
    """
    이미지 기반 PDF를 OCR로 텍스트 추출
    """
    try:
        pages = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        return f"[OCR 실패] PDF 이미지를 로딩할 수 없습니다: {str(e)}"

    full_text = ""
    for i, page in enumerate(pages):
        gray = page.convert("L")
        bw = gray.point(lambda x: 0 if x < 140 else 255)
        text = pytesseract.image_to_string(bw, lang=lang)
        full_text += f"\n\n--- Page {i + 1} ---\n{text.strip()}"

    return full_text.strip()
