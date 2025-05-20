"""
PDF에서 최대한 텍스트를 추출하기 위한 모듈.
- 먼저 pdfplumber로 레이어 텍스트 추출
- Carbon 캡처처럼 어두운 배경 이미지는 Gemini Vision OCR로 코드 추출
"""

import io, re, os
from typing import Union, List, Sequence

import pdfplumber
from pdf2image import convert_from_bytes
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageStat
import pytesseract

from utils.google_vision_code_ocr import gemini_code_ocr  # ✅ Gemini OCR 함수 추가

# ===== 사용자 조정 파라미터 =====
MIN_CHARS   = 40
OCR_LANG    = "kor+eng"
DPI         = 300
OCR_CONFIG = (
    '--oem 3 --psm 6 -c preserve_interword_spaces=1 '
    '-c tessedit_char_whitelist='
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    '_-+=*/(){}[]<>.:;.,|%$&#@!?`~^'
)
CARBON_WIDTH_THRESHOLD = 200
CARBON_HEIGHT_THRESHOLD = 150

# ------------------------------------------------------------------
def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    g = img.convert("L")
    if ImageStat.Stat(g).mean[0] < 140:
        g = ImageOps.invert(g)
    g = ImageEnhance.Contrast(g).enhance(2.0)
    g = g.filter(ImageFilter.SHARPEN)
    if min(g.size) < 1000:
        w, h = g.size
        g = g.resize((w * 2, h * 2), Image.LANCZOS)
    return g

def _ocr_page(img: Image.Image) -> str:
    pre = _preprocess_for_ocr(img)
    return pytesseract.image_to_string(pre, lang=OCR_LANG, config=OCR_CONFIG)

def _merge_dedupe(base: str, extra: str) -> str:
    base_set = {ln.strip() for ln in base.splitlines() if ln.strip()}
    merged = [ln.strip() for ln in base.splitlines() if ln.strip()]
    for ln in extra.splitlines():
        s = ln.strip()
        if s and s not in base_set:
            merged.append(s)
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

# ======================= 공개 함수 ===============================
def extract_text_from_pdf(pdf_data: Union[str, bytes, "UploadedFile"]) -> str:
    pdf_bytes = _get_pdf_bytes(pdf_data)
    pages_text: List[str] = []

    pil_pages = convert_from_bytes(pdf_bytes, dpi=DPI)

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            base_text = page.extract_text() or ""
            img_objs: Sequence = page.objects.get("image", getattr(page, "images", []))
            needs_ocr = len(base_text.strip()) < MIN_CHARS or len(img_objs) > 0

            # ✅ 코드 이미지(Gemini OCR) 보강
            try:
                for img in img_objs:
                    if img["width"] > CARBON_WIDTH_THRESHOLD and img["height"] < CARBON_HEIGHT_THRESHOLD:
                        x0, y0, x1, y1 = map(int, (img["x0"], img["top"], img["x1"], img["bottom"]))
                        crop = pil_pages[idx].crop((x0, y0, x1, y1))
                        gemini_code = gemini_code_ocr(crop)
                        base_text += f"\n```python\n{gemini_code}\n```"
            except Exception as e:
                base_text += f"\n[Gemini OCR 오류: {str(e)}]"

            # ✅ 추가 OCR 필요할 경우 (전체 페이지 기준)
            if needs_ocr:
                pil_img = pil_pages[idx]
                ocr_text = _ocr_page(pil_img)
                base_text = _merge_dedupe(base_text, ocr_text)

            pages_text.append(base_text)

    return "\n".join(pages_text).strip()
