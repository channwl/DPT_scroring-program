import streamlit as st
import PyPDF2
from openai import OpenAI
import random
import re
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

- 항목별로 '채점 항목 | 배점 | 세부 기준' 형태의 표로 작성해 주세요.
- 표 아래에 항목별 배점 합계도 표기해 주세요.
- 세부 기준은 상세하고 구체적으로 작성해 주세요."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    return response.choices[0].message.content

# 학생 답안 채점 함수 (GPT는 표만 작성하도록 시킴)
def grade_student_answer(rubric, answer_text):
    prompt = f"""다음은 교수자가 작성한 채점 기준입니다:
{rubric}

아래는 학생 답안입니다:
{answer_text}

각 항목별로 아래 형태의 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |

- 표 마지막에 GPT 추천 총점도 표로 작성해 주세요.
- 마지막에 간략한 피드백도 포함해 주세요.
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    return response.choices[0].message.content


# 학생 답안 및 정보 추출 함수
def extract_answers_and_info(pdf_text):
    pattern = re.compile(r"([가-힣]{2,10})\s*\(?([0-9]{8})\)?\s*(.*?)(?=(?:[가-힣]{2,10}\s*\(?[0-9]{8}\)?|$))", re.DOTALL)
    matches = pattern.finditer(pdf_text)

    answers = []
    student_info = []

    for match in matches:
        name = match.group(1).strip()
        student_id = match.group(2).strip()
        answer_text = match.group(3).strip()

        if len(answer_text) > 20:
            answers.append(answer_text)
            student_info.append({'name': name, 'id': student_id})

    return answers, student_info

# Streamlit UI 시작
st.title("🎓 AI 교수자 채점 시스템")

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
            pdf_text = extract_text_from_pdf(pdf_file)
            answers, info_list = extract_answers_and_info(pdf_text)

            for i, ans in enumerate(answers):
                name = info_list[i]['name']
                sid = info_list[i]['id']
                all_answers.append(ans)
                student_info_list.append({'name': name, 'id': sid})

        st.write(f"총 {len(all_answers)}명의 답안이 추출되었습니다.")

        random_index = random.randint(0, len(all_answers) - 1)
        random_answer = all_answers[random_index]
        selected_student = student_info_list[random_index]

        st.info(f"이번에 채점할 학생: 이름 - {selected_student['name']}, 학번 - {selected_student['id']}")

        with st.spinner("무작위 학생 답안을 채점 중입니다..."):
            grading_result = grade_student_answer(st.session_state.rubric, random_answer)

        st.success("✅ GPT 추천 채점 결과:")
        st.write(grading_result)
