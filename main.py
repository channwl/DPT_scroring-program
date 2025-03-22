import streamlit as st
import PyPDF2
import openai

# GPT API Key 입력창, Streamlit 'Secret 창에서 열어볼 수 있음"
openai.api_key = st.secrets["OPENAI_API_KEY"]

#쉽게 말하자면, PDF -> 글자 변환
def etract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file) #PDF 파일을 읽는 객체 생성
    text = "" #추출한 텍스트를 저장할 빈 문자열 
    for page in pdf_reader.pages: #PDF 페이지를 읽으면서
        text += page.extract_text() #text 변수에 입력
    return text 

#프롬포트 작성 함수 정의
def generate_initial_rubric(problem_text):
    prompt = f"""다음 문제에 대한 초기 채점 기준을 백지 상태에서 자유롭게 작성해 주세요.
문제: {problem_text}

- 평가 항목과 점수 배점은 문제의 성격에 맞게 자유롭게 설계해 주세요.
- 항목별로 구체적인 평가 포인트도 작성해 주세요
- ex) 채점항목 : 논리적 전개 | 배점 : 20점 | 세부 기준 : 서술이 논리적이며 구조가 잘 짜여 있는지
- 최대한 상세하고 일관성 있게 작성해 주세요."""
    
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    return response["choices"][0]["message"]["contenxt"]

st.title("채점 프로그램 (1단계: 초기 채점 기준 생성)")

pdf_file = st.file_uploader("문제 PDF 파일을 업로드 해주세요.", type="pdf")

if pdf_file is not None:
    st.write("PDF 파일 분석 중...")
    extracted_text = extract_text_from_pdf(pdf_file)
    st.write("### 추출된 문제 내용")
    st.write(extracted_text)

    if st.button("초기 채점 기준 생성하기"):
        rubric = generate_initial_rubric(extracted_text)
        st.write("### 생성된 초기 채점 기준")
        st.write(rubric)
