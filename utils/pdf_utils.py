from PIL import Image
import pytesseract
import pdfplumber
import io

def extract_text_from_pdf(pdf_path: str, lang: str = 'eng+kor') -> str:
    """
    텍스트 기반 PDF는 pdfplumber로, 이미지 기반은 OCR로 처리
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text() or "" for page in pdf.pages])
        if text.strip():
            return text
    except Exception as e:
        print(f"[PDFPlumber 오류] {e}")

    return extract_text_via_ocr(pdf_path, lang=lang)

def extract_text_with_image_ocr(pdf_path: str) -> list[str]:
    full_text_by_page = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 텍스트 추출
            text = page.extract_text() or ""

            # 이미지 OCR 추출
            ocr_texts = []
            for img_obj in page.images:
                try:
                    bbox = (img_obj["x0"], img_obj["top"], img_obj["x1"], img_obj["bottom"])
                    cropped = page.crop(bbox).to_image(resolution=300)
                    image_bytes = cropped.original.stream.get_data()
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    
                    # OCR 실행 (한국어/영어 혼합 가능)
                    ocr_result = pytesseract.image_to_string(pil_image, lang="eng+kor")
                    ocr_texts.append(ocr_result)
                except Exception as e:
                    ocr_texts.append(f"[OCR 실패: {str(e)}]")

            combined = text + "\n\n" + "\n".join(ocr_texts)
            full_text_by_page.append(combined.strip())
    return full_text_by_page
