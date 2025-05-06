# step3_feedback_update.py
# 이 파일은 STEP 3: 교수자의 피드백을 입력받아 채점 기준을 수정하는 기능을 제공합니다.

import streamlit as st
from chains.grading_chain import grade_answer


def run_step3():
    st.subheader("📝 STEP 3: 교수자 피드백 반영 및 채점 기준 수정")

    if st.session_state.problem_text and st.session_state.problem_filename:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        original_rubric = st.session_state.generated_rubrics.get(rubric_key)

        if not original_rubric:
            st.warning("채점 기준이 없습니다. STEP 1에서 먼저 생성해주세요.")
            if st.button("STEP 1로 이동"):
                st.session_state.step = 1
            return

        st.subheader("📊 원본 채점 기준")
        st.markdown(original_rubric)

        feedback = st.text_area("✏️ 교수자 피드백 입력", value=st.session_state.feedback_text)
        st.session_state.feedback_text = feedback

        if st.button("♻️ 피드백 반영"):
            if not feedback.strip():
                st.warning("피드백을 입력해주세요.")
            else:
                prompt = f"""기존 채점 기준:
                
{original_rubric}

피드백:
{feedback}

위 본문을 기반으로, 다음 지침에 따라 수정된 문제별 **채점 기준 마크다운 표**를 생성하세요.

📌 출력 지침:
1. 문제 번호와 배점을 그대로 반영하세요.
   - 예: 문제 1 (4점)
2. 각 문제는 아래 마크다운 표 형식을 따릅니다:
   | 채점 항목 | 배점 | 세부 기준 |
   |---|---|---|
   | ... | ... | ... |
3. 표 아래에는 다음 문장을 추가하세요:
   **배점 총합: X점**
4. 모든 문제 기준 작성 후 마지막에 아래와 같이 전체 점수를 작성하세요:
   → 전체 배점 총합: 30점
5. 모든 출력은 **한글로만** 작성하세요. 영어는 절대 사용하지 마세요.
6. 문제 수를 줄이거나 임의로 문제를 묶으면 안 됩니다.

이제 채점 기준을 생성하세요.
"""
                with st.spinner("GPT가 기준을 수정 중입니다..."):
                    updated = grade_answer(prompt)
                    st.session_state.modified_rubrics[rubric_key] = updated
                    st.success("✅ 채점 기준 수정 완료")

        if rubric_key in st.session_state.modified_rubrics:
            st.subheader("🆕 수정된 채점 기준")
            st.markdown(st.session_state.modified_rubrics[rubric_key])

    else:
        st.warning("먼저 STEP 1에서 문제를 업로드해주세요.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1

