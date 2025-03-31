import streamlit as st
import PyPDF2
import random
import re
import pandas as pd
import os
from datetime import datetime
from openai import OpenAI
from typing import List, Dict, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import LocalStateCheckpoint

# OpenAI 클라이언트 설정
client = OpenAI(api_key=st.secrets["openai"]["API_KEY"])

# PDF에서 텍스트 추출 함수
def extract_text_from_pdf(pdf_file):
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted
    return text

# 학생 답안 및 정보 추출 함수
def extract_answers_and_info(pdf_text):
    pattern = re.compile(r"([가-힣]{2,10})\s*\(?([0-9]{8})\)?\s*(.*?)(?=(?:[가-힣]{2,10}\s*\(?[0-9]{8}\)?|$))", re.DOTALL)
    matches = pattern.finditer(pdf_text)
    answers = []
    student_info = []
    for match in matches:
        name = match.group(1).strip()
        student_id = match.group(2).strip()
        answer_text = match.group(3).strip()
        if len(answer_text) > 20:
            answers.append(answer_text)
            student_info.append({'name': name, 'id': student_id})
    return answers, student_info

# 채점 그래프를 위한 상태 타입 정의
class GradingState(TypedDict):
    problem_text: str  # 문제 내용
    initial_rubric: str  # 초기 채점 기준
    refined_rubric: str  # 교수자 피드백 반영 채점 기준 
    student_answers: List[str]  # 학생 답안 목록
    student_info: List[Dict]  # 학생 정보 목록
    graded_results: List[Dict]  # 채점 결과 목록
    instructor_feedback: str  # 교수자 피드백
    current_student_index: int  # 현재 채점 중인 학생 인덱스
    status: str  # 현재 상태
    history: List[Dict]  # 처리 이력

# == LangGraph 노드 함수 (각 단계별 처리 로직) ==

# 1. 초기 채점 기준 생성
def generate_initial_rubric(state: GradingState) -> GradingState:
    prompt = f"""다음 문제에 대한 초기 채점 기준을 작성해 주세요.
문제: {state['problem_text']}
- 항목별로 '채점 항목 | 배점 | 세부 기준' 형태의 표로 작성해 주세요.
- 표 아래에 항목별 배점 합계도 표기해 주세요.
- 세부 기준은 상세하고 구체적으로 작성해 주세요."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    
    rubric = response.choices[0].message.content
    
    return {
        **state,
        "initial_rubric": rubric,
        "refined_rubric": rubric,  # 초기에는 refined_rubric도 initial_rubric과 동일
        "status": "initial_rubric_generated",
        "history": state["history"] + [{"action": "generate_initial_rubric", "timestamp": datetime.now().isoformat()}]
    }

# 2. 샘플 답안 채점
def grade_sample_answers(state: GradingState) -> GradingState:
    # 샘플로 사용할 답안 선택 (최대 3개)
    sample_count = min(3, len(state["student_answers"]))
    sample_indices = random.sample(range(len(state["student_answers"])), sample_count)
    
    sample_results = []
    for idx in sample_indices:
        student_answer = state["student_answers"][idx]
        student_info = state["student_info"][idx]
        
        # 채점 실행
        prompt = f"""다음은 교수자가 작성한 채점 기준입니다:
{state['initial_rubric']}

아래는 학생 답안입니다:
{student_answer}

각 항목별로 아래 형태의 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |

- 표 마지막에 GPT 추천 총점도 표로 작성해 주세요.
- 마지막에 간략한 피드백도 포함해 주세요.
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        
        grading_result = response.choices[0].message.content
        
        # 점수 추출 (정규식으로 총점 찾기)
        total_score_match = re.search(r"GPT 추천 총점.*?(\d+(\.\d+)?)/(\d+(\.\d+)?)", grading_result)
        score = "N/A"
        if total_score_match:
            score = total_score_match.group(1)
        
        sample_results.append({
            "student_name": student_info["name"],
            "student_id": student_info["id"],
            "answer": student_answer,
            "grading_result": grading_result,
            "score": score,
            "index": idx
        })
    
    return {
        **state,
        "sample_results": sample_results,
        "status": "sample_graded",
        "history": state["history"] + [{"action": "grade_sample_answers", "timestamp": datetime.now().isoformat()}]
    }

