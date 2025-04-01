import streamlit as st
import PyPDF2
import random
import re
import io
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate

st.set_page_config(page_title="AI 채점 시스템", layout="wide")

# GPT 연결 및 초기화
llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

if "rubric_memory" not in st.session_state:
    st.session_state.rubric_memory = ConversationSummaryMemory(
        llm=llm,
        memory_key="history",
        return_messages=True
    )

if "step" not in st.session_state:
    st.session_state.step = 1

prompt_template = PromptTemplate.from_template("{history}\n{input}")
rubric_chain = LLMChain(
    llm=llm,
    prompt=prompt_template,
    memory=st.session_state.rubric_memory
)

# 유틸 함수들
def extract_text_from_pdf(pdf_file):
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
    return "".join([page.extract_text() or "" for page in reader.pages])

def extract_info_from_filename(filename):
    id_match = re.search(r"\d{8}", filename)
    name_match = re.findall(r"[가-힣]{2,4}", filename)
    return name_match[-1] if name_match else "UnknownName", id_match.group() if id_match else "UnknownID"

def extract_answers_and_info_from_files(pdf_files):
    answers, info = [], []
    for file in pdf_files:
        file.seek(0)
        text = extract_text_from_pdf(file)
        name, sid = extract_info_from_filename(file.name)
        if len(text.strip()) > 20:
            answers.append(text)
            info.append({'name': name, 'id': sid})
    return answers, info

# 사이드바
with st.sidebar:
    st.markdown("## 📘 채점 흐름")

    if st.button("1️⃣ 문제 업로드 및 채점 기준 생성"):
        st.session_state.step = 1
    if st.button("2️⃣ 학생 답안 업로드 및 무작위 채점"):
        st.session_state.step = 2
    if st.button("3️⃣ 교수자 피드백 입력"):
        st.session_state.step = 3

    st.markdown("### 📝 교수자 피드백", unsafe_allow_html=True)
    st.session_state.feedback_text = st.text_area("채점 기준 수정 피드백", key="sidebar_feedback")

    st.markdown("---")
    st.caption("🚀 본 시스템은 **DPT 팀**이 개발한 교수자 지원 도구입니다.")
    st.caption("채점 기준 수립과 일관된 채점을 돕기 위해 설계되었습니다.")

# 단계 안내 및 버튼
st.markdown(f"### 현재 단계: STEP {st.session_state.step}")

# STEP 1
if st.session_state.step == 1:
    problem_pdf = st.file_uploader("📄 문제 PDF 업로드", type="pdf", key="problem_upload")
    if problem_pdf:
        st.session_state.problem_pdf = problem_pdf
        st.session_state.problem_filename = problem_pdf.name
        text = extract_text_from_pdf(problem_pdf)
        rubric_key = f"rubric_{problem_pdf.name}"

        st.subheader("📃 문제 내용")
        st.write(text)

        prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요:
문제: {text}
- '채점 항목 | 배점 | 세부 기준' 형태로 표 작성
- 배점 합계 포함"""

        if st.button("📐 채점 기준 생성"):
            with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                result = rubric_chain.invoke({"input": prompt})
                st.session_state[rubric_key] = result["text"]
                st.success("✅ 채점 기준 생성 완료")

        if rubric_key in st.session_state:
            st.subheader("📊 채점 기준")
            st.write(st.session_state[rubric_key])

# STEP 2
elif st.session_state.step == 2:
    student_pdfs = st.file_uploader("📥 학생 답안 PDF 업로드 (여러 개)", type="pdf", accept_multiple_files=True, key="student_answers")
    if st.session_state.get("problem_pdf") and student_pdfs:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        if rubric_key not in st.session_state:
            st.warning("채점 기준이 없습니다.")
        else:
            if st.button("🎯 무작위 채점 실행"):
                all_answers, info_list = extract_answers_and_info_from_files(student_pdfs)
                if not all_answers:
                    st.warning("답안을 찾을 수 없습니다.")
                else:
                    idx = random.randint(0, len(all_answers) - 1)
                    selected_student = info_list[idx]
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

    if st.session_state.get("last_grading_result"):
        stu = st.session_state["last_selected_student"]
        st.subheader(f"📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.write(st.session_state["last_grading_result"])

# STEP 3
elif st.session_state.step == 3:
    if st.session_state.get("problem_pdf"):
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        feedback = st.session_state.get("feedback_text", "")
        if rubric_key not in st.session_state:
            st.warning("채점 기준이 없습니다.")
        elif st.button("♻️ 피드백 반영"):
            prompt = f"""기존 채점 기준:
{st.session_state[rubric_key]}

피드백:
{feedback}

피드백을 반영한 채점 기준을 '채점 항목 | 배점 | 세부 기준' 형식의 표로 다시 작성해주세요."""
            with st.spinner("GPT가 기준을 수정 중입니다..."):
                updated = rubric_chain.invoke({"input": prompt})
                st.session_state[rubric_key] = updated["text"]
                st.success("✅ 채점 기준 수정 완료")

        if rubric_key in st.session_state:
            st.subheader("🆕 수정된 채점 기준")
            st.write(st.session_state[rubric_key])
