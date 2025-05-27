import io
import pdfplumber
from typing import Union

def extract_text_from_pdf(pdf_data: Union[str, bytes, "UploadedFile"]) -> str:
    # PDF 데이터를 byte로 변환
    if isinstance(pdf_data, str):
        with open(pdf_data, "rb") as f:
            pdf_bytes = f.read()
    elif isinstance(pdf_data, bytes):
        pdf_bytes = pdf_data
    elif hasattr(pdf_data, "read"):
        pdf_bytes = pdf_data.read()
    else:
        raise ValueError("지원하지 않는 입력 타입입니다.")

    # PDF의 텍스트 레이어에서 텍스트 추출 (OCR 없음)
    pages_text = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    return "\n".join(pages_text).strip()
