import fitz  # PyMuPDF
import io

def extract_text_from_pdf(pdf_data):
    """
    PDF 데이터를 받아 텍스트를 문자열로 추출 (PyMuPDF 사용)
    - pdf_data는 UploadedFile, bytes, 또는 파일 경로(str) 일 수 있음
    """
    try:
        if isinstance(pdf_data, str):
            # 파일 경로
            doc = fitz.open(pdf_data)
        elif isinstance(pdf_data, bytes):
            doc = fitz.open(stream=pdf_data, filetype="pdf")
        elif hasattr(pdf_data, "read"):
            pdf_bytes = pdf_data.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        else:
            raise ValueError("지원하지 않는 파일 형식입니다.")

        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()

    except Exception as e:
        return f"[오류] PyMuPDF 텍스트 추출 실패: {str(e)}"
