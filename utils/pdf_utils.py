# pdf_utils.py
# 이 파일은 PDF 파일에서 텍스트를 추출하는 유틸 함수들을 포함합니다.
# pdfplumber를 이용하여 페이지 단위로 텍스트를 모아 문자열로 반환합니다.

import pdfplumber
import io

def extract_text_from_pdf(pdf_data):
    """
    PDF 파일(bytes 또는 UploadedFile 객체)을 받아 텍스트를 문자열로 추출
    """
    if isinstance(pdf_data, bytes):
        pdf_stream = io.BytesIO(pdf_data)
    else:
        pdf_stream = io.BytesIO(pdf_data.read())

    text = ""
    with pdfplumber.open(pdf_stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    return text