# 3. 교수자 피드백을 기반으로 채점 기준 수정
def refine_rubric(state: GradingState) -> GradingState:
    prompt = f"""다음은 초기 채점 기준과 이에 따른 샘플 채점 결과입니다:

[초기 채점 기준]
{state['initial_rubric']}

[샘플 채점 결과]
{', '.join([f"학생 {res['student_name']} 점수: {res['score']}" for res in state['sample_results']])}

교수자가 다음과 같은 피드백을 제공했습니다:
{state['instructor_feedback']}

위 피드백을 반영하여 채점 기준을 수정해 주세요. 수정된 채점 기준을 '채점 항목 | 배점 | 세부 기준' 형태의 표로 작성해 주세요.
표 아래에 항목별 배점 합계도 표기해 주세요."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500
    )
    
    refined_rubric = response.choices[0].message.content
    
    return {
        **state,
        "refined_rubric": refined_rubric,
        "status": "rubric_refined",
        "history": state["history"] + [{"action": "refine_rubric", "timestamp": datetime.now().isoformat()}]
    }

# 4. 모든 학생 답안 채점
def grade_all_answers(state: GradingState) -> GradingState:
    # 현재 인덱스의 학생 답안 채점
    current_idx = state["current_student_index"]
    
    # 모든 학생 채점이 완료된 경우
    if current_idx >= len(state["student_answers"]):
        return {
            **state,
            "status": "all_graded",
            "history": state["history"] + [{"action": "grade_all_answers_completed", "timestamp": datetime.now().isoformat()}]
        }
    
    student_answer = state["student_answers"][current_idx]
    student_info = state["student_info"][current_idx]
    
    # 최종 채점 기준으로 채점 실행
    prompt = f"""다음은 교수자가 승인한 최종 채점 기준입니다:
{state['refined_rubric']}

아래는 학생 답안입니다:
{student_answer}

각 항목별로 아래 형태의 표를 작성해 주세요:
| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |

