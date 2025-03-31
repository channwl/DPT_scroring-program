import streamlit as st
import PyPDF2
import random
import re
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate

# GPT-4o 연결
llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

# LangChain Memory 설정
if "rubric_memory" not in st.session_state:
    st.session_state.rubric_memory = ConversationSummaryMemory(
        llm=llm,
        memory_key="history",
        return_messages=True
    )

# PromptTemplate 설정
prompt_template = PromptTemplate.from_template("{history}\n{input}")

# LLMChain 구성
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

# PDF 파일들에서 답안 및 학생 정보 추출
def extract_answers_and_info_from_files(pdf_files):
    answers = []
    student_info = []
    for pdf_file in pdf_files:
        pdf_text = extract_text_from_pdf(pdf_file)
        name, student_id = extract_info_from_filename(pdf_file.name)
        if len(pdf_text.strip()) > 20:
            answers.append(pdf_text)
            student_info.append({'name': name, 'id': student_id})
    return answers, student_info

# Streamlit UI 시작
st.title("🎓 AI 교수자 채점 시스템 (탭 기반)")

# 탭 구성
tab1, tab2, tab3 = st.tabs(["① 채점 기준 생성", "② 무작위 학생 채점", "③ 교수자 피드백 반영"])

# ----------------------------
# ① 채점 기준 생성 탭
# ----------------------------
with tab1:
    st.header("STEP 1: 문제 파일 업로드 및 채점 기준 생성")
    problem_pdf = st.file_uploader("문제 PDF 업로드", type="pdf", key="problem_pdf")

    if problem_pdf:
        problem_text = extract_text_from_pdf(problem_pdf)
        rubric_key = f"rubric_{problem_pdf.name}"

        st.subheader("📜 문제 내용")
        st.write(problem_text)

        if st.button("✅ 채점 기준 생성"):
            if rubric_key not in st.session_state:
                prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요:
문제: {problem_text}
- 항목별로 '채점 항목 | 배점 | 세부 기준' 형태로 작성해 주세요.
- 표 아래에 배점 합계도 적어주세요."""
                with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                    rubric = rubric_chain.invoke({"input": prompt})
                    st.session_state[rubric_key] = rubric['text']
                st.success("✅ 채점 기준 생성 완료")
            else:
                st.info("기존 채점 기준이 이미 존재합니다.")

        # 항상 표시
        if rubric_key in st.session_state:
            st.subheader("📊 채점 기준")
            st.write(st.session_state[rubric_key])

# ----------------------------
# ② 무작위 학생 채점 탭
# ----------------------------
with tab2:
    st.header("STEP 2: 학생 답안 업로드 및 무작위 채점")
    answers_pdfs = st.file_uploader("답안 PDF 업로드 (복수 가능)", type="pdf", accept_multiple_files=True, key="answers")

    if "problem_pdf" not in st.session_state or st.session_state.problem_pdf is None:
        st.info("채점 기준 탭에서 문제 PDF를 먼저 업로드해주세요.")
    elif answers_pdfs:
        problem_pdf = st.session_state.problem_pdf
        rubric_key = f"rubric_{problem_pdf.name}"

        if rubric_key not in st.session_state:
            st.warning("채점 기준이 생성되지 않았습니다.")
        else:
            if st.button("✅ 무작위 채점 실행"):
                all_answers, student_info_list = extract_answers_and_info_from_files(answers_pdfs)

                if not all_answers:
                    st.warning("학생 답안을 찾을 수 없습니다.")
                else:
                    random_index = random.randint(0, len(all_answers) - 1)
                    random_answer = all_answers[random_index]
                    selected_student = student_info_list[random_index]

                    st.info(f"채점할 학생: {selected_student['name']} ({selected_student['id']})")

                    prompt = f"""다음은 채점 기준입니다:
{st.session_state[rubric_key]}

그리고 아래는 학생 답안입니다:
{random_answer}

이 기준에 따라 채점 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |
표 아래에 총점과 간단한 피드백도 작성해주세요."""

                    with st.spinner("GPT가 채점 중입니다..."):
                        grading_result = rubric_chain.invoke({"input": prompt})

                    st.success("✅ 채점 완료")
                    st.subheader("📋 GPT 채점 결과")
                    st.write(grading_result['text'])

# ----------------------------
# ③ 교수자 피드백 반영 탭
# ----------------------------
with tab3:
    st.header("STEP 3: 교수자 피드백 반영")

    if "problem_pdf" not in st.session_state or st.session_state.problem_pdf is None:
        st.info("채점 기준 탭에서 문제 PDF를 먼저 업로드해주세요.")
    else:
        problem_pdf = st.session_state.problem_pdf
        rubric_key = f"rubric_{problem_pdf.name}"

        if rubric_key not in st.session_state:
            st.warning("채점 기준이 먼저 생성되어야 합니다.")
        else:
            st.subheader("📝 교수자 피드백 입력")
            feedback_text = st.text_area("피드백을 입력하세요 (예: 이 항목을 더 강조해주세요)")

            if st.button("✅ 피드백 반영하여 채점 기준 수정"):
                current_rubric = st.session_state[rubric_key]
                prompt = f"""다음은 기존 채점 기준입니다:
{current_rubric}

아래는 교수자의 피드백입니다:
{feedback_text}

이 피드백을 반영해서 채점 기준을 수정해 주세요.
- 형식은 '채점 항목 | 배점 | 세부 기준' 표 형식으로 유지해주세요."""

                with st.spinner("GPT가 기준을 수정 중입니다..."):
                    updated_rubric = rubric_chain.invoke({"input": prompt})
                    st.session_state[rubric_key] = updated_rubric['text']

                st.success("✅ 채점 기준 수정 완료")
                st.subheader("🆕 수정된 채점 기준")
                st.write(updated_rubric['text'])
