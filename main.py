import streamlit as st
import PyPDF2
import random
import re
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationSummaryMemory

# OpenAI GPT-4o 모델을 LangChain에 연결
# temperature=0은 가장 일관성 있는 응답을 얻기 위함
llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

# LangChain의 메모리 생성: 이전 대화 요약을 저장함
# 채점 기준 생성과 수정에 사용되는 대화 기록을 기억함
if "rubric_memory" not in st.session_state:
    st.session_state.rubric_memory = ConversationSummaryMemory(
        llm=llm,
        memory_key="chat_history",
        return_messages=True
    )

# GPT 모델과 메모리를 연결한 대화 체인 생성
rubric_conversation = ConversationChain(
    llm=llm,
    memory=st.session_state.rubric_memory,
    verbose=False
)

# PDF 파일에서 텍스트를 추출하는 함수
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    return text

# 학생 이름, 학번, 답안을 추출하는 함수 (정규표현식 사용)
def extract_answers_and_info(pdf_text):
    pattern = re.compile(
        r"([가-힣]{2,10})\s\(?([0-9]{8})\)?\s(.?)(?=(?:[가-힣]{2,10}\s\(?[0-9]{8}\)?|$))",
        re.DOTALL
    )
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

# Streamlit 앱 시작
st.title("🎓 AI 교수자 채점 시스템")

# 사이드바 UI: 문제/답안 업로드 및 버튼
with st.sidebar:
    st.header("📂 STEP 1: 문제 파일 업로드")
    problem_pdf = st.file_uploader("문제 PDF 업로드", type="pdf")

    st.header("📂 STEP 2: 학생 답안 PDF 업로드")
    answers_pdfs = st.file_uploader("답안 PDF 업로드 (복수 가능)", type="pdf", accept_multiple_files=True)

    generate_rubric_btn = st.button("✅ 1단계: 채점 기준 생성")
    single_random_grade_btn = st.button("✅ 2단계: 무작위 학생 채점")
    update_rubric_btn = st.button("✅ 3단계: 교수자 피드백 반영")

# 문제 PDF가 업로드되었을 때
if problem_pdf:
    problem_text = extract_text_from_pdf(problem_pdf)
    rubric_key = f"rubric_{problem_pdf.name}"  # 문제 파일 이름으로 고유 키 생성

    st.subheader("📜 문제 내용")
    st.write(problem_text)

    # 채점 기준 생성
    if generate_rubric_btn:
        if rubric_key not in st.session_state:
            prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요:
문제: {problem_text}
- 항목별로 '채점 항목 | 배점 | 세부 기준' 형태로 작성해 주세요.
- 표 아래에 배점 합계도 적어주세요."""
            with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                rubric = rubric_conversation.predict(input=prompt)
                st.session_state[rubric_key] = rubric
            st.success("✅ 채점 기준 생성 완료")
        else:
            st.info("기존 채점 기준이 이미 존재합니다.")
        st.subheader("📊 채점 기준")
        st.write(st.session_state[rubric_key])

# 무작위 학생 채점 실행
if answers_pdfs and single_random_grade_btn:
    if problem_pdf is None:
        st.warning("문제 PDF를 먼저 업로드하세요.")
    else:
        rubric_key = f"rubric_{problem_pdf.name}"
        if rubric_key not in st.session_state:
            st.warning("채점 기준을 먼저 생성하세요.")
        else:
            all_answers = []
            student_info_list = []
            for pdf_file in answers_pdfs:
                pdf_text = extract_text_from_pdf(pdf_file)
                answers, info_list = extract_answers_and_info(pdf_text)
                all_answers.extend(answers)
                student_info_list.extend(info_list)

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
                    grading_result = rubric_conversation.predict(input=prompt)

                st.success("✅ 채점 완료")
                st.subheader("📋 GPT 채점 결과")
                st.write(grading_result)

# 교수자 피드백 입력 및 기준 수정
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
                    updated_rubric = rubric_conversation.predict(input=prompt)
                    st.session_state[rubric_key] = updated_rubric

                st.success("✅ 채점 기준 수정 완료")
                st.subheader("🆕 수정된 채점 기준")
                st.write(updated_rubric)
            else:
                st.warning("피드백을 입력하세요.")
