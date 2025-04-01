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

if "generated_rubrics" not in st.session_state:
    st.session_state.generated_rubrics = {}  # 생성된 채점 기준을 저장할 딕셔너리

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

        # 이미 생성된 채점 기준이 있는지 확인
        if rubric_key not in st.session_state.generated_rubrics:
            prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요 (반드시 **한글**로 작성):

문제: {text}

요구사항:
- 표 형식으로 작성해주세요 (예: '채점 항목 | 배점 | 세부 기준')
- 각 항목의 세부 기준은 구체적으로 작성해주세요
- 설명은 반드시 **한글**로 작성해야 하며, 영어 혼용 없이 작성해주세요
- 표 아래에 **배점 총합**도 함께 작성해주세요
"""
            if st.button("📐 채점 기준 생성"):
                # 메모리 초기화하여 이전 대화가 영향을 주지 않도록 함
                st.session_state.rubric_memory.clear()
                
                with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                    result = rubric_chain.invoke({"input": prompt})
                    # 생성된 채점 기준을 별도 딕셔너리에 저장
                    st.session_state.generated_rubrics[rubric_key] = result["text"]
                    st.success("✅ 채점 기준 생성 완료")
        else:
            if st.button("📐 채점 기준 재생성"):
                st.warning("⚠️ 이미 생성된 채점 기준이 있습니다. 재생성하시겠습니까?")
                confirm = st.button("확인", key="confirm_regenerate")
                if confirm:
                    # 여기서는 명시적으로 사용자가 재생성을 원할 때만 처리
                    prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요 (반드시 **한글**로 작성):

문제: {text}

요구사항:
- 표 형식으로 작성해주세요 (예: '채점 항목 | 배점 | 세부 기준')
- 각 항목의 세부 기준은 구체적으로 작성해주세요
- 설명은 반드시 **한글**로 작성해야 하며, 영어 혼용 없이 작성해주세요
- 표 아래에 **배점 총합**도 함께 작성해주세요
"""
                    st.session_state.rubric_memory.clear()
                    with st.spinner("GPT가 채점 기준을 재생성 중입니다..."):
                        result = rubric_chain.invoke({"input": prompt})
                        st.session_state.generated_rubrics[rubric_key] = result["text"]
                        st.success("✅ 채점 기준 재생성 완료")

        # 채점 기준 표시
        if rubric_key in st.session_state.generated_rubrics:
            st.subheader("📊 채점 기준")
            st.write(st.session_state.generated_rubrics[rubric_key])


# STEP 2
elif st.session_state.step == 2:
    student_pdfs = st.file_uploader("📥 학생 답안 PDF 업로드 (여러 개)", type="pdf", accept_multiple_files=True, key="student_answers")
    if st.session_state.get("problem_pdf") and student_pdfs:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        if rubric_key not in st.session_state.generated_rubrics:
            st.warning("채점 기준이 없습니다. STEP 1에서 먼저 채점 기준을 생성해주세요.")
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
{st.session_state.generated_rubrics[rubric_key]}

그리고 아래는 학생 답안입니다:
{answer}

이 기준에 따라 채점 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |
표 아래에 총점과 간단한 피드백도 작성해주세요."""

                    with st.spinner("GPT가 채점 중입니다..."):
                        # 채점에는 메모리가 필요하지 않으므로 별도 체인을 만들어 사용
                        grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                        result = grading_chain.invoke({"input": prompt})
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
        
        if rubric_key not in st.session_state.generated_rubrics:
            st.warning("채점 기준이 없습니다. STEP 1에서 먼저 채점 기준을 생성해주세요.")
        elif st.button("♻️ 피드백 반영"):
            # 원본 채점 기준 보존을 위해 수정된 채점 기준은 별도 키에 저장
            if "modified_rubrics" not in st.session_state:
                st.session_state.modified_rubrics = {}
            
            prompt = f"""기존 채점 기준:
{st.session_state.generated_rubrics[rubric_key]}

피드백:
{feedback}

피드백을 반영한 채점 기준을 '채점 항목 | 배점 | 세부 기준' 형식의 표로 다시 작성해주세요."""
            
            with st.spinner("GPT가 기준을 수정 중입니다..."):
                # 피드백 반영에도 별도 체인 사용
                feedback_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                updated = feedback_chain.invoke({"input": prompt})
                st.session_state.modified_rubrics[rubric_key] = updated["text"]
                st.success("✅ 채점 기준 수정 완료")

        # 원본 채점 기준 표시
        if rubric_key in st.session_state.generated_rubrics:
            st.subheader("📊 원본 채점 기준")
            st.write(st.session_state.generated_rubrics[rubric_key])
            
            # 수정된 채점 기준이 있으면 표시
            if "modified_rubrics" in st.session_state and rubric_key in st.session_state.modified_rubrics:
                st.subheader("🆕 수정된 채점 기준")
                st.write(st.session_state.modified_rubrics[rubric_key])
