# utils/pdf_utils.py
import io, re
import pdfplumber                 # 텍스트 + 그림 구조 파악
from pdf2image import convert_from_bytes
from PIL import Image
import pytesseract
from typing import Union, List, Sequence

# ===== 사용자 조정 파라미터 =====
MIN_CHARS = 40          # 페이지당 텍스트가 이보다 적으면 OCR
OCR_LANG  = "kor+eng"   # Tesseract 언어

# --------------------------------
def _ocr_page(img: Image.Image) -> str:
    """단일 PIL 이미지 → OCR 결과 문자열"""
    return pytesseract.image_to_string(img, lang=OCR_LANG)

def _merge_dedupe(base: str, extra: str) -> str:
    """
    base 텍스트와 extra 텍스트를 줄 단위로 병합하며 중복 제거.
    줄 벡터 수가 많으면 LCS나 fuzzy 매칭으로 교체 가능.
    """
    b_set = {ln.strip() for ln in base.splitlines() if ln.strip()}
    merged: List[str] = []
    for ln in base.splitlines():
        s = ln.strip()
        if s:
            merged.append(s)              # base 줄 우선 보존
    for ln in extra.splitlines():
        s = ln.strip()
        if s and s not in b_set:
            merged.append(s)              # OCR 보강 줄 추가
    return "\n".join(merged)

def _get_pdf_bytes(pdf_data: Union[str, bytes, "UploadedFile"]) -> bytes:
    if isinstance(pdf_data, str):
        with open(pdf_data, "rb") as f:
            return f.read()
    elif isinstance(pdf_data, bytes):
        return pdf_data
    elif hasattr(pdf_data, "read"):
        return pdf_data.read()
    else:
        raise ValueError("지원하지 않는 입력 타입입니다.")

def extract_text_from_pdf(pdf_data: Union[str, bytes, "UploadedFile"]) -> str:
    """
    ① pdfplumber 로 텍스트 추출  
    ② 각 페이지별로 (텍스트 < MIN_CHARS) **또는** (이미지 존재) → OCR 수행  
    ③ base + OCR 결과 병합 후 중복 제거
    """
    pdf_bytes = _get_pdf_bytes(pdf_data)
    pages_text: List[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)
        for idx, page in enumerate(pdf.pages):
            base_text = page.extract_text() or ""
            # pdfplumber 0.11+ 는 page.objects["image"]; 그 이하 버전은 page.images
            img_objs: Sequence = page.objects.get("image", getattr(page, "images", []))
            # OCR 필요 조건
            needs_ocr = len(base_text.strip()) < MIN_CHARS or len(img_objs) > 0

            if needs_ocr:
                pil_img = convert_from_bytes(
                    pdf_bytes,
                    first_page=idx + 1,
                    last_page=idx + 1,
                    fmt="png",
                    thread_count=1,
                    dpi=200                      # 해상도 조절 가능
                )[0]
                ocr_text = _ocr_page(pil_img)
                page_text = _merge_dedupe(base_text, ocr_text)
            else:
                page_text = base_text

            pages_text.append(page_text)

    return "\n".join(pages_text).strip()
