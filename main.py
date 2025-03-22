import streamlit as st
import PyPDF2
from openai import OpenAI

# OpenAI 클라이언트 초기화 (최신 버전 방식)
client = OpenAI(api_key=st.secrets["openai"]["API_KEY"])

# PDF → 텍스트 추출 함수
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    return text

# GPT 초기 채점 기준 생성 함수 (최신 방식)
def generate_initial_rubric(problem_text):
    prompt = f"""다음 문제에 대한 초기 채점 기준을 백지 상태에서 자유롭게 작성해 주세요.
문제: {problem_text}

- 평가 항목과 점수 배점은 문제의 성격에 맞게 자유롭게 설계해 주세요.
- 항목별로 구체적인 평가 포인트도 작성해 주세요.
- 예시) 
  채점 항목: 논리적 전개 | 배점: 20점 | 세부 기준: 서술이 논리적이며 구조가 잘 짜여 있는지
- 최대한 상세하고 일관성 있게 작성해 주세요."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    return response.choices[0].message.content

# UI 구성
st.title("🎓 AI 기반 교수자 맞춤형 채점 기준 생성 시스템")

st.write("""
안녕하세요!  
본 시스템은 **PDF로 된 문제 파일**을 분석해,  
GPT를 통해 **초기 채점 기준**을 자동 생성해 드리는 서비스입니다.  
왼쪽의 단계를 따라 업로드하고 요청해 주세요. 😊
""")

with st.sidebar:
    st.header("📂 STEP 1: 문제 파일 업로드")
    pdf_file = st.file_uploader("👉 PDF 파일을 선택해 주세요.", type="pdf")

    st.header("🤖 STEP 2: 채점 기준 받기")
    generate_button = st.button("✅ 채점 기준 생성 요청하기")

if pdf_file is not None:
    extracted_text = extract_text_from_pdf(pdf_file)
    st.success("문제 내용이 성공적으로 추출되었습니다! 🎉")
    st.subheader("📜 추출된 문제 내용")
    st.write(extracted_text)

    if generate_button:
        with st.spinner("열심히 채점 기준을 작성 중입니다... ⏳"):
            rubric = generate_initial_rubric(extracted_text)
        st.success("채점 기준이 생성되었습니다! ✅")
        st.subheader("📊 생성된 초기 채점 기준")
        st.write(rubric)
else:
    st.info("왼쪽 메뉴에서 PDF 파일을 업로드해 주세요.")


