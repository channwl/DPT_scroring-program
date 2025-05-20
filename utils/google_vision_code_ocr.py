# utils/google_vision_code_ocr.py
import os, io, base64, tempfile
from vertexai.preview import generative_models as genai
from PIL import Image

# 1) secrets로부터 임시 인증파일 생성
if "GOOGLE_CREDENTIALS" in os.environ:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
        f.write(os.environ["GOOGLE_CREDENTIALS"])
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name

PROJECT   = os.getenv("GCP_PROJECT_ID")
LOCATION  = os.getenv("GCP_LOCATION", "us-central1")

MODEL_URI = f"projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/gemini-1.5-pro-vision"

def _pil_to_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()

def gemini_code_ocr(pil_img: Image.Image) -> str:
    model = genai.GenerativeModel(MODEL_URI)
    prompt = "이 이미지에 있는 파이썬 코드를 들여쓰기 포함 순수 텍스트로만 반환하세요."
    resp = model.generate_content(
        [{"type": "image/jpeg", "data": _pil_to_b64(pil_img)}, prompt]
    )
    return resp.text.strip()
