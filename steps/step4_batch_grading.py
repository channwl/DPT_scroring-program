# step4_batch_grading.py
# 이 파일은 STEP 4: 전체 학생 답안을 일괄 채점하고 결과를 정리하는 Streamlit UI 및 실행 로직입니다.

import streamlit as st
from chains.grading_chain import grade_answer
from utils.score_utils import extract_total_score, extract_evidence_sentences, extract_summary_feedback
from utils.text_cleaning import apply_indentation


def run_step4():
    st.subheader("📄 STEP 4: 전체 학생 답안 일괄 채점")

    rubric_key = f"rubric_{st.session_state.problem_filename}"
    rubric_text = st.session_state.modified_rubrics.get(rubric_key) or st.session_state.generated_rubrics.get(rubric_key)

    if not rubric_text:
        st.warning("채점 기준이 없습니다. STEP 1을 먼저 진행하세요.")
        return
    elif not st.session_state.student_answers_data:
        st.warning("학생 답안이 없습니다. STEP 2를 먼저 진행하세요.")
        return

    st.subheader("📊 채점 기준")
    st.markdown(rubric_text)

    if st.button("📝 전체 학생 채점 실행"):
        st.session_state.highlighted_results = []
        progress_bar = st.progress(0)
        total_students = len(st.session_state.student_answers_data)

        with st.spinner("GPT가 채점 중입니다..."):
            for i, student in enumerate(st.session_state.student_answers_data):
                name, sid, answer = student["name"], student["id"], student["text"]

                prompt = f"""
다음은 채점 기준입니다:
{rubric_text}

아래는 학생({name}, {sid})의 답안입니다:
{answer}

## ✍️ 실제 채점 결과를 아래 형식으로 작성하세요

1. 표 형식으로 작성해주세요 (정확히 '| 채점 항목 | 배점 | 세부 기준 |' 형식의 마크다운 표를 사용하세요)
2. 각 항목의 세부 기준은 구체적으로 작성해주세요
3. 표 아래에 **배점 총합**도 함께 작성해주세요
4. 반드시 마크다운 표 문법을 정확히 사용하십시오 (각 행 시작과 끝에 |, 헤더 행 아래에 |---|---|---| 형식의 구분선)
5. **근거 문장(Evidence)** 각 항목별 최대 3개, 반드시 학생 답안에서 "직접 발췌"한 문장을 쌍따옴표로 기재
6. **총점과 총평**: **총점: XX점**, **총평:** …
"""
                result = grade_answer(prompt)
                grading_result = result

                evidence_sentences = extract_evidence_sentences(grading_result)
                total_score = extract_total_score(grading_result)
                feedback = extract_summary_feedback(grading_result)

                st.session_state.highlighted_results.append({
                    "name": name,
                    "id": sid,
                    "score": total_score,
                    "feedback": feedback,
                    "grading_result": grading_result,
                    "original_text": answer,
                    "evidence_sentences": evidence_sentences
                })
                progress_bar.progress((i + 1) / total_students)

        st.success(f"✅ 전체 {total_students}명 학생 채점 완료!")

    if st.session_state.highlighted_results:
        sorted_results = sorted(
            st.session_state.highlighted_results,
            key=lambda x: x["score"] if x["score"] is not None else 0,
            reverse=True
        )

        st.subheader("📊 학생별 점수 요약")
        summary_data = [
            {"이름": r["name"], "학번": r["id"], "점수": r["score"] if r["score"] is not None else "N/A"}
            for r in sorted_results
        ]
        st.table(summary_data)

        st.subheader("📝 학생별 상세 답안 및 채점")
        for result in sorted_results:
            with st.expander(f"📄 {result['name']} ({result['id']}) - {result['score']}점"):
                tab1, tab2, tab3 = st.tabs(["🔍 채점 근거 문장", "📑 채점 결과", "📘 원본 답안"])

                with tab1:
                    st.markdown("**GPT가 선택한 평가 근거 문장입니다.**")
                    if result["evidence_sentences"]:
                        for i, sentence in enumerate(result["evidence_sentences"], 1):
                            st.markdown(f"- **{i}.** {sentence}")
                    else:
                        st.info("근거 문장이 없습니다.")

                with tab2:
                    st.markdown("**GPT 채점 결과**")
                    st.markdown(result["grading_result"])

                with tab3:
                    st.markdown("**📄 문단 구조로 정리된 답안**")
                    formatted = apply_indentation(result["original_text"])
                    st.markdown(formatted, unsafe_allow_html=True)
