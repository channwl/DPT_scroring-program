# utils/pdf_utils.py
import io
import fitz                       # PyMuPDF
import pdfplumber
from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract
from typing import Union, List

def _ocr_img(img: Image.Image) -> str:
    """PIL 이미지 한 장을 한–영 OCR."""
    return pytesseract.image_to_string(img, lang="kor+eng")

def extract_text_from_pdf(pdf_data: Union[str, bytes, "UploadedFile"]) -> str:
    """
    1) PyMuPDF / pdfplumber 로 텍스트 추출  
    2) 각 페이지 글자 수 < 20 → OCR 로 보강
    """
    # ----- 입력 → 바이트 -----
    if isinstance(pdf_data, str):          # 파일 경로
        with open(pdf_data, "rb") as f:
            pdf_bytes = f.read()
    elif isinstance(pdf_data, bytes):
        pdf_bytes = pdf_data
    else:                                  # UploadedFile
        pdf_bytes = pdf_data.read()

    full_text: List[str] = []

    # ----- 1차: pdfplumber -----
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            if len(page_text.strip()) < 20:          # 글자 거의 없음 → OCR
                img = convert_from_bytes(
                    pdf_bytes, first_page=idx + 1, last_page=idx + 1,
                    fmt="png", thread_count=1
                )[0]
                ocr_text = _ocr_img(img)
                full_text.append(ocr_text)
            else:
                full_text.append(page_text)

    return "\n".join(full_text).strip()
