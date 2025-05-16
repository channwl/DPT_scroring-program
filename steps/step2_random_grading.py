# step2_random_grading.py
# 이 파일은 STEP 2: 학생 답안 PDF 업로드 및 무작위 채점을 실행하는 Streamlit UI 로직입니다.

import streamlit as st
import random
from utils.pdf_utils import extract_text_from_pdf
from utils.text_cleaning import clean_text_postprocess
from utils.file_info import extract_info_from_filename
from chains.grading_chain import grade_answer


def process_student_pdfs(pdf_files):
    answers, info = [], []
    for file in pdf_files:
        file.seek(0)
        file_bytes = file.read()
        text = extract_text_from_pdf(file_bytes)
        text = clean_text_postprocess(text)
        name, sid = extract_info_from_filename(file.name)
        if len(text.strip()) > 20:
            answers.append(text)
            info.append({'name': name, 'id': sid, 'text': text})
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
                    if not all_answers:
                        st.warning("답안을 찾을 수 없습니다.")
                        return
                    idx = random.randint(0, len(all_answers) - 1)
                    selected_student = info_list[idx]
                    answer = all_answers[idx]

                    prompt = f"""다음은 채점 기준입니다:
{rubric}

그리고 아래는 학생 답안입니다:
{answer}

📌 작성 규칙 (아래 형식을 반드시 그대로 지킬 것!)
1. **반드시 마크다운 표**로 작성해주세요. 정확히 아래 구조를 따라야 합니다.
2. **헤더는 `| 채점 항목 | 배점 | 세부 기준 |` 이고**, 그 아래 구분선은 `|---|---|---|`로 시작해야 합니다.
3. **각 행은 반드시 |로 시작하고 |로 끝나야 하며**, 총 3개의 열을 포함해야 합니다.
4. 각 항목의 세부 기준은 **구체적으로**, **한글로만** 작성해주세요. 영어는 절대 사용하지 마세요.
5. 표 아래에 반드시 "**배점 총합: XX점**"을 작성하세요.
"""

                    st.text("📦 Prompt 길이 확인")
                    st.write(f"Rubric 길이: {len(rubric)}자")
                    st.write(f"Answer 길이: {len(answer)}자")
                    st.write(f"Prompt 전체 길이: {len(prompt)}자")

                    st.subheader("🔍 생성된 Prompt 일부 미리보기")
                    st.code(prompt[:700], language="markdown")


                    with st.spinner("GPT가 채점 중입니다..."):
                        result = grade_answer(prompt)
                        st.session_state.last_grading_result = result
                        st.session_state.last_selected_student = selected_student
                        st.success("✅ 채점 완료")

    else:
        st.warning("먼저 STEP 1에서 문제를 업로드해주세요.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1

    if st.session_state.last_grading_result and st.session_state.last_selected_student:
        stu = st.session_state.last_selected_student
        st.subheader(f"📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)
