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
        # 임시 파일로 저장 후 처리
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(file.read())
            tmp_path = tmp_file.name
            
        # 파일 경로로 텍스트 추출
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

    if 'problem_text' in st.session_state and 'problem_filename' in st.session_state:
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
                    with st.spinner("학생 답안을 처리 중입니다..."):
                        all_answers, info_list = process_student_pdfs(student_pdfs)

                    if not all_answers:
                        st.warning("답안을 찾을 수 없습니다.")
                        return

                    # 무작위 선택
                    idx = random.randint(0, len(all_answers) - 1)
                    selected_student = info_list[idx]
                    answer = all_answers[idx]

                    # 답안 길이 제한 (예방적 차단)
                    MAX_LENGTH = 4000
                    trimmed_answer = answer[:MAX_LENGTH]

                    prompt = f"""당신은 대학 시험을 채점하는 GPT 채점자입니다.

당신의 역할은, 사람이 작성한 "채점 기준"에 **엄격하게 따라** 학생의 답안을 채점하는 것입니다.  
**창의적인 해석이나 기준 변경 없이**, 각 항목에 대해 **정확한 근거와 함께 점수를 부여**해야 합니다.

---

채점 기준:
{rubric}

학생 답안:
{trimmed_answer}

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
"""

                    st.write("📏 프롬프트 길이:", len(prompt))
                    st.code(prompt[:2000] + "\n\n... (이후 생략)", language="markdown")

                    with st.spinner("GPT가 채점 중입니다..."):
                        try:
                            result = grade_answer(prompt)
                            st.session_state.last_grading_result = result
                            st.session_state.last_selected_student = selected_student
                            st.success("✅ 채점 완료")
                        except Exception as e:
                            st.error("❌ GPT 채점 중 오류 발생")
                            st.exception(e)

    else:
        st.warning("먼저 STEP 1에서 문제를 업로드해주세요.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1

    # 결과 표시
    if 'last_grading_result' in st.session_state and 'last_selected_student' in st.session_state:
        stu = st.session_state.last_selected_student
        st.write("🧪 last_selected_student:", st.session_state.get("last_selected_student"))
        st.write("🧪 타입:", type(st.session_state.get("last_selected_student")))
        st.subheader(f"📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)
