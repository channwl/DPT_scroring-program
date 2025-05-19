import fitz  # PyMuPDF
import io
import urllib.parse

def extract_text_from_pdf(pdf_data):
    """
    PDF 데이터를 받아 텍스트를 문자열로 추출 (PyMuPDF 사용)
    - pdf_data는 UploadedFile, bytes, 또는 파일 경로(str) 일 수 있음
    """
    try:
        if isinstance(pdf_data, str):
            # URL 인코딩된 한글 파일명을 디코딩
            decoded_path = urllib.parse.unquote(pdf_data)
            doc = fitz.open(decoded_path)
        elif isinstance(pdf_data, bytes):
            doc = fitz.open(stream=pdf_data, filetype="pdf")
        elif hasattr(pdf_data, "read"):
            try:
                # 파일 객체에서 바이트로 읽기
                pdf_bytes = pdf_data.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            except Exception as file_error:
                # 파일 객체 읽기 실패 시 이름 사용해 다시 시도
                if hasattr(pdf_data, "name"):
                    pdf_data.seek(0)  # 파일 포인터 초기화
                    pdf_bytes = pdf_data.read()
                    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                else:
                    raise file_error
        else:
            raise ValueError("지원하지 않는 파일 형식입니다.")
        
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()  # 파일 닫기 (메모리 누수 방지)
        return text.strip()
    except Exception as e:
        return f"[오류] PyMuPDF 텍스트 추출 실패: {str(e)}"
