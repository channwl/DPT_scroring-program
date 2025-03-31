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

# 교수자 예시 입력 기반 정규표현식 생성
def generate_regex_from_example(example):
    name_match = re.search(r"[가-힣]{2,}", example)
    id_match = re.search(r"\(?\d{8}\)?", example)
    if name_match and id_match:
        return r"([가-힣]{2,10})\s*\(?(\d{8})\)?\s*([\s\S]*?)(?=(?:[가-힣]{2,10})\s*\(?\d{8}\)?|\Z)"
    return None

# 정규표현식 기반 답안 추출
def extract_answers_and_info(pdf_text, pattern_str):
    pattern = re.compile(pattern_str, re.MULTILINE)
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
    problem_pdf = st.file_uploader("문제 PDF 업로드", type="pdf")

    st.header("📂 STEP 2: 학생 답안 PDF 업로드")
    answers_pdfs = st.file_uploader("답안 PDF 업로드 (복수 가능)", type="pdf", accept_multiple_files=True)

    st.header("✍️ STEP 2-1: 학생 정보 예시 입력")
    format_example = st.text_input("예시: 홍길동 (20231234)", value="홍길동 (20231234)")

    generate_rubric_btn = st.button("✅ 1단계: 채점 기준 생성")
    single_random_grade_btn = st.button("✅ 2단계: 무작위 학생 채점")
    update_rubric_btn = st.button("✅ 3단계: 교수자 피드백 반영")

# 예시 기반 정규표현식 생성
custom_pattern = generate_regex_from_example(format_example)
if format_example and not custom_pattern:
    st.warning("❗ 예시에서 이름(한글)과 학번(8자리)을 인식하지 못했습니다. 다시 입력해주세요.")
elif custom_pattern:
    st.code(custom_pattern, language="regex")

# 1단계: 채점 기준 생성
if problem_pdf:
    problem_text = extract_text_from_pdf(problem_pdf)
    rubric_key = f"rubric_{problem_pdf.name}"

    st.subheader("📜 문제 내용")
    st.write(problem_text)

    if generate_rubric_btn:
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

        st.subheader("📊 채점 기준")
        st.write(st.session_state[rubric_key])

# 2단계: 무작위 학생 채점
if answers_pdfs and single_random_grade_btn:
    if problem_pdf is None:
        st.warning("문제 PDF를 먼저 업로드하세요.")
    elif not custom_pattern:
        st.warning("학생 정보 예시를 입력해 정규표현식을 생성해주세요.")
    else:
        rubric_key = f"rubric_{problem_pdf.name}"
        if rubric_key not in st.session_state:
            st.warning("채점 기준을 먼저 생성하세요.")
        else:
            all_answers = []
            student_info_list = []
            for pdf_file in answers_pdfs:
                pdf_text = extract_text_from_pdf(pdf_file)
                answers, info_list = extract_answers_and_info(pdf_text, custom_pattern)
                all_answers.extend(answers)
                student_info_list.extend(info_list)

            if not all_answers:
                st.warning("학생 답안을 찾을 수 없습니다. 예시 형식을 다시 확인해주세요.")
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

# 3단계: 교수자 피드백 반영
if update_rubric_btn:
    if problem_pdf is None:
        st.warning("문제 PDF가 필요합니다.")
    else:
        rubric_key = f"rubric_{problem_pdf.name}"
        if rubric_key not in st.session_state:
            st.warning("채점 기준을 먼저 생성해주세요.")
        else:
            st.subheader("📝 교수자 피드백 입력")
            feedback_text = st.text_area("피드백을 입력하세요 (예: 이 항목을 더 강조해주세요)")

            if feedback_text.strip():
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
            else:
                st.warning("피드백을 입력하세요.")
