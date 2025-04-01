import streamlit as st
import PyPDF2
import random
import re
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate

# GPT 연결
llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

# 세션 상태 초기화
if "rubric_memory" not in st.session_state:
    st.session_state.rubric_memory = ConversationSummaryMemory(
        llm=llm,
        memory_key="history",
        return_messages=True
    )

if "step" not in st.session_state:
    st.session_state.step = 1

# LLMChain 구성
prompt_template = PromptTemplate.from_template("{history}\n{input}")
rubric_chain = LLMChain(
    llm=llm,
    prompt=prompt_template,
    memory=st.session_state.rubric_memory
)

# PDF 텍스트 추출
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    return text

# 파일명에서 이름/학번 추출
def extract_info_from_filename(filename):
    id_match = re.search(r"\d{8}", filename)
    name_match = re.findall(r"[가-힣]{2,4}", filename)
    student_id = id_match.group() if id_match else "UnknownID"
    student_name = name_match[-1] if name_match else "UnknownName"
    return student_name, student_id

# 답안/학생정보 추출
def extract_answers_and_info_from_files(pdf_files):
    answers, student_info = [], []
    for pdf_file in pdf_files:
        text = extract_text_from_pdf(pdf_file)
        name, student_id = extract_info_from_filename(pdf_file.name)
        if len(text.strip()) > 20:
            answers.append(text)
            student_info.append({'name': name, 'id': student_id})
    return answers, student_info

# 헤더
st.title("🎓 AI 교수자 채점 시스템")
st.markdown("자동 채점 | GPT-4o + LangChain")

# 이전/다음 단계 버튼
col1, col2 = st.columns(2)
with col1:
    if st.button("⬅️ 이전 단계", disabled=st.session_state.step == 1):
        st.session_state.step -= 1
with col2:
    if st.button("➡️ 다음 단계", disabled=st.session_state.step == 3):
        st.session_state.step += 1

st.markdown(f"## ✅ 현재 단계: STEP {st.session_state.step}")

# STEP 1: 문제 업로드 및 채점 기준 생성
if st.session_state.step == 1:
    st.header("📌 STEP 1: 문제 PDF 업로드 및 채점 기준 생성")
    problem_pdf = st.file_uploader("문제 PDF 업로드", type="pdf", key="problem_pdf")

    if problem_pdf:
        st.session_state.problem_pdf = problem_pdf
        problem_text = extract_text_from_pdf(problem_pdf)
        rubric_key = f"rubric_{problem_pdf.name}"

        st.subheader("📄 문제 내용")
        st.write(problem_text)

        if rubric_key not in st.session_state:
            prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요:
문제: {problem_text}
- 항목별로 '채점 항목 | 배점 | 세부 기준' 형태로 작성해 주세요.
- 표 아래에 배점 합계도 적어주세요."""
            with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                rubric = rubric_chain.invoke({"input": prompt})
                st.session_state[rubric_key] = rubric["text"]
            st.success("✅ 채점 기준 생성 완료")

        if rubric_key in st.session_state:
            st.subheader("📊 생성된 채점 기준")
            st.write(st.session_state[rubric_key])

# STEP 2: 무작위 채점
elif st.session_state.step == 2:
    st.header("📌 STEP 2: 답안 업로드 및 무작위 채점")
    answers_pdfs = st.file_uploader("답안 PDF 업로드 (여러 개 가능)", type="pdf", accept_multiple_files=True)

    if "problem_pdf" not in st.session_state:
        st.info("먼저 STEP 1에서 문제 PDF를 업로드해주세요.")
    elif answers_pdfs:
        problem_pdf = st.session_state.problem_pdf
        rubric_key = f"rubric_{problem_pdf.name}"

        if rubric_key not in st.session_state:
            st.warning("채점 기준이 먼저 생성되어야 합니다.")
        else:
            if st.button("🎯 무작위 학생 채점"):
                all_answers, student_info_list = extract_answers_and_info_from_files(answers_pdfs)

                if not all_answers:
                    st.warning("답안 내용이 너무 짧거나 추출되지 않았습니다.")
                else:
                    rand_idx = random.randint(0, len(all_answers) - 1)
                    selected_student = student_info_list[rand_idx]
                    random_answer = all_answers[rand_idx]

                    prompt = f"""다음은 채점 기준입니다:
{st.session_state[rubric_key]}

그리고 아래는 학생 답안입니다:
{random_answer}

이 기준에 따라 채점 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |
표 아래에 총점과 간단한 피드백도 작성해주세요."""

                    with st.spinner("GPT가 채점 중입니다..."):
                        grading_result = rubric_chain.invoke({"input": prompt})
                        st.session_state.last_grading_result = grading_result["text"]
                        st.session_state.last_selected_student = selected_student

                    st.success("✅ 채점 완료!")

    # 최근 채점 결과 표시
    if "last_grading_result" in st.session_state:
        student = st.session_state.last_selected_student
        st.subheader(f"📋 최근 채점 결과 - {student['name']} ({student['id']})")
        st.write(st.session_state.last_grading_result)

# STEP 3: 피드백 반영
elif st.session_state.step == 3:
    st.header("📌 STEP 3: 교수자 피드백 반영")
    if "problem_pdf" not in st.session_state:
        st.info("먼저 STEP 1에서 문제 PDF를 업로드해주세요.")
    else:
        problem_pdf = st.session_state.problem_pdf
        rubric_key = f"rubric_{problem_pdf.name}"

        if rubric_key not in st.session_state:
            st.warning("채점 기준이 생성되어야 피드백을 반영할 수 있습니다.")
        else:
            st.subheader("📝 교수자 피드백 입력")
            feedback_text = st.text_area("피드백을 입력하세요 (예: 특정 항목을 더 강조해주세요)")

            if st.button("♻️ 채점 기준 수정"):
                current_rubric = st.session_state[rubric_key]
                prompt = f"""다음은 기존 채점 기준입니다:
{current_rubric}

아래는 교수자의 피드백입니다:
{feedback_text}

이 피드백을 반영해서 채점 기준을 수정해 주세요.
- 형식은 '채점 항목 | 배점 | 세부 기준' 표 형식으로 유지해주세요."""

                with st.spinner("GPT가 기준을 수정 중입니다..."):
                    updated_rubric = rubric_chain.invoke({"input": prompt})
                    st.session_state[rubric_key] = updated_rubric["text"]

                st.success("✅ 채점 기준 수정 완료")
                st.subheader("🆕 수정된 채점 기준")
                st.write(updated_rubric["text"])