- 표 마지막에 GPT 추천 총점도 표로 작성해 주세요.
- 마지막에 간략한 피드백도 포함해 주세요.
"""
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    
    grading_result = response.choices[0].message.content
    
    # 점수 추출 (정규식으로 총점 찾기)
    total_score_match = re.search(r"GPT 추천 총점.*?(\d+(\.\d+)?)/(\d+(\.\d+)?)", grading_result)
    score = "N/A"
    if total_score_match:
        score = total_score_match.group(1)
    
    # 기존 결과에 추가
    graded_results = state.get("graded_results", [])
    graded_results.append({
        "student_name": student_info["name"],
        "student_id": student_info["id"],
        "answer": student_answer,
        "grading_result": grading_result,
        "score": score,
        "index": current_idx
    })
    
    return {
        **state,
        "graded_results": graded_results,
        "current_student_index": current_idx + 1,
        "status": "grading_in_progress",
        "history": state["history"] + [{"action": "grade_answer", "timestamp": datetime.now().isoformat(), "student": student_info["id"]}]
    }

# 그래프 상태 전환 조건
def should_continue_grading(state: GradingState) -> str:
    if state["current_student_index"] >= len(state["student_answers"]):
        return "completed"
    else:
        return "continue"

# LangGraph 워크플로우 설정
def create_grading_workflow():
    # 그래프 생성
    workflow = StateGraph(GradingState)
    
    # 노드 추가
    workflow.add_node("generate_initial_rubric", generate_initial_rubric)
    workflow.add_node("grade_sample_answers", grade_sample_answers)
    workflow.add_node("refine_rubric", refine_rubric)
    workflow.add_node("grade_all_answers", grade_all_answers)
    
    # 엣지 (흐름) 설정
    workflow.add_edge("generate_initial_rubric", "grade_sample_answers")
    workflow.add_edge("grade_sample_answers", "refine_rubric")
    workflow.add_edge("refine_rubric", "grade_all_answers")
    
    # 분기 추가 (학생 답안 순환 처리)
    workflow.add_conditional_edges(
        "grade_all_answers",
        should_continue_grading,
        {
            "continue": "grade_all_answers",
            "completed": END
        }
    )
    
    # 체크포인트 설정 (상태 저장)
    checkpoint_dir = os.path.join(os.getcwd(), "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    checkpoint = LocalStateCheckpoint(checkpoint_dir)
    
    # 컴파일
    return workflow.compile(checkpointer=checkpoint)

# Streamlit UI 구성
st.title("🎓 AI 교수자 채점 시스템 (LangGraph)")

# 탭 설정
tab1, tab2, tab3, tab4 = st.tabs(["1. 문제 및 답안 업로드", "2. 채점 기준 확인", "3. 교수자 피드백", "4. 최종 채점 결과"])

# 세션 상태 초기화
if "workflow" not in st.session_state:
    st.session_state.workflow = create_grading_workflow()
if "workflow_id" not in st.session_state:
    st.session_state.workflow_id = None
if "current_state" not in st.session_state:
    st.session_state.current_state = None
if "initial_setup_done" not in st.session_state:
    st.session_state.initial_setup_done = False
if "rubric_refined" not in st.session_state:
    st.session_state.rubric_refined = False
if "grading_completed" not in st.session_state:
    st.session_state.grading_completed = False

# 탭 1: 문제 및 답안 업로드
with tab1:
    st.header("📂 문제 및 학생 답안 업로드")
    
    problem_pdf = st.file_uploader("👉 문제 PDF 파일을 업로드해 주세요.", type="pdf")
    answers_pdfs = st.file_uploader("👉 학생 답안 PDF 파일(복수 선택 가능)", type="pdf", accept_multiple_files=True)
    
    if problem_pdf and answers_pdfs:
        if st.button("✅ 1단계: 문제 분석 및 채점 준비"):
            with st.spinner("문제 및 답안을 분석 중입니다..."):
                # 문제 텍스트 추출
                problem_text = extract_text_from_pdf(problem_pdf)
                
                # 학생 답안 추출
                all_answers = []
                student_info_list = []
                
                for pdf_file in answers_pdfs:
                    pdf_text = extract_text_from_pdf(pdf_file)
                    answers, info_list = extract_answers_and_info(pdf_text)
                    all_answers.extend(answers)
                    student_info_list.extend(info_list)
                
                if len(all_answers) == 0:
                    st.error("답안을 추출할 수 없습니다. 파일 형식을 확인해 주세요.")
                else:
                    # 워크플로우 초기 상태 설정
                    initial_state = {
                        "problem_text": problem_text,
                        "initial_rubric": "",
                        "refined_rubric": "",
                        "student_answers": all_answers,
                        "student_info": student_info_list,
                        "graded_results": [],
                        "instructor_feedback": "",
                        "current_student_index": 0,
                        "status": "initialized",
                        "history": [{"action": "initialize", "timestamp": datetime.now().isoformat()}]
                    }
                    
                    # 워크플로우 시작
                    config = {"configurable": {"thread_id": "grading_session"}}
                    result = st.session_state.workflow.invoke(initial_state, config=config)
                    
                    # 세션 상태 저장
                    st.session_state.workflow_id = result.get("thread_id", "main")
                    st.session_state.current_state = result
                    st.session_state.initial_setup_done = True
                    
                    st.success(f"초기 설정 완료! 총 {len(all_answers)}명의 학생 답안이 준비되었습니다.")
                    st.rerun()

# 탭 2: 채점 기준 확인
with tab2:
    st.header("📊 채점 기준 확인")
    
    if not st.session_state.initial_setup_done:
        st.info("먼저 문제 및 답안을 업로드해 주세요.")
    else:
        current_state = st.session_state.current_state
        
        if current_state["status"] == "initialized":
            if st.button("✅ 2단계: 초기 채점 기준 생성"):
                with st.spinner("GPT가 초기 채점 기준을 생성 중입니다..."):
                    config = {"configurable": {"thread_id": st.session_state.workflow_id}}
                    result = st.session_state.workflow.invoke(
                        {"generate_initial_rubric": current_state},
                        config=config
                    )
                    st.session_state.current_state = result
                    st.rerun()
        
        if current_state["status"] in ["initial_rubric_generated", "sample_graded", "rubric_refined", "grading_in_progress", "all_graded"]:
            st.subheader("🔍 초기 채점 기준")
            st.write(current_state["initial_rubric"])
            
            if current_state["status"] == "initial_rubric_generated":
                if st.button("✅ 3단계: 샘플 답안 채점"):
                    with st.spinner("샘플 답안을 채점 중입니다..."):
                        config = {"configurable": {"thread_id": st.session_state.workflow_id}}
                        result = st.session_state.workflow.invoke(
                            {"grade_sample_answers": current_state},
                            config=config
                        )
                        st.session_state.current_state = result
                        st.rerun()
            
            if current_state["status"] in ["sample_graded", "rubric_refined", "grading_in_progress", "all_graded"]:
                st.subheader("📝 샘플 채점 결과")
                for idx, sample in enumerate(current_state["sample_results"]):
                    with st.expander(f"학생 {sample['student_name']} ({sample['student_id']}) - 점수: {sample['score']}"):
                        st.write(sample["grading_result"])

# 탭 3: 교수자 피드백
with tab3:
    st.header("💬 교수자 피드백")
    
    if not st.session_state.initial_setup_done:
        st.info("먼저 문제 및 답안을 업로드해 주세요.")
    else:
        current_state = st.session_state.current_state
        
        if current_state["status"] in ["sample_graded", "rubric_refined", "grading_in_progress", "all_graded"]:
            if not st.session_state.rubric_refined:
                feedback = st.text_area(
                    "채점 기준과 샘플 채점 결과에 대한 피드백을 입력해 주세요.",
                    height=200,
                    placeholder="예: '이론적 배경 항목의 배점을 10점에서 15점으로 올려주세요. 문제 이해도 평가를 더 엄격하게 해주세요.'"
                )
                
                if st.button("✅ 4단계: 채점 기준 수정"):
                    with st.spinner("피드백을 바탕으로 채점 기준을 수정 중입니다..."):
                        # 교수자 피드백 업데이트
                        current_state["instructor_feedback"] = feedback
                        
                        config = {"configurable": {"thread_id": st.session_state.workflow_id}}
                        result = st.session_state.workflow.invoke(
                            {"refine_rubric": current_state},
                            config=config
                        )
                        st.session_state.current_state = result
                        st.session_state.rubric_refined = True
                        st.rerun()
            
            if current_state["status"] in ["rubric_refined", "grading_in_progress", "all_graded"] or st.session_state.rubric_refined:
                st.subheader("📋 수정된 채점 기준")
                st.write(current_state["refined_rubric"])
                
                if not st.session_state.grading_completed and current_state["status"] != "all_graded":
                    if st.button("✅ 5단계: 모든 학생 답안 채점"):
                        with st.spinner("모든 학생 답안을 채점 중입니다..."):
                            config = {"configurable": {"thread_id": st.session_state.workflow_id}}
                            
                            # 워크플로우 계속 실행 (모든 학생 채점 완료될 때까지)
                            result = current_state
                            while result["status"] != "all_graded":
                                result = st.session_state.workflow.invoke(
                                    {"grade_all_answers": result},
                                    config=config
                                )
                                # 진행 상황 업데이트
                                progress = (result["current_student_index"] / len(result["student_answers"])) * 100
                                st.progress(min(100, int(progress)))
                            
                            st.session_state.current_state = result
                            st.session_state.grading_completed = True
                            st.success("모든 학생 답안 채점이 완료되었습니다!")
                            st.rerun()

# 탭 4: 최종 채점 결과
with tab4:
    st.header("📊 최종 채점 결과")
    
    if not st.session_state.initial_setup_done:
        st.info("먼저 문제 및 답안을 업로드해 주세요.")
    elif not st.session_state.grading_completed and st.session_state.current_state["status"] != "all_graded":
        st.info("모든 단계를 완료한 후 결과를 확인할 수 있습니다.")
    else:
        current_state = st.session_state.current_state
        
        # 채점 통계
        grades = [float(res["score"]) for res in current_state["graded_results"] if res["score"] != "N/A"]
        
        if grades:
            col1, col2, col3 = st.columns(3)
            col1.metric("평균 점수", f"{sum(grades) / len(grades):.2f}")
            col2.metric("최고 점수", f"{max(grades):.2f}")
            col3.metric("최저 점수", f"{min(grades):.2f}")
            
            # 데이터프레임 생성
            df = pd.DataFrame([{
                "이름": res["student_name"],
                "학번": res["student_id"],
                "점수": res["score"]
            } for res in current_state["graded_results"]])
            
            st.subheader("📋 전체 채점 결과")
            st.dataframe(df)
            
            # CSV 다운로드 옵션
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 CSV 파일로 다운로드",
                csv,
                "grading_results.csv",
                "text/csv",
                key='download-csv'
            )
            
            # 개별 채점 결과 확인
            st.subheader("📝 개별 채점 결과")
            selected_student = st.selectbox(
                "학생 선택",
                options=[f"{res['student_name']} ({res['student_id']})" for res in current_state["graded_results"]]
            )
            
            if selected_student:
                student_id = selected_student.split("(")[1].split(")")[0]
                for res in current_state["graded_results"]:
                    if res["student_id"] == student_id:
                        st.write(res["grading_result"])
                        break
