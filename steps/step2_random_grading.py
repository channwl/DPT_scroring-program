import streamlit as st
import random
import tempfile

from utils.pdf_utils import extract_text_from_pdf
from utils.text_cleaning import clean_text_postprocess
from utils.file_info import extract_info_from_filename
from chains.grading_chain import grade_answer

def process_student_pdfs(pdf_files):
    answers, info = [], []
    for file in pdf_files:
        # 임시파일에 저장 후 텍스트 추출
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file.read())
            tmp_path = tmp_file.name

        text = extract_text_from_pdf(tmp_path)
        text = clean_text_postprocess(text)
        name, sid = extract_info_from_filename(file.name)

        if len(text.strip()) > 20:
            answers.append(text)
            info.append({'name': name, 'id': sid, 'text': text})

    st.session_state.student_answers_data = info
    return answers, info

def run_step2():
    st.subheader("📄 STEP 2: 학생 답안 업로드 및 무작위 채점")

    # 디버깅용 텍스트 확인
    # 디버깅용 텍스트 확인
    if st.session_state.get("last_selected_student"):
        st.subheader("🪵 디버깅용: 텍스트 확인")

        if st.checkbox("📋 추출된 텍스트 보기 (디버깅용)", value=False):
            extracted_text = st.session_state["last_selected_student"]["text"]
            st.text_area("📄 추출된 텍스트", extracted_text, height=400)


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
                    
                    def generate_rubric(problem_text: str) -> str:
                    prompt = f"""당신은 대학 시험을 채점하는 GPT 채점자입니다.

당신의 역할은, 사람이 작성한 "채점 기준"에 **엄격하게 따라** 학생의 답안을 채점하는 것입니다.  
**창의적인 해석이나 기준 변경 없이**, 각 항목에 대해 **정확한 근거와 함께 점수를 부여**해야 합니다.

---

채점 기준:
{rubric}

학생 답안:
{answer}

---

채점 지침:

1. 반드시 채점 기준에 명시된 항목명과 배점을 그대로 사용하세요. 절대 항목을 바꾸거나 재구성하지 마세요.
2. 각 항목마다 다음과 같은 표 형식으로 작성하세요:

| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|---|---|---|---|
| 핵심 개념 설명 | 3점 | 2점 | "학생은 주요 개념을 언급했지만, 정의가 불명확함" |
| ... | ... | ... | ... |

3. "부여 점수"는 해당 항목의 배점 범위 내에서 실제 학생 답안의 충족도를 기준으로 결정하세요.
4. "평가 근거"는 반드시 학생 답안에서 근거를 발췌하여 한글로 설명하세요. 추상적인 표현(예: '좋다', '괜찮다')은 사용 금지입니다.
5. 모든 출력은 **한글로만 작성**하고, 영어는 절대 사용하지 마세요.
6. 표 아래에 "**총점: XX점**"을 반드시 작성하세요. 모든 부여 점수의 합계입니다.
7. 사진 파일이 있으면 OCR로 인식해주세요.
"""

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
