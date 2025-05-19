import fitz  # PyMuPDF
import io
import tempfile

def extract_text_from_pdf(pdf_data):
    """
    PDF 데이터를 받아 텍스트를 문자열로 추출 (PyMuPDF 사용)
    - pdf_data는 UploadedFile, bytes, 또는 파일 경로(str) 일 수 있음
    """
    try:
        # 파일 경로일 경우
        if isinstance(pdf_data, str):
            doc = fitz.open(pdf_data)

        # bytes 또는 UploadedFile
        else:
            if hasattr(pdf_data, "read"):
                pdf_bytes = pdf_data.read()
            elif isinstance(pdf_data, bytes):
                pdf_bytes = pdf_data
            else:
                raise ValueError("지원하지 않는 파일 형식입니다.")

            # 임시 파일로 저장 (한글 파일명 문제 우회)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            doc = fitz.open(tmp_path)

        text = ""
        for page in doc:
            text += page.get_text()
        return text.strip()

    except Exception as e:
        return f"[오류] PyMuPDF 텍스트 추출 실패: {str(e)}"
