import pdfplumber
import io

def extract_text_from_pdf(pdf_data):
    """
    PDF 데이터를 받아 텍스트를 문자열로 추출
    - pdf_data는 파일 경로(str), bytes, 또는 UploadedFile 객체일 수 있음
    """
    try:
        if isinstance(pdf_data, str):
            # 파일 경로일 경우
            with pdfplumber.open(pdf_data) as pdf:
                return "\n".join([page.extract_text() or "" for page in pdf.pages])

        elif isinstance(pdf_data, bytes):
            pdf_stream = io.BytesIO(pdf_data)

        else:
            # UploadedFile 객체 (Streamlit의 st.file_uploader 결과)
            pdf_stream = io.BytesIO(pdf_data.read())

        with pdfplumber.open(pdf_stream) as pdf:
            return "\n".join([page.extract_text() or "" for page in pdf.pages])

    except Exception as e:
        return f"[오류] PDF 텍스트 추출 실패: {str(e)}"
