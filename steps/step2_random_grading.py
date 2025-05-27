import streamlit as st
import io
import re
import tempfile
import os
import uuid
import urllib.parse

from utils.pdf_utils import extract_text_from_pdf
from utils.text_cleaning import clean_text_postprocess
from utils.file_info import extract_info_from_filename, sanitize_filename
from config.llm_config import get_llm


def save_uploaded_file(uploaded_file):
    """
    업로드된 파일을 안전한 임시경로에 저장하고 경로 반환
    """
    try:
        # 원본 파일명 디코딩
        original_filename = urllib.parse.unquote(uploaded_file.name)
        
        # 파일 식별을 위해 원본 파일명은 유지하지만 안전하게 처리
        safe_filename = sanitize_filename(original_filename)
        
        # 임시 파일 경로에는 UUID를 사용하여 충돌 방지
        temp_filename = f"upload_{uuid.uuid4().hex}.pdf"
        
        # 임시 디렉토리에 파일 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", mode='wb') as tmp_file:
            # getbuffer() 사용하여 파일 읽기
            uploaded_file.seek(0)  # 파일 포인터 초기화
            tmp_file.write(uploaded_file.getbuffer())
            return tmp_file.name, safe_filename  # 경로와 안전한 파일명 반환
    except Exception as e:
        st.error(f"파일 저장 중 오류 발생: {str(e)}")
        # 오류 발생 시 기본값으로 대체
        unique_name = f"{uuid.uuid4().hex}.pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", mode='wb') as tmp_file:
            uploaded_file.seek(0)  # 파일 포인터 초기화
            tmp_file.write(uploaded_file.getbuffer())
            return tmp_file.name, unique_name


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
def process_student_pdfs(pdf_files, save_session:bool = True):
    answers, info = [], []

    for file in pdf_files:
        try:
            # 🔧 한글 파일명을 안전하게 저장
            uploaded_path, safe_name = save_uploaded_file(file)
            
            # 원본 파일명에서 이름/학번 추출
            name, sid = extract_info_from_filename(file.name)
            
            # 텍스트 추출 (업로드된 파일 경로 사용)
            text = extract_text_from_pdf(uploaded_path)
            text = clean_text_postprocess(text)
            
            # 임시 파일 삭제
            try:
                os.unlink(uploaded_path)
            except:
                pass  # 삭제 실패해도 계속 진행

            if len(text.strip()) > 20:
                answers.append(text)
                info.append({'name': name, 'id': sid, 'text': text, 'filename': safe_name})
            else:
                st.warning(f"{safe_name}에서 충분한 텍스트를 추출하지 못했습니다.")
        except Exception as e:
            st.error(f"{file.name} 처리 중 오류 발생: {str(e)}")
            st.exception(e)
            continue  # 오류가 발생해도 다른 파일 계속 처리

    if not answers:
        return [], []

    if save_session:  
        st.session_state.student_answers_data = info
    return answers, info

