"""
PDF에서 최대한 텍스트를 추출하기 위한 모듈.
- 먼저 pdfplumber로 레이어 텍스트 추출
- Carbon 캡처처럼 어두운 배경 이미지는 Gemini Vision OCR로 코드 추출
"""

import io, re, o
from typing import Union, List, Sequence

import pdfplumber #pdf의 텍스트 레이어 추출
from pdf2image import convert_from_bytes ##PDF 페이지를 PIL 이미지로 변환
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageStat #이미지 전처리
import pytesseract #Tesseract OCR (텍스트 인식)


from utils.google_vision_code_ocr import gemini_code_ocr  #Gemini OCR 함수 추가

# ===== 사용자 조정 파라미터 =====
MIN_CHARS   = 40 #텍스트가 너무 짧으면 OCR 필요하다고 인식 
OCR_LANG    = "kor+eng" #한국어 + 영어 OCR
DPI         = 300 #해상도
OCR_CONFIG = (
    '--oem 3 --psm 6 -c preserve_interword_spaces=1 '
    '-c tessedit_char_whitelist='
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    '_-+=*/(){}[]<>.:;.,|%$&#@!?`~^'
)
CARBON_WIDTH_THRESHOLD = 200
CARBON_HEIGHT_THRESHOLD = 150

# ------------------------------------------------------------------
def _preprocess_for_ocr(img: Image.Image) -> Image.Image: #이미지 전처리 함수
    g = img.convert("L") #이미지 그레이스케일 변환
    if ImageStat.Stat(g).mean[0] < 140: #평균 밝기가 어두우면 흑백 반전 -> 검은 배경의 흰 글씨를 잘 못읽음
        g = ImageOps.invert(g) #대비를 2배 향상 : 텍스트 강조
    g = ImageEnhance.Contrast(g).enhance(2.0)
    g = g.filter(ImageFilter.SHARPEN)
    if min(g.size) < 1000: #이미지가 작으면 확대 (고해상도 OCR 보장)
        w, h = g.size
        g = g.resize((w * 2, h * 2), Image.LANCZOS)
    return g

def _ocr_page(img: Image.Image) -> str: #위 전처리 이미지를 토대로, Tesseract로 OCR 수행
    pre = _preprocess_for_ocr(img)
    return pytesseract.image_to_string(pre, lang=OCR_LANG, config=OCR_CONFIG)

def _merge_dedupe(base: str, extra: str) -> str: 
    base_set = {ln.strip() for ln in base.splitlines() if ln.strip()} #기존 텍스트 (base)와 OCR로 얻은 추가 텍스트 (extra) 병합하되 중복 제거
    merged = [ln.strip() for ln in base.splitlines() if ln.strip()] #base에서 줄 단위로 중복 검사용 set 생성
    for ln in extra.splitlines(): #병합용 초기 리스트
        s = ln.strip()
        if s and s not in base_set:
            merged.append(s)
    return "\n".join(merged) #중복되지 않은 OCR 결과만 병합

#입력이 파일 경로, bytes, Strealmit 업로드 객체 모두 가능한 형태로 구성
#모두 byte로 일괄 변환

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

# ======================= 핵심 처리 함수 ===============================
def extract_text_from_pdf(pdf_data: Union[str, bytes, "UploadedFile"]) -> str:

    #PDF 데이터를 byte로 변환
    pdf_bytes = _get_pdf_bytes(pdf_data)
    pages_text: List[str] = []

    #PDF를 이미지로 변환 (OCR)
    pil_pages = convert_from_bytes(pdf_bytes, dpi=DPI)

    #pdfplumber로 텍스트 추출
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for idx, page in enumerate(pdf.pages):
            base_text = page.extract_text() or "" #기본 텍스트 추출 + OCR 필요성 판단
            img_objs: Sequence = page.objects.get("image", getattr(page, "images", []))
            needs_ocr = len(base_text.strip()) < MIN_CHARS or len(img_objs) > 0

            #코드 이미지(Gemini OCR) 보강 - carbon 대비
            try:
                for img in img_objs:
                    if img["width"] > CARBON_WIDTH_THRESHOLD and img["height"] < CARBON_HEIGHT_THRESHOLD:
                        x0, y0, x1, y1 = map(int, (img["x0"], img["top"], img["x1"], img["bottom"]))
                        crop = pil_pages[idx].crop((x0, y0, x1, y1))
                        gemini_code = gemini_code_ocr(crop)
                        base_text += f"\n```python\n{gemini_code}\n```"
            except Exception as e:
                base_text += f"\n[Gemini OCR 오류: {str(e)}]"

            # 필요 시에 전체 페이지 OCR 수행
            
            if needs_ocr:
                pil_img = pil_pages[idx]
                ocr_text = _ocr_page(pil_img)
                base_text = _merge_dedupe(base_text, ocr_text)

            pages_text.append(base_text)

    return "\n".join(pages_text).strip()
