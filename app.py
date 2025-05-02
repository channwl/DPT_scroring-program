# app.py
# Streamlit 메인 실행 진입점. 각 STEP 모듈을 불러와 인터랙티브 채점 플로우를 제어합니다.

import streamlit as st
from steps.step1_generate_rubric import run_step1
from steps.step2_random_grading import run_step2
from steps.step3_feedback_update import run_step3
from steps.step4_batch_grading import run_step4
from langchain.memory import ConversationSummaryMemory
from config.llm_config import get_llm

# 페이지 설정
st.set_page_config(page_title="AI 채점 시스템", layout="wide")
st.title("🎓 AI 기반 자동 채점 시스템 - by DPT")

# LLM 및 메모리 초기화
llm = get_llm()

def initialize_session_state():
    defaults = {
        "rubric_memory": ConversationSummaryMemory(llm=llm, memory_key="history", return_messages=True),
        "step": 1,
        "generated_rubrics": {},
        "problem_text": None,
        "problem_filename": None,
        "student_answers_data": [],
        "feedback_text": "",
        "modified_rubrics": {},
        "last_grading_result": None,
        "last_selected_student": None,
        "all_grading_results": [],
        "highlighted_results": []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# 사이드바 구성
with st.sidebar:
    st.markdown("## 🧭 채점 흐름")
    if st.button("1️⃣ 문제 업로드 및 채점 기준 생성"):
        st.session_state.step = 1
    if st.button("2️⃣ 학생 답안 업로드 및 무작위 채점"):
        st.session_state.step = 2
    if st.button("3️⃣ 교수자 피드백 입력"):
        st.session_state.step = 3
    if st.button("4️⃣ 전체 학생 일괄 채점"):
        st.session_state.step = 4

    st.markdown("### 📝 교수자 피드백")
    feedback = st.text_area("채점 기준 수정 피드백", value=st.session_state.feedback_text, key="sidebar_feedback")
    st.session_state.feedback_text = feedback

    with st.expander("ℹ️ 사용법 안내 보기"):
        st.markdown("""
**STEP 1:** 문제 업로드 → 채점 기준 생성  
**STEP 2:** 학생 답안 업로드 → 무작위 채점  
**STEP 3:** 교수자 피드백 → 기준 수정  
**STEP 4:** 전체 학생 자동 채점 + 하이라이팅
""")

# STEP 실행 흐름
if st.session_state.step == 1:
    run_step1()
elif st.session_state.step == 2:
    run_step2()
elif st.session_state.step == 3:
    run_step3()
elif st.session_state.step == 4:
    run_step4()
