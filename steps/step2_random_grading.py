import streamlit as st
import random
import io
import re
import tempfile

from utils.pdf_utils import extract_text_from_pdf
from utils.text_cleaning import clean_text_postprocess
from utils.file_info import extract_info_from_filename
from config.llm_config import get_llm

import tempfile
import uuid

def save_uploaded_file(uploaded_file):
    """
    업로드된 파일을 안전한 임시경로에 저장하고 경로 반환
    """
    # 한글 이름 무시하고 UUID로 대체
    unique_name = f"{uuid.uuid4().hex}.pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix="upload_", mode='wb') as tmp_file:
        tmp_file.write(uploaded_file.read())
        return tmp_file.name, unique_name  # 경로와 강제 파일명


# ✅ GPT 직접 호출 함수
def grade_answer(prompt: str) -> str:
    try:
        llm = get_llm()
        response = llm.invoke(prompt)
        content = getattr(response, "content", None)
        if not content:
            return "[오류] GPT 응답이 비어 있습니다."
        return str(content)
    except Exception as e:
        return f"[오류] GPT 호출 실패: {str(e)}"


# ✅ 학생 PDF 처리 함수 (한글 파일명 포함 처리)
def process_student_pdfs(pdf_files):
    answers = []
    info = []

    for file in pdf_files:
        try:
            # 🔧 한글 파일명을 안전하게 저장
            uploaded_path, safe_name = save_uploaded_file(file)

            # 이름/학번 추출 (원래 file.name 대신 safe_name 사용)
            name, sid = extract_info_from_filename(safe_name)

            # 텍스트 추출 (한글 경로 문제 없음)
            text = extract_text_from_pdf(uploaded_path)
            text = clean_text_postprocess(text)

            if len(text.strip()) > 20:
                answers.append(text)
                info.append({'name': name, 'id': sid, 'text': text})
            else:
                st.warning(f"{safe_name}에서 충분한 텍스트를 추출하지 못했습니다.")
        except Exception as e:
            st.error(f"{file.name} 처리 중 오류 발생: {str(e)}")
            return [], []

    st.session_state.student_answers_data = info
    return answers, info



# ✅ STEP 2 실행 함수
def run_step2():
    st.subheader("📄 STEP 2: 학생 답안 업로드 및 무작위 채점")
    if st.session_state.get("problem_text") and st.session_state.get("problem_filename"):
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        rubric = st.session_state.generated_rubrics.get(rubric_key)

        if rubric:
            st.markdown("#### 📊 채점 기준")
            st.markdown(rubric)

        student_pdfs = st.file_uploader("📥 학생 답안 PDF 업로드 (여러 개)", type="pdf", accept_multiple_files=True)

        if student_pdfs and st.button("🎯 무작위 채점 실행"):
            # 세션 변수 초기화
            for key in ["last_grading_result", "last_selected_student", "student_answers_data"]:
                st.session_state.pop(key, None)

            all_answers, info_list = process_student_pdfs(student_pdfs)
            if not all_answers:
                st.warning("유효한 답안을 찾을 수 없습니다.")
                return

            idx = random.randint(0, len(all_answers) - 1)
            selected_student = info_list[idx]
            answer = all_answers[idx]

            if not answer.strip():
                st.error("❌ 학생 답안이 비어 있어 GPT에 채점을 요청할 수 없습니다.")
                return

            prompt = f"""당신은 학생의 서술형 시험 답안을 채점하는 GPT입니다.

아래는 교수자가 만든 채점 기준입니다:
{rubric}

다음은 학생 답안입니다:
{answer}

📌 채점 규칙:
1. 마크다운 표로 채점하세요.
2. 헤더는 | 채점 항목 | 배점 | 세부 기준 |, 아래는 |---|---|---| 형식
3. 각 행은 |로 시작하고 끝나야 하며, 열은 3개
4. 영어는 사용하지 말고 한글로만 작성
5. 맨 아래에 **배점 총합: XX점** 문구 작성
"""

            st.write("📏 Prompt 길이:", len(prompt))
            with st.expander("📄 GPT 프롬프트 확인"):
                st.code(prompt)

            if len(prompt) > 12000:
                st.error("❌ prompt가 너무 깁니다.")
                return

            with st.spinner("GPT가 채점 중입니다..."):
                result = grade_answer(prompt)

            if not isinstance(result, str) or result.startswith("[오류]"):
                st.error(f"GPT 응답 오류:\n{result}")
                return

            st.session_state.last_grading_result = result
            st.session_state.last_selected_student = selected_student
            st.success("✅ 채점 완료")

    else:
        st.warning("STEP 1에서 문제를 먼저 업로드해야 합니다.")

    # 결과 표시
    if st.session_state.get("last_grading_result"):
        stu = st.session_state.last_selected_student
        st.markdown(f"### 📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)
