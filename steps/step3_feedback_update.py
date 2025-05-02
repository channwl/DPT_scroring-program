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

📌 작성 규칙 (아래 형식을 반드시 그대로 지킬 것!)
1. **반드시 마크다운 표**로 작성해주세요. 정확히 아래 구조를 따라야 합니다.
2. **헤더는 `| 채점 항목 | 배점 | 세부 기준 |` 이고**, 그 아래 구분선은 `|---|---|---|`로 시작해야 합니다.
3. **각 행은 반드시 |로 시작하고 |로 끝나야 하며**, 총 3개의 열을 포함해야 합니다.
4. 각 항목의 세부 기준은 **구체적으로**, **한글로만** 작성해주세요. 영어는 절대 사용하지 마세요.
5. 표 아래에 반드시 "**배점 총합: XX점**"을 작성하세요.
6. GPT가 판단하지 말고 반드시 **전체 항목을 포함한 수정표**를 출력하세요.
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

