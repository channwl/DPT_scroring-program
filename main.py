import streamlit as st
import PyPDF2
import random
import re
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate

# 페이지 설정
st.set_page_config(page_title="AI 채점 시스템", layout="wide")

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

prompt_template = PromptTemplate.from_template("{history}\n{input}")
rubric_chain = LLMChain(
    llm=llm,
    prompt=prompt_template,
    memory=st.session_state.rubric_memory
)

# ----------------------------
# 사용자 친화적 파일 업로드
# ----------------------------
def styled_file_uploader(label, key, type):
    st.markdown(f"""<div style='padding: 10px 0 5px 0; font-weight: bold;'>{label}</div>""", unsafe_allow_html=True)
    return st.file_uploader("", key=key, type=type, label_visibility="collapsed")

# PDF 텍스트 추출
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(pdf_file)
    return "".join([page.extract_text() or "" for page in reader.pages])

# 파일명에서 이름/학번 추출
def extract_info_from_filename(filename):
    id_match = re.search(r"\d{8}", filename)
    name_match = re.findall(r"[가-힣]{2,4}", filename)
    return name_match[-1] if name_match else "UnknownName", id_match.group() if id_match else "UnknownID"

# 답안 및 정보 추출
def extract_answers_and_info_from_files(pdf_files):
    answers, student_info = [], []
    for file in pdf_files:
        text = extract_text_from_pdf(file)
        name, sid = extract_info_from_filename(file.name)
        if len(text.strip()) > 20:
            answers.append(text)
            student_info.append({'name': name, 'id': sid})
    return answers, student_info

# ----------------------------
# 사이드바 구성
# ----------------------------
with st.sidebar:
    st.title("📘 채점 흐름 가이드")
    st.markdown("1️⃣ 문제 업로드 및 채점 기준")
    st.markdown("2️⃣ 학생 답안 업로드 및 채점")
    st.markdown("3️⃣ 교수자 피드백 입력")

    st.markdown("---")
    st.subheader("📝 교수자 피드백")
    st.session_state.feedback_text = st.text_area("채점 기준 수정용 피드백", key="sidebar_feedback")

    st.markdown("---")
    st.caption("🚀 본 서비스는 **DPT 팀**이 개발한 교수자 지원 도구입니다.")
    st.caption("채점 기준 수립과 일관된 채점을 돕기 위해 설계되었습니다.")

# ----------------------------
# STEP 1: 문제 업로드 및 채점 기준 생성
# ----------------------------
with st.expander("📌 STEP 1: 문제 업로드 및 채점 기준 생성", expanded=True):
    uploaded_problem = styled_file_uploader("📄 문제 PDF 업로드", "upload_problem", ["pdf"])

    if uploaded_problem:
        st.session_state.problem_pdf = uploaded_problem
        st.session_state.problem_filename = uploaded_problem.name

        problem_text = extract_text_from_pdf(uploaded_problem)
        rubric_key = f"rubric_{st.session_state.problem_filename}"

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

# ----------------------------
# STEP 2: 답안 업로드 및 무작위 채점
# ----------------------------
with st.expander("🎯 STEP 2: 무작위 학생 채점 결과", expanded=True):
    answers_pdfs = styled_file_uploader("📥 답안 PDF 업로드 (복수 가능)", "upload_answers", ["pdf"])

    if "problem_pdf" not in st.session_state:
        st.info("STEP 1에서 문제 PDF를 먼저 업로드해주세요.")
    elif answers_pdfs:
        rubric_key = f"rubric_{st.session_state.problem_filename}"

        if rubric_key not in st.session_state:
            st.warning("채점 기준이 먼저 생성되어야 합니다.")
        else:
            if st.button("✅ 무작위 채점 실행"):
                all_answers, student_info_list = extract_answers_and_info_from_files(answers_pdfs)
                if not all_answers:
                    st.warning("답안이 너무 짧거나 추출 실패했습니다.")
                else:
                    idx = random.randint(0, len(all_answers) - 1)
                    selected_student = student_info_list[idx]
                    answer = all_answers[idx]

                    prompt = f"""다음은 채점 기준입니다:
{st.session_state[rubric_key]}

그리고 아래는 학생 답안입니다:
{answer}

이 기준에 따라 채점 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |
표 아래에 총점과 간단한 피드백도 작성해주세요."""

                    with st.spinner("GPT가 채점 중입니다..."):
                        result = rubric_chain.invoke({"input": prompt})
                        st.session_state.last_grading_result = result["text"]
                        st.session_state.last_selected_student = selected_student

                    st.success("✅ 채점 완료")

    if "last_grading_result" in st.session_state:
        student = st.session_state["last_selected_student"]
        st.subheader(f"📋 최근 채점 결과 - {student['name']} ({student['id']})")
        st.write(st.session_state["last_grading_result"])

# ----------------------------
# STEP 3: 피드백 반영 및 수정
# ----------------------------
with st.expander("♻️ STEP 3: 교수자 피드백 반영 및 기준 수정", expanded=True):
    if "problem_pdf" not in st.session_state:
        st.info("STEP 1에서 문제 PDF를 먼저 업로드해주세요.")
    else:
        rubric_key = f"rubric_{st.session_state.problem_filename}"

        if rubric_key not in st.session_state:
            st.warning("채점 기준이 먼저 생성되어야 합니다.")
        else:
            feedback_text = st.session_state.get("feedback_text", "")

            if st.button("✏️ 피드백 반영하여 채점 기준 수정"):
                prompt = f"""다음은 기존 채점 기준입니다:
{st.session_state[rubric_key]}

아래는 교수자의 피드백입니다:
{feedback_text}

이 피드백을 반영해서 채점 기준을 수정해 주세요.
- 형식은 '채점 항목 | 배점 | 세부 기준' 표 형식으로 유지해주세요."""

                with st.spinner("GPT가 채점 기준을 수정 중입니다..."):
                    updated = rubric_chain.invoke({"input": prompt})
                    st.session_state[rubric_key] = updated["text"]
                    st.success("✅ 채점 기준 수정 완료")

            if rubric_key in st.session_state:
                st.subheader("🆕 수정된 채점 기준")
                st.write(st.session_state[rubric_key])
