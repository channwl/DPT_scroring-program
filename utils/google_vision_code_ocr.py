# utils/google_vision_code_ocr.py - Gemini OCR 함수
import os, io, base64, tempfile
from vertexai.preview import generative_models as genai #Vertax AI Gemini Vision 호출용 라이브러리
from PIL import Image

# 1) secrets로부터 임시 인증파일 생성 (환경변수에서 인증번호 가져와 Json 파일로 저장) -> Vertex API에 사용
if "GOOGLE_CREDENTIALS" in os.environ: #환경변수 설정되있는 경우에만 실행
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as f:
        f.write(os.environ["GOOGLE_CREDENTIALS"])
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name

PROJECT   = os.getenv("GCP_PROJECT_ID")
LOCATION  = os.getenv("GCP_LOCATION", "us-central1")

MODEL_URI = f"projects/{PROJECT}/locations/{LOCATION}/publishers/google/models/gemini-1.5-pro-vision"

def _pil_to_b64(img: Image.Image) -> str: #이미지 변환 유틸 함수
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()

def gemini_code_ocr(pil_img: Image.Image) -> str:
    model = genai.GenerativeModel(MODEL_URI) #위에서 정의한 모델 인스턴스화
    prompt = "이 이미지에 있는 파이썬 코드를 들여쓰기 포함 순수 텍스트로만 반환하세요."
    resp = model.generate_content(
        [{"type": "image/jpeg", "data": _pil_to_b64(pil_img)}, prompt]
    ) #첫번째 요소는 이미지, 두번째 요소는 텍스트 프롬프트
    return resp.text.strip()
