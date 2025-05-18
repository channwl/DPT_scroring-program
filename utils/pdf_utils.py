import pdfplumber
import io

def extract_text_from_pdf(pdf_data):
    """
    PDF 데이터를 받아 텍스트를 문자열로 추출
    - pdf_data는 파일 경로(str), bytes, 또는 Streamlit UploadedFile 객체일 수 있음
    """
    try:
        # 케이스 1: 파일 경로
        if isinstance(pdf_data, str):
            with pdfplumber.open(pdf_data) as pdf:
                return "\n".join([page.extract_text() or "" for page in pdf.pages])

        # 케이스 2: UploadedFile or bytes
        elif hasattr(pdf_data, "read"):
            # UploadedFile 객체 or 파일 스트림
            byte_data = pdf_data.read()
        elif isinstance(pdf_data, bytes):
            byte_data = pdf_data
        else:
            return "[오류] 지원하지 않는 데이터 형식입니다."

        # pdfplumber에 전달할 스트림 생성
        pdf_stream = io.BytesIO(byte_data)

        with pdfplumber.open(pdf_stream) as pdf:
            return "\n".join([page.extract_text() or "" for page in pdf.pages])

    except Exception as e:
        return f"[오류] PDF 텍스트 추출 실패: {str(e)}"
