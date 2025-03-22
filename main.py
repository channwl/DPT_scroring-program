import streamlit as st
import PyPDF2
from openai import OpenAI
import random
import matplotlib.pyplot as plt
import pandas as pd

# OpenAI 클라이언트 최신 방식
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

# 초기 채점 기준 생성 함수
def generate_initial_rubric(problem_text):
    prompt = f"""다음 문제에 대한 초기 채점 기준을 작성해 주세요.
문제: {problem_text}

- 평가 항목과 점수 배점은 문제의 성격에 맞게 자유롭게 설계해 주세요.
- 항목별로 구체적인 평가 포인트도 작성해 주세요.
- 예시) 
  채점 항목: 논리적 전개 | 배점: 20점 | 세부 기준: 서술이 논리적이며 구조가 잘 짜여 있는지
- 상세하고 일관성 있게 작성해 주세요."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    return response.choices[0].message.content

# 학생 답안 채점 함수
def grade_student_answer(rubric, answer_text):
    prompt = f"""다음은 교수자가 작성한 채점 기준입니다:\n{rubric}\n\n
그리고 아래는 학생의 답안입니다:\n{answer_text}\n\n
이 채점 기준에 따라 학생의 답안을 점수화하고, 항목별 점수와 총점, 간략 피드백을 표 형태로 작성해 주세요."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    return response.choices[0].message.content

# Streamlit UI 시작
st.title("🎓 AI 교수자 채점 & 분석 시스템")

with st.sidebar:
    st.header("📂 STEP 1: 문제 파일 업로드")
    problem_pdf = st.file_uploader("👉 문제 PDF 파일을 업로드해 주세요.", type="pdf")

    st.header("📂 STEP 2: 학생 답안 PDF 업로드")
    answers_pdf = st.file_uploader("👉 학생 답안 PDF 파일(30명 이상)을 업로드해 주세요.", type="pdf")

    generate_rubric_btn = st.button("✅ 1단계: 채점 기준 생성")
    random_grade_btn = st.button("✅ 2단계: 랜덤 답안 채점 및 시각화")

if problem_pdf:
    problem_text = extract_text_from_pdf(problem_pdf)
    st.subheader("📜 추출된 문제 내용")
    st.write(problem_text)

    if generate_rubric_btn:
        with st.spinner("GPT가 채점 기준을 작성 중입니다..."):
            rubric = generate_initial_rubric(problem_text)
        st.success("채점 기준 생성 완료!")
        st.subheader("📊 생성된 채점 기준")
        st.write(rubric)

        # 세션에 저장
        st.session_state.rubric = rubric

if answers_pdf and random_grade_btn:
    if 'rubric' not in st.session_state:
        st.warning("먼저 채점 기준을 생성해 주세요.")
    else:
        st.subheader("📜 학생 답안 추출 중...")
        answers_text = extract_text_from_pdf(answers_pdf)
        # 간단히 학생 답안 분리 (각 답안은 '학생' 또는 'Student'로 시작한다고 가정)
        answers_list = answers_text.split("학생")
        answers_list = [a.strip() for a in answers_list if len(a.strip()) > 20]

        st.write(f"총 {len(answers_list)}명의 답안이 추출되었습니다.")

        # 랜덤으로 5명 추출 및 채점
        random_answers = random.sample(answers_list, min(5, len(answers_list)))
        results = []

        for idx, ans in enumerate(random_answers, 1):
            with st.spinner(f"{idx}번째 학생 답안 채점 중..."):
                grading_result = grade_student_answer(st.session_state.rubric, ans)
                st.write(f"### ✅ 학생 {idx} 채점 결과")
                st.write(grading_result)

                # 점수 추출 시도 (정규표현식 활용 추천, 여기선 수동으로 처리하거나 GPT가 표를 주는 경우 자동 추출 가능)
                # 예제에서는 총점: XX점 형태로 반환한다고 가정
                import re
                match = re.search(r"총점[:：]?\s*(\d+)", grading_result)
                if match:
                    total_score = int(match.group(1))
                    results.append(total_score)

        # 시각화
        if results:
            st.subheader("📈 점수 분포 시각화")
            score_df = pd.DataFrame({'Score': results})
            fig, ax = plt.subplots()
            ax.hist(score_df['Score'], bins=10, edgecolor='black')
            ax.set_xlabel("점수")
            ax.set_ylabel("학생 수")
            ax.set_title("랜덤 추출 학생 점수 분포")
            st.pyplot(fig)
