import pdfplumber

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    텍스트 기반 PDF에서 텍스트를 추출합니다.
    OCR 처리는 하지 않습니다.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        return text.strip()
    except Exception as e:
        print(f"[PDF 텍스트 추출 오류] {e}")
        return ""
