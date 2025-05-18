# utils/pdf_utils.py

import fitz  # PyMuPDF
import io

def extract_text_from_pdf(pdf_data):
    """
    PDF 데이터를 받아 텍스트를 문자열로 추출 (PyMuPDF 사용)
    - pdf_data는 UploadedFile 객체(st.file_uploader) 또는 bytes 일 수 있음
    """
    try:
        # pdf_data가 UploadedFile 객체인 경우 → read()
        if hasattr(pdf_data, "read"):
            pdf_bytes = pdf_data.read()
        elif isinstance(pdf_data, bytes):
            pdf_bytes = pdf_data
        else:
            raise ValueError("지원하지 않는 파일 형식입니다.")

        # PyMuPDF로 PDF 열기
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()

    except Exception as e:
        return f"[오류] PyMuPDF 텍스트 추출 실패: {str(e)}"
