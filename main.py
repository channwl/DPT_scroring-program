import streamlit as st
import PyPDF2
from openai import OpenAI
import random
import matplotlib.pyplot as plt
import pandas as pd
import re

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

# 학생 답안 채점 함수 (수정된 버전)
def grade_student_answer(rubric, answer_text):
    prompt = f"""다음은 교수자가 작성한 채점 기준입니다:\n{rubric}\n\n
그리고 아래는 학생의 답안입니다:\n{answer_text}\n\n
이 채점 기준에 따라 학생의 답안을 점수화하고, 아래 사항을 꼭 지켜 작성해 주세요:
- 항목별 점수, 항목명, 세부 평가 내용을 표로 작성
- 표 마지막에 총점을 표기
- 총점은 반드시 각 항목 점수의 합계와 일치하도록 계산
- 항목별 점수 합계와 총점이 일치하는지 검토 후 작성
- 간략한 피드백도 표 아래에 포함"""

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

    st.header("📂 STEP 2: 학생 답안 PDF 여러 개 업로드")
    answers_pdfs = st.file_uploader("👉 학생 답안 PDF 파일(복수 선택 가능)", type="pdf", accept_multiple_files=True)

    generate_rubric_btn = st.button("✅ 1단계: 채점 기준 생성")
    single_random_grade_btn = st.button("✅ 2단계: 무작위 학생 한 명 채점하기")

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

        st.session_state.rubric = rubric

if answers_pdfs and single_random_grade_btn:
    if 'rubric' not in st.session_state:
        st.warning("먼저 채점 기준을 생성해 주세요.")
    else:
        all_answers = []
        student_info_list = []
        st.subheader("📜 학생 답안 추출 중...")

        for pdf_file in answers_pdfs:
            answers_text = extract_text_from_pdf(pdf_file)
            answers_list = answers_text.split("학생")
            answers_list = [a.strip() for a in answers_list if len(a.strip()) > 20]

            filename = pdf_file.name
            file_match = re.match(r"(.+)_([0-9]{8})", filename)
            if file_match:
                student_name_from_file = file_match.group(1)
                student_id_from_file = file_match.group(2)
            else:
                student_name_from_file = "알 수 없음"
                student_id_from_file = "알 수 없음"

            for ans in answers_list:
                all_answers.append(ans)
                student_info_list.append({'name': student_name_from_file, 'id': student_id_from_file})

        st.write(f"총 {len(all_answers)}명의 답안이 추출되었습니다.")

        random_index = random.randint(0, len(all_answers) - 1)
        random_answer = all_answers[random_index]
        selected_student = student_info_list[random_index]

        st.info(f"이번에 채점할 학생: 이름 - {selected_student['name']}, 학번 - {selected_student['id']}")

        with st.spinner("무작위 학생 답안을 채점하는 중입니다..."):
            grading_result = grade_student_answer(st.session_state.rubric, random_answer)

        st.success("무작위 학생의 채점 결과:")
        st.write(grading_result)