def run_step2():
    st.subheader("📄 STEP 2: 학생 답안 업로드 및 첫 번째 답안 채점")

    # STEP 1에서 생성된 문제와 파일명이 있어야 진행 가능
    if st.session_state.get("problem_text") and st.session_state.get("problem_filename"):
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        rubric = st.session_state.generated_rubrics.get(rubric_key)

        if rubric:
            st.markdown("#### 📊 채점 기준")
            st.markdown(rubric)

        # 학생 PDF 업로드 UI
        student_pdfs = st.file_uploader(
        "📥 채점 기준 테스트 파일 업로드",
        type="pdf",
        accept_multiple_files=True,
        key="student_pdfs_upload"
        )
        
        if student_pdfs:
            st.session_state.all_student_pdfs = student_pdfs

            with st.spinner("📄 PDF에서 텍스트 추출 중..."):
                answers, info = process_student_pdfs(student_pdfs, save_session=True)

            if len(info) == 0:
                st.error("❌ 텍스트를 추출하지 못했습니다. 스캔본일 수 있습니다.")
            else:
                st.success(f"✅ {len(info)}개 PDF에서 텍스트 저장 완료")
                st.write("🔎 저장된 학생 목록:")
                for i in info:
                    st.markdown(f"- **{i['name']} ({i['id']})** → `{i['filename']}`")

        # 2) '무작위 채점' 버튼을 누르면 첫 번째 PDF만 처리
        if st.session_state.get("all_student_pdfs") and st.button("📌 무작위 채점"):
            pdfs_to_grade = st.session_state.all_student_pdfs
            first_pdf = pdfs_to_grade[0]
            # save_session=False 로 전체 세션 데이터 덮어쓰지 않기
            answers, info = process_student_pdfs([first_pdf], save_session=False)
            if not answers:
                st.warning("처리할 학생 답안이 없습니다.")
                return

            # ▶ 첫 번째 학생만 임시 채점
            first_answer = answers[0]
            first_info   = info[0]
            name, sid    = first_info['name'], first_info['id']

            # 6) GPT 채점 프롬프트 생성
            prompt = f"""당신은 대학 시험을 채점하는 GPT 채점자입니다.

당신의 역할은, 사람이 작성한 "채점 기준"에 **엄격하게 따라** 학생의 답안을 채점하는 것입니다.  
**창의적인 해석이나 기준 변경 없이**, 각 항목에 대해 **정확한 근거와 함께 점수를 부여**해야 합니다.

아래는 교수자가 만든 채점 기준입니다:
{rubric}

다음은 학생 답안입니다:
학생({name}, {sid})의 답안입니다:
{first_answer}

📌 채점 출력 형식
다음 형식의 마크다운 표를 작성하세요:

| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|---|---|---|---|
| 예: 핵심 개념 설명 | 3점 | 2점 | "핵심 개념을 언급했지만 정의가 불명확함" |
| ... | ... | ... | ... |
문제별로 구분하여 표를 나타내주세요.

📌 채점 지침
1. 반드시 채점 기준에 명시된 항목명과 배점을 그대로 사용하세요. 항목을 임의로 바꾸거나 재구성하지 마세요.
2. 각 항목의 "부여 점수"는 해당 항목 배점 이내에서 학생 답안을 기준으로 정확히 결정하세요.
3. "평가 근거"는 반드시 학생 답안에서 확인 가능한 내용으로 작성하세요. 추상적 표현(예: '잘함', '훌륭함')은 금지입니다.
4. 모든 출력은 **한글로만** 작성하고, 영어는 절대 사용하지 마세요.
5. 명확하게 채점 기준에 따른 내용이 모두 포함된 경우에만 **만점(1~2점)**을 부여하세요.
6. 단어만 언급하거나 의미가 불명확한 경우는 **0점 또는 부분점수(0.5점 이하)**를 부여하세요.
7. 불완전하거나 비논리적인 설명은 반드시 감점 대상입니다.
8. 각 항목에 대해 "구체적인 내용 확인"이 없으면 점수를 주지 마세요.
9. 전체 점수는 문제별 배점을 절대 초과하면 안 됩니다.
10. 표 아래에 다음 문장을 작성하세요:
   **총점: XX점**

"""
            # 7) GPT 호출
            with st.spinner("프로그램이 채점 중입니다..."):
                result = grade_answer(prompt)

            # 8) 에러 처리
            if not isinstance(result, str) or result.startswith("[오류]"):
                st.error(f"GPT 응답 오류:\n{result}")
                return

            # 9) 세션에 결과 저장 및 표시 준비
            st.session_state.last_grading_result = result
            st.session_state.last_selected_student = {"name": name, "id": sid}
            st.success("✅ 채점 완료")

    else:
        st.warning("STEP 1에서 문제를 먼저 업로드해야 합니다.")

    # 10) 이전 채점 결과가 있으면 화면에 출력
    if st.session_state.get("last_grading_result"):
        stu = st.session_state.last_selected_student
        st.markdown(f"### 📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)
