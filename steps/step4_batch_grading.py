# step4_batch_grading.py
# 이 파일은 STEP 4: 전체 학생 답안을 일괄 채점하고 결과를 정리하는 Streamlit UI 및 실행 로직입니다.

import streamlit as st
from chains.grading_chain import grade_answer
from utils.score_utils import extract_total_score, extract_evidence_sentences, extract_summary_feedback
from utils.text_cleaning import apply_indentation
import re
from steps.step2_random_grading import process_student_pdfs

def extract_total_score(text: str) -> float:
    matches = re.findall(r"총점[:：]?\s*(\d+(?:\.\d+)?)", text)
    if matches:
        return float(matches[-1])
    return None
    
def run_step4():
    st.subheader("📄 STEP 4: 전체 학생 답안 일괄 채점")

    rubric_key = f"rubric_{st.session_state.problem_filename}"
    rubric_text = (
        st.session_state.modified_rubrics.get(rubric_key)
        or st.session_state.generated_rubrics.get(rubric_key)
    )

    if not rubric_text:
        st.warning("채점 기준이 없습니다. STEP 1을 먼저 진행하세요.")
        return

    st.subheader("📊 채점 기준")
    st.markdown(rubric_text)

    # STEP2에서 저장한 전체 PDF 리스트가 있어야 진행
    if not st.session_state.get("all_student_pdfs"):
        st.warning("학생 답안이 없습니다. STEP 2를 먼저 진행하세요.")
        return

    if st.button("📝 전체 학생 채점 실행"):
        # 전체 PDF를 다시 처리해서 answers, info 얻기 (세션에 저장됨)
        info = st.session_state.get("student_answers_data", [])
        if not info:
            st.error("STEP 2에서 학생 답안 텍스트를 먼저 저장해야 합니다.")
            return
            
        st.session_state.highlighted_results = []
        progress_bar = st.progress(0)
        total_students = len(info)

        with st.spinner("GPT가 채점 중입니다..."):
            for i, student in enumerate(info):
                name, sid, answer = student["name"], student["id"], student["text"]

                prompt = f"""
당신은 대학 시험을 채점하는 GPT 채점자입니다.

당신의 역할은, 사람이 작성한 "채점 기준"에 **엄격하게 따라** 학생의 답안을 채점하는 것입니다.  
**창의적인 해석이나 기준 변경 없이**, 각 항목에 대해 **정확한 근거와 함께 점수를 부여**해야 합니다.

---

📌 채점 기준:
{rubric_text}

📌 학생({name}, {sid})의 답안:
{answer}

---

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
5. 명확하게 채점 기준에 따른 내용이 모두 구체적으로 포함된 경우에만 **만점(1~2점)**을 부여하세요.
6. 단어만 언급하거나 의미가 불명확한 경우는 **0점 또는 부분점수(0.5점 이하)**를 부여하세요.
7. 불완전하거나 비논리적인 설명은 반드시 감점 대상입니다.
8. 예시를 제공하라는 문제에서는, 예시가 구체적으로 제공되지 않으면 감점해주세요. 또한 각 내용의 설명이 구체적이지 않은 경우에도 감점해주세요.
9. 전체 점수는 문제별 배점을 절대 초과하면 안 됩니다.
10. 표 아래에 다음 문장을 작성하세요:
   **총점: XX점**

📌 근거 문장 출력
그리고 문제별로 아래 형식으로 **근거 문장(Evidence)**을 출력하세요:
- 항목별 최대 3개, 반드시 학생 답안에서 "직접 발췌"한 문장으로, 쌍따옴표로 표시
- 예시:
**근거 문장**
- 핵심 개념 설명: "텍스트 전처리는 토크나이징에서 시작한다", "불용어 제거가 필요하다"
- 논리 전개: "이어서 모델에 입력하기 위한 절차를 구성했다"

8. 그리고 채점 결과를 문제별로 묶어서 보여주세요.
9. 채점 결과 점수는 전체 채점 점수여야 합니다.
"""
                grading_result = grade_answer(prompt)
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
                tab1, tab2 = st.tabs(["📑 채점 결과", "📘 원본 답안"])

                with tab1:
                    st.markdown("**GPT 채점 결과**")
                    st.markdown(result["grading_result"])

                with tab2:
                    st.markdown("**📄 문단 구조로 정리된 답안**")
                    formatted = apply_indentation(result["original_text"])
                    st.markdown(formatted, unsafe_allow_html=True)
