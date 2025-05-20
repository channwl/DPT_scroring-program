# utils/pdf_utils.py
"""
PDF에서 최대한 텍스트를 추출하기 위한 모듈.
- 먼저 pdfplumber로 레이어 텍스트 추출
- (텍스트가 부족 OR 이미지 포함) 페이지에는 OCR 보강
- Carbon 캡처처럼 어두운 배경 이미지는 전처리(invert, sharpen, upscale) 후 OCR
"""

import io, re
from typing import Union, List, Sequence

import pdfplumber
from pdf2image import convert_from_bytes
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageStat
import pytesseract

# ===== 사용자 조정 파라미터 =====
MIN_CHARS   = 40          # 페이지당 텍스트가 이보다 적으면 OCR
OCR_LANG    = "kor+eng"   # Tesseract 언어 (한/영 혼합)
DPI         = 300         # pdf2image 해상도
OCR_CONFIG = (
    '--oem 3 --psm 6 -c preserve_interword_spaces=1 '
    '-c tessedit_char_whitelist='
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    '_-+=*/(){}[]<>.:;,\'|%$&#@!?`~^'
)

# ------------------------------------------------------------------
def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """
    Carbon 등 어두운 배경 이미지를 위해:
    1) 그레이스케일 → 배경 어두우면 invert
    2) 대비·선명도 강화
    3) 작은 이미지는 2× 업스케일
    """
    g = img.convert("L")  # grayscale
    # 배경 평균 밝기가 낮으면 반전
    if ImageStat.Stat(g).mean[0] < 140:
        g = ImageOps.invert(g)
    # 대비·샤프닝
    g = ImageEnhance.Contrast(g).enhance(2.0)
    g = g.filter(ImageFilter.SHARPEN)
    # 업스케일
    if min(g.size) < 1000:  # 폭·높이 중 작은 값
        w, h = g.size
        g = g.resize((w * 2, h * 2), Image.LANCZOS)
    return g

def _ocr_page(img: Image.Image) -> str:
    """전처리 후 Tesseract OCR 수행"""
    pre = _preprocess_for_ocr(img)
    return pytesseract.image_to_string(pre, lang=OCR_LANG, config=OCR_CONFIG)

def _merge_dedupe(base: str, extra: str) -> str:
    """base 텍스트 + OCR 텍스트를 줄 단위로 병합하며 중복 제거"""
    base_set = {ln.strip() for ln in base.splitlines() if ln.strip()}
    merged: List[str] = []
    for ln in base.splitlines():
        s = ln.strip()
        if s:
            merged.append(s)
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
    """
    ① pdfplumber로 기본 텍스트 추출
    ② (텍스트 < MIN_CHARS) 또는 (이미지 포함) → OCR 수행
    ③ base + OCR 결과 병합, 줄 중복 제거
    """
    pdf_bytes = _get_pdf_bytes(pdf_data)
    pages_text: List[str] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            base_text = page.extract_text() or ""
            # pdfplumber 0.11+ 는 page.objects["image"]; 이하 버전은 page.images
            img_objs: Sequence = page.objects.get("image", getattr(page, "images", []))
            needs_ocr = len(base_text.strip()) < MIN_CHARS or len(img_objs) > 0

            if needs_ocr:
                pil_img = convert_from_bytes(
                    pdf_bytes,
                    first_page=idx + 1,
                    last_page=idx + 1,
                    fmt="png",
                    thread_count=1,
                    dpi=DPI,
                )[0]
                ocr_text = _ocr_page(pil_img)
                page_text = _merge_dedupe(base_text, ocr_text)
            else:
                page_text = base_text

            pages_text.append(page_text)

    return "\n".join(pages_text).strip()
