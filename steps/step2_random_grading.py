import streamlit as st
import random
from utils.pdf_utils import extract_text_from_pdf
from utils.text_cleaning import clean_text_postprocess
from utils.file_info import extract_info_from_filename
from chains.grading_chain import grade_answer
from config.llm_config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser

# LangChain 기반 GPT 채점 기준 생성 체인 정의
llm = get_llm()

rubric_prompt_template = ChatPromptTemplate.from_messages([
    ("system", "당신은 대학 시험을 채점하는 전문가 GPT입니다."),
    ("user", "{input}")
])

rubric_chain = rubric_prompt_template | llm | StrOutputParser()


def process_student_pdfs(pdf_files):
    answers, info = [], []

    for file in pdf_files:
        try:
            file.seek(0)
            file_bytes = file.read()

            # 텍스트 추출
            text = extract_text_from_pdf(file_bytes)
            st.text(f"📄 PDF 텍스트 길이: {len(text)}")

            # 클린업
            text = clean_text_postprocess(text)
            st.text(f"🧹 정리된 텍스트 길이: {len(text)}")

            # 이름 및 학번 추출
            name, sid = extract_info_from_filename(file.name)
            st.text(f"👤 파일명에서 추출된 이름: {name}, 학번: {sid}")

            if len(text.strip()) > 20:
                answers.append(text)
                info.append({'name': name, 'id': sid, 'text': text})
            else:
                st.warning(f"⚠️ {file.name}에서 충분한 텍스트를 추출하지 못했습니다.")

        except Exception as e:
            st.error(f"❌ {file.name} 처리 중 오류 발생: {str(e)}")
            return [], []  # 오류 발생 시 즉시 중단

    st.session_state.student_answers_data = info
    return answers, info


def run_step2():
    st.subheader("📄 STEP 2: 학생 답안 업로드 및 무작위 채점")

    if st.session_state.problem_text and st.session_state.problem_filename:
        st.subheader("📃 문제 내용")
        st.write(st.session_state.problem_text)

        rubric_key = f"rubric_{st.session_state.problem_filename}"
        rubric = st.session_state.generated_rubrics.get(rubric_key)
        if rubric:
            st.subheader("📊 채점 기준")
            st.markdown(rubric)

        student_pdfs = st.file_uploader("📥 학생 답안 PDF 업로드 (여러 개)", type="pdf", accept_multiple_files=True)

        if student_pdfs:
            if not rubric:
                st.warning("채점 기준이 없습니다. STEP 1에서 먼저 생성해주세요.")
            else:
                if st.button("🎯 무작위 채점 실행"):
                    all_answers, info_list = process_student_pdfs(student_pdfs)

                    if not all_answers or not info_list:
                        st.warning("❌ 업로드된 PDF에서 유효한 텍스트를 추출하지 못했습니다.")
                        return

                idx = random.randint(0, len(all_answers) - 1)
                selected_student = info_list[idx]
                answer = all_answers[idx]

                if not rubric or not answer or len(answer.strip()) < 30:
                    st.error("❌ rubric 또는 answer가 비어 있거나 너무 짧습니다.")
                    return

                prompt = f"""다음은 채점 기준입니다:
{rubric}

그리고 아래는 학생 답안입니다:
{answer}

📌 작성 규칙 (아래 형식을 반드시 그대로 지킬 것!)
1. **반드시 마크다운 표**로 작성해주세요. 정확히 아래 구조를 따라야 합니다.
2. **헤더는 | 채점 항목 | 배점 | 세부 기준 | 이고**, 그 아래 구분선은 |---|---|---|로 시작해야 합니다.
3. **각 행은 반드시 |로 시작하고 |로 끝나야 하며**, 총 3개의 열을 포함해야 합니다.
4. 각 항목의 세부 기준은 **구체적으로**, **한글로만** 작성해주세요. 영어는 절대 사용하지 마세요.
5. 표 아래에 반드시 "**배점 총합: XX점**"을 작성하세요.
"""

    if len(prompt) > 12000:
        st.error(f"❌ prompt가 너무 깁니다. 현재 길이: {len(prompt)}자")
        return

    try:
        with st.spinner("GPT가 채점 중입니다..."):
            result = grade_answer(prompt)

            if result.startswith("[오류]") or "Error" in result:
                st.error(f"❌ GPT 응답 오류: {result}")
                return

            st.session_state.last_grading_result = result
            st.session_state.last_selected_student = selected_student
            st.success("✅ 채점 완료")

    except Exception as e:
        st.error("❌ GPT 채점 중 예외 발생")
        st.exception(e)

    else:
        st.warning("먼저 STEP 1에서 문제를 업로드해주세요.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1

    if st.session_state.last_grading_result and st.session_state.last_selected_student:
        stu = st.session_state.last_selected_student
        st.subheader(f"📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)
