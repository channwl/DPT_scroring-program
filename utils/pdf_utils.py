from PIL import Image
import pytesseract
import fitz  # PyMuPDF
import io

def extract_text_from_pdf(pdf_path: str, lang: str = 'eng+kor') -> str:
    """
    텍스트 기반 PDF는 PyMuPDF로 텍스트 추출하고,
    이미지가 포함된 경우 OCR로 병합해서 반환.
    """
    doc = fitz.open(pdf_path)
    combined_output = ""

    for page_num, page in enumerate(doc):
        # 일반 텍스트 추출
        text = page.get_text() or ""
        combined_output += f"\n--- Page {page_num + 1} 텍스트 ---\n{text}"

        # 이미지 OCR 추출
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                pil_image = Image.open(io.BytesIO(image_bytes))

                ocr_result = pytesseract.image_to_string(pil_image, lang=lang)
                combined_output += f"\n--- Page {page_num + 1} 이미지 {img_index + 1} OCR ---\n{ocr_result}"
            except Exception as e:
                combined_output += f"\n[OCR 실패: {e}]"

    return combined_output.strip()
