# ✅ 최종 통합 코드: Explainable Grading System (Step 4 포함)

import streamlit as st
import PyPDF2
import random
import re
import io
import os
import json
import matplotlib.pyplot as plt
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate

# -------------------- 초기 설정 --------------------
st.set_page_config(page_title="설명 가능한 채점 시스템", layout="wide")
st.title("🎓 Explainable AI 채점 시스템")

llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

# 세션 초기화
def initialize():
    keys = {
        "step": 1,
        "rubric_memory": ConversationSummaryMemory(llm=llm, memory_key="history", return_messages=True),
        "problem_text": None,
        "problem_filename": None,
        "generated_rubrics": {},
        "student_answers_data": [],
        "feedback_text": "",
        "modified_rubrics": {},
        "highlighted_results": [],
        "all_grading_results": []
    }
    for k, v in keys.items():
        if k not in st.session_state:
            st.session_state[k] = v

initialize()

# -------------------- 유틸 함수 --------------------
def extract_text_from_pdf(pdf_data):
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
    return "".join([p.extract_text() or "" for p in reader.pages])

def extract_info_from_filename(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    sid_match = re.search(r'\d{6,10}', base)
    sid = sid_match.group() if sid_match else "UnknownID"
    name_candidates = [p for p in re.findall(r'[가-힣]{2,5}', base) if p not in sid]
    for name in name_candidates:
        if name not in {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}:
            return name, sid
    return "UnknownName", sid

def extract_total_score(grading_text):
    match = re.search(r'총점[:：]?\s*(\d+)\s*점', grading_text)
    return int(match.group(1)) if match else None

def apply_highlight(answer_text, items):
    colors = ["#FFF59D", "#81C784", "#64B5F6", "#F48FB1"]
    for idx, item in enumerate(items):
        phrase = item.get("근거문장")
        if phrase and phrase in answer_text:
            answer_text = answer_text.replace(
                phrase,
                f'<span style="background-color:{colors[idx % len(colors)]}; font-weight:bold;">{phrase}</span>'
            )
    return answer_text

# -------------------- 사이드바 --------------------
with st.sidebar:
    st.markdown("## 📘 채점 흐름")
    if st.button("1️⃣ 문제 업로드 및 채점 기준 생성"):
        st.session_state.step = 1
    if st.button("2️⃣ 학생 답안 업로드 및 무작위 채점"):
        st.session_state.step = 2
    if st.button("3️⃣ 교수자 피드백 입력"):
        st.session_state.step = 3
    if st.button("4️⃣ 전체 학생 일괄 채점 + 하이라이팅"):
        st.session_state.step = 4

    st.markdown("### ✏️ 교수자 피드백")
    st.session_state.feedback_text = st.text_area("채점 기준 수정 피드백", value=st.session_state.feedback_text)

    with st.expander("ℹ️ 사용법 안내 보기"):
        st.markdown("""
**STEP 1:** 문제 업로드 → 채점 기준 생성  
**STEP 2:** 학생 답안 업로드 → 무작위 채점  
**STEP 3:** 교수자 피드백 → 기준 수정  
**STEP 4:** 전체 학생 자동 채점 + 하이라이팅 + 점수 분포
""")

# -------------------- STEP 4: 전체 채점 및 하이라이팅 --------------------
if st.session_state.step == 4:
    if st.session_state.problem_text and st.session_state.problem_filename:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        rubric_text = st.session_state.generated_rubrics.get(rubric_key)

        if not rubric_text:
            st.warning("STEP 1에서 채점 기준을 먼저 생성해주세요.")
        elif not st.session_state.student_answers_data:
            st.warning("STEP 2에서 학생 답안을 먼저 업로드해주세요.")
        else:
            st.subheader("📊 채점 기준")
            st.markdown(rubric_text)

            if st.button("📥 전체 학생 채점 실행"):
                grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                st.session_state.highlighted_results.clear()
                with st.spinner("GPT가 전체 학생을 채점 중입니다..."):
                    for stu in st.session_state.student_answers_data:
                        name, sid, answer = stu["name"], stu["id"], stu["text"]
                        prompt = f"""
다음은 채점 기준입니다:
{rubric_text}

아래는 학생 답안입니다:
{answer}

다음 JSON 포맷으로 채점 결과를 출력하세요:
```json
{{
  "total_score": 정수,
  "feedback": "총평",
  "items": [
    {{ "항목": "항목명", "배점": 숫자, "점수": 숫자, "평가": "내용", "근거문장": "답안 중 일부 문장" }}
  ]
}}
```
                        """
                        result = grading_chain.invoke({"input": prompt})
                        try:
                            data = json.loads(result["text"])
                            highlighted = apply_highlight(answer, data.get("items", []))
                            st.session_state.highlighted_results.append({
                                "name": name,
                                "id": sid,
                                "score": data.get("total_score"),
                                "feedback": data.get("feedback"),
                                "highlighted_text": highlighted,
                                "items": data.get("items")
                            })
                        except Exception as e:
                            st.warning(f"JSON 파싱 실패: {e}")
                st.success("✅ 전체 학생 채점 완료")

            # 결과 및 분포 표시
            if st.session_state.highlighted_results:
                st.subheader("📋 전체 학생 채점 결과")
                scores = []
                for r in st.session_state.highlighted_results:
                    st.markdown(f"### ✍️ {r['name']} ({r['id']}) - 총점: {r['score']}점")
                    st.markdown(f"🗣️ GPT 피드백: {r['feedback']}")
                    st.markdown("**🧾 학생 답안 (하이라이팅 표시됨):**", unsafe_allow_html=True)
                    st.markdown(r["highlighted_text"], unsafe_allow_html=True)
                    st.markdown("---")
                    if r["score"]:
                        scores.append(r["score"])

                if scores:
                    st.subheader("📊 점수 분포")
                    fig, ax = plt.subplots()
                    ax.hist(scores, bins=range(min(scores), max(scores)+2), edgecolor='black', align='left')
                    ax.set_xlabel("점수")
                    ax.set_ylabel("학생 수")
                    ax.set_title("GPT 채점 점수 분포")
                    st.pyplot(fig)
    else:
        st.warning("STEP 1에서 문제 업로드가 필요합니다.")
