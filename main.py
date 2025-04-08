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

# 페이지 설정
st.set_page_config(page_title="AI 채점 시스템", layout="wide")
st.title("🎓 AI 기반 자동 채점 시스템 - by DPT")

# GPT 초기화
llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

# 세션 상태 초기화
def initialize_session_state():
    defaults = {
        "rubric_memory": ConversationSummaryMemory(
            llm=llm, memory_key="history", return_messages=True
        ),
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

# Prompt 및 체인 설정
prompt_template = PromptTemplate.from_template("{history}\n{input}")
rubric_chain = LLMChain(llm=llm, prompt=prompt_template, memory=st.session_state.rubric_memory)

# PDF 텍스트 추출 함수
def extract_text_from_pdf(pdf_data):
    reader = PyPDF2.PdfReader(io.BytesIO(pdf_data) if isinstance(pdf_data, bytes) else io.BytesIO(pdf_data.read()))
    return "".join([page.extract_text() or "" for page in reader.pages])

# 파일명에서 이름/학번 추출
def extract_info_from_filename(filename):
    base_filename = os.path.splitext(os.path.basename(filename))[0]
    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"
    name_candidates = [part for part in re.findall(r'[가-힣]{2,5}', base_filename) if part not in student_id]
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}
    for name in name_candidates:
        if name not in exclude_words:
            return name, student_id
    return "UnknownName", student_id

# 학생 PDF 처리
def process_student_pdfs(pdf_files):
    answers, info = [], []
    for file in pdf_files:
        file.seek(0)
        file_bytes = file.read()
        text = extract_text_from_pdf(io.BytesIO(file_bytes))
        name, sid = extract_info_from_filename(file.name)
        if len(text.strip()) > 20:
            answers.append(text)
            info.append({'name': name, 'id': sid, 'text': text})
    st.session_state.student_answers_data = info
    return answers, info

# 총점 추출 함수
def extract_total_score(grading_text):
    match = re.search(r'총점[:：]?\s*(\d+)\s*점', grading_text)
    return int(match.group(1)) if match else None

# 사이드바
with st.sidebar:
    st.markdown("## \U0001F4D8 채점 흐름")

    if st.button("1️⃣ 문제 업로드 및 채점 기준 생성"):
        st.session_state.step = 1
    if st.button("2️⃣ 학생 답안 업로드 및 무작위 채점"):
        st.session_state.step = 2
    if st.button("3️⃣ 교수자 피드백 입력"):
        st.session_state.step = 3
    if st.button("4️⃣ 전체 학생 일괄 채점"):
        st.session_state.step = 4

    st.markdown("### \U0001F4DD 교수자 피드백")
    feedback = st.text_area("채점 기준 수정 피드백", value=st.session_state.feedback_text, key="sidebar_feedback")
    st.session_state.feedback_text = feedback

    with st.expander("ℹ️ 사용법 안내 보기"):
        st.markdown("""
**STEP 1:** 문제 업로드 → 채점 기준 생성  
**STEP 2:** 학생 답안 업로드 → 무작위 채점  
**STEP 3:** 교수자 피드백 → 기준 수정  
**STEP 4:** 전체 학생 자동 채점 + 점수 분포 시각화
""")

# STEP 1 - 문제 업로드 -> 채점 기준 생성
if st.session_state.step == 1:
    problem_pdf = st.file_uploader("📄 문제 PDF 업로드", type="pdf", key="problem_upload")

    if problem_pdf:
        # PDF 파일을 업로드하면 내용과 파일명을 세션 상태에 저장
        file_bytes = problem_pdf.read()
        st.session_state.problem_pdf_bytes = file_bytes
        st.session_state.problem_filename = problem_pdf.name
        text = extract_text_from_pdf(io.BytesIO(file_bytes))
        st.session_state.problem_text = text
        
        rubric_key = f"rubric_{problem_pdf.name}"

        st.subheader("📃 문제 내용")
        st.write(text)

        # 이미 생성된 채점 기준이 있는지 확인
        if rubric_key not in st.session_state.generated_rubrics:
            prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요 (반드시 **한글**로 작성):

문제: {text}

요구사항:
1. 표 형식으로 작성해주세요 (정확히 '| 채점 항목 | 배점 | 세부 기준 |' 형식의 마크다운 표를 사용하세요)
2. 각 항목의 세부 기준은 구체적으로 작성해주세요
3. 설명은 반드시 **한글**로 작성해야 하며, 영어 혼용 없이 작성해주세요
4. 표 아래에 **배점 총합**도 함께 작성해주세요
5. 반드시 마크다운 표 문법을 정확히 사용해주세요, (각 행 시작과 끝에 |, 헤더 행 아래에 |---|---|---| 형식의 구분선)

예시 형식:
| 채점 항목 | 배점 | 세부 기준 |
|---------|-----|---------|
| 항목 1 | 5점 | 세부 기준 설명 |
| 항목 2 | 10점 | 세부 기준 설명 |

**배점 총합: 15점**
"""
            if st.button("📐 채점 기준 생성"):
                # 메모리 초기화하여 이전 대화가 영향을 주지 않도록 함
                st.session_state.rubric_memory.clear()
                
                with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                    result = rubric_chain.invoke({"input": prompt})
                    # 생성된 채점 기준을 별도 딕셔너리에 저장
                    st.session_state.generated_rubrics[rubric_key] = result["text"]
                    st.success("✅ 채점 기준 생성 완료")
        else:
            if st.button("📐 채점 기준 재생성"):
                confirm = st.checkbox("⚠️ 이미 생성된 채점 기준이 있습니다. 재생성하시겠습니까?")
                if confirm:
                    # 여기서는 명시적으로 사용자가 재생성을 원할 때만 처리
                    prompt = f"""다음 문제에 대한 채점 기준을 작성해 주세요 (반드시 **한글**로 작성):

문제: {text}

요구사항:
1. 표 형식으로 작성해주세요 (정확히 '| 채점 항목 | 배점 | 세부 기준 |' 형식의 마크다운 표를 사용하세요)
2. 각 항목의 세부 기준은 구체적으로 작성해주세요
3. 설명은 반드시 **한글**로 작성해야 하며, 영어 혼용 없이 작성해주세요
4. 표 아래에 **배점 총합**도 함께 작성해주세요
5. 반드시 마크다운 표 문법을 정확히 사용하십시오 (각 행 시작과 끝에 |, 헤더 행 아래에 |---|---|---| 형식의 구분선)

예시 형식:
| 채점 항목 | 배점 | 세부 기준 |
|---------|-----|---------|
| 항목 1 | 5점 | 세부 기준 설명 |
| 항목 2 | 10점 | 세부 기준 설명 |

**배점 총합: 15점**
"""
                    st.session_state.rubric_memory.clear()
                    with st.spinner("GPT가 채점 기준을 재생성 중입니다..."):
                        result = rubric_chain.invoke({"input": prompt})
                        st.session_state.generated_rubrics[rubric_key] = result["text"]
                        st.success("✅ 채점 기준 재생성 완료")

        # 채점 기준 표시
        if rubric_key in st.session_state.generated_rubrics:
            st.subheader("📊 채점 기준")
            st.markdown(st.session_state.generated_rubrics[rubric_key])

#학생 답안 -> 무작위 채점
# STEP 2
elif st.session_state.step == 2:
    # 문제가 이미 업로드되었는지 확인
    if st.session_state.problem_text and st.session_state.problem_filename:
        st.subheader("📃 문제 내용")
        st.write(st.session_state.problem_text)
        
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        if rubric_key in st.session_state.generated_rubrics:
            st.subheader("📊 채점 기준")
            st.markdown(st.session_state.generated_rubrics[rubric_key])
        
        student_pdfs = st.file_uploader("📥 학생 답안 PDF 업로드 (여러 개)", type="pdf", accept_multiple_files=True, key="student_answers")
        
        if student_pdfs:
            if rubric_key not in st.session_state.generated_rubrics:
                st.warning("채점 기준이 없습니다. STEP 1에서 먼저 채점 기준을 생성해주세요.")
            else:
                if st.button("🎯 무작위 채점 실행"):
                    all_answers, info_list = process_student_pdfs(student_pdfs)
                    if not all_answers:
                        st.warning("답안을 찾을 수 없습니다.")
                    else:
                        idx = random.randint(0, len(all_answers) - 1)
                        selected_student = info_list[idx]
                        answer = all_answers[idx]

                        prompt = f"""다음은 채점 기준입니다:
{st.session_state.generated_rubrics[rubric_key]}

그리고 아래는 학생 답안입니다:
{answer}

이 기준에 따라 채점 표를 작성해 주세요:
반드시 다음과 같은 정확한 마크다운 표 형식을 사용하세요:

| 채점 항목 | 배점 | GPT 추천 점수 | 세부 평가 |
|---------|-----|------------|---------|
| 항목 1 | 5점 | 4점 | 평가 내용 |

표 아래에 총점과 간단한 피드백도 작성해주세요."""

                        with st.spinner("GPT가 채점 중입니다..."):
                            # 채점에는 메모리가 필요하지 않으므로 별도 체인을 만들어 사용
                            grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                            result = grading_chain.invoke({"input": prompt})
                            st.session_state.last_grading_result = result["text"]
                            st.session_state.last_selected_student = selected_student
                            st.success("✅ 채점 완료")
    else:
        st.warning("먼저 STEP 1에서 문제를 업로드해주세요.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1

    # 채점 결과 표시
    if st.session_state.last_grading_result and st.session_state.last_selected_student:
        stu = st.session_state.last_selected_student
        st.subheader(f"📋 채점 결과 - {stu['name']} ({stu['id']})")
        st.markdown(st.session_state.last_grading_result)

# STEP 3 : 교수자 피드백 -> 채점 기준 수정
elif st.session_state.step == 3:
    # 문제가 이미 업로드되었는지 확인
    if st.session_state.problem_text and st.session_state.problem_filename:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        
        if rubric_key not in st.session_state.generated_rubrics:
            st.warning("채점 기준이 없습니다. STEP 1에서 먼저 채점 기준을 생성해주세요.")
            if st.button("STEP 1로 이동"):
                st.session_state.step = 1
        else:
            # 원본 채점 기준 표시
            st.subheader("📊 원본 채점 기준")
            st.markdown(st.session_state.generated_rubrics[rubric_key])
            
            if st.button("♻️ 피드백 반영"):
                feedback = st.session_state.feedback_text
                if not feedback.strip():
                    st.warning("피드백을 입력해주세요.")
                else:
                    prompt = f"""기존 채점 기준:
{st.session_state.generated_rubrics[rubric_key]}

피드백:
{feedback}

요구사항:
1. 표 형식으로 작성해주세요 (정확히 '| 채점 항목 | 배점 | 세부 기준 |' 형식의 마크다운 표를 사용하세요)
2. 각 항목의 세부 기준은 구체적으로 작성해주세요
3. 설명은 반드시 **한글**로 작성해야 하며, 영어 혼용 없이 작성해주세요
4. 표 아래에 **배점 총합**도 함께 작성해주세요
5. 반드시 마크다운 표 문법을 정확히 사용하십시오 (각 행 시작과 끝에 |, 헤더 행 아래에 |---|---|---| 형식의 구분선)

예시 형식:
| 채점 항목 | 배점 | 세부 기준 |
|---------|-----|---------|
| 항목 1 | 5점 | 세부 기준 설명 |
| 항목 2 | 10점 | 세부 기준 설명 |

**배점 총합: 15점**
"""
                
                    with st.spinner("GPT가 기준을 수정 중입니다..."):
                        # 피드백 반영에도 별도 체인 사용
                        feedback_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                        updated = feedback_chain.invoke({"input": prompt})
                        st.session_state.modified_rubrics[rubric_key] = updated["text"]
                        st.success("✅ 채점 기준 수정 완료")
                
            # 수정된 채점 기준이 있으면 표시
            if rubric_key in st.session_state.modified_rubrics:
                st.subheader("🆕 수정된 채점 기준")
                st.markdown(st.session_state.modified_rubrics[rubric_key])
    else:
        st.warning("먼저 STEP 1에서 문제를 업로드해주세요.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1

# STEP 4: 전체 학생 채점 및 하이라이팅 (마크다운 기반으로 개선)

import re
import pandas as pd
from io import StringIO

# 마크다운 표 파싱 함수
def parse_markdown_grading_table(text):
    table_match = re.search(r"\| *채점 항목 *\|.*?\n(\|.*?\n)+", text, re.DOTALL)
    if not table_match:
        raise ValueError("마크다운 표를 찾을 수 없습니다.")

    table_text = table_match.group()
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip() and not re.match(r'^\|[- ]+\|$', line)]
    csv_text = '\n'.join([','.join([cell.strip() for cell in line.strip('|').split('|')]) for line in lines])
    df = pd.read_csv(StringIO(csv_text))

    total_score_match = re.search(r"총점[:：]?\s*(\d+)\s*점", text)
    total_score = int(total_score_match.group(1)) if total_score_match else None

    feedback_match = re.search(r"총평[:：]?\s*(.+)", text)
    feedback = feedback_match.group(1).strip() if feedback_match else ""

    return df, total_score, feedback

# 하이라이팅 함수

def apply_highlight(text, evidence_list):
    highlighted_text = text
    for idx, evidence in enumerate(evidence_list):
        if pd.isna(evidence) or len(evidence.strip()) < 5:
            continue
        color = f"hsl({(idx * 45) % 360}, 70%, 85%)"
        tooltip = f"근거 문장"
        if evidence in highlighted_text:
            highlighted_text = highlighted_text.replace(
                evidence,
                f'<span style="background-color: {color}; padding: 2px; border-radius: 3px;" title="{tooltip}">{evidence}</span>'
            )
    return highlighted_text.replace('\n', '<br>')

# STEP 4 실행
if st.session_state.step == 4:
    if st.session_state.problem_text and st.session_state.problem_filename:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        rubric_text = st.session_state.modified_rubrics.get(rubric_key, st.session_state.generated_rubrics.get(rubric_key))

        if not rubric_text:
            st.warning("STEP 1에서 채점 기준을 먼저 생성해주세요.")
        elif not st.session_state.student_answers_data:
            st.warning("STEP 2에서 학생 답안을 먼저 업로드해주세요.")
        else:
            st.subheader("📊 채점 기준")
            st.markdown(rubric_text)

            if st.button("📥 전체 학생 채점 실행"):
                grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                st.session_state.all_grading_results = []
                st.session_state.highlighted_results = []
                progress_bar = st.progress(0)
                total_students = len(st.session_state.student_answers_data)

                with st.spinner("GPT가 전체 학생을 채점 중입니다..."):
                    for i, stu in enumerate(st.session_state.student_answers_data):
                        name, sid, answer = stu["name"], stu["id"], stu["text"]

                        prompt = f"""
다음은 채점 기준입니다:
{rubric_text}

아래는 학생의 답안입니다:
{answer}

이 기준에 따라 아래와 같은 형식으로 채점해 주세요. 반드시 정확히 마크다운 표 형식을 지켜 주세요:

| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|----------|-----|-----------|-----------|
| 이해도 | 10 | 8 | 개념은 설명했지만 일부 용어 오용 |
| 논리성 | 5 | 5 | 주장 일관성 유지 |

총점: 13점  
총평: 전반적으로 잘 작성했지만 약간의 오해가 있습니다.
"""
                        result = grading_chain.invoke({"input": prompt})
                        try:
                            df, total_score, feedback = parse_markdown_grading_table(result["text"])
                            highlighted_answer = apply_highlight(answer, df['평가 근거'])

                            markdown_table = "| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |\n|----------|------|------------|-----------|\n"
                            for _, row in df.iterrows():
                                markdown_table += f"| {row['채점 항목']} | {row['배점']} | {row['부여 점수']} | {row['평가 근거']} |\n"

                            markdown_table += f"\n**총점: {total_score}점**\n\n**총평:** {feedback}"

                            st.session_state.highlighted_results.append({
                                "name": name,
                                "id": sid,
                                "score": total_score,
                                "feedback": feedback,
                                "highlighted_text": highlighted_answer,
                                "markdown_table": markdown_table,
                                "text": answer
                            })

                        except Exception as e:
                            st.error(f"{name}({sid})의 채점 결과 처리 중 오류 발생: {str(e)}")
                            st.code(result["text"])

                        progress_bar.progress((i + 1) / total_students)

                progress_bar.empty()
                st.success(f"✅ 전체 학생({total_students}명) 채점 완료")

            if st.session_state.highlighted_results:
                st.subheader("📋 전체 학생 채점 결과")
                sort_options = ["이름순", "학번순", "점수 높은순", "점수 낮은순"]
                sort_method = st.radio("정렬 방식", sort_options, horizontal=True)

                sorted_results = st.session_state.highlighted_results.copy()
                if sort_method == "이름순":
                    sorted_results.sort(key=lambda x: x["name"])
                elif sort_method == "학번순":
                    sorted_results.sort(key=lambda x: x["id"])
                elif sort_method == "점수 높은순":
                    sorted_results.sort(key=lambda x: x["score"], reverse=True)
                elif sort_method == "점수 낮은순":
                    sorted_results.sort(key=lambda x: x["score"])

                student_options = [(f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']})") for r in sorted_results]
                selected_student = st.selectbox("🧑‍🎓 학생 선택", ["모든 학생 보기"] + student_options)

                for r in sorted_results:
                    label = f"{r['name']} ({r['id']}) - {r['score']}점"
                    if selected_student == "모든 학생 보기" or selected_student == label:
                        st.markdown(f"### ✍️ {r['name']} ({r['id']}) - 총점: {r['score']}점")
                        st.markdown(r["markdown_table"])
                        tabs = st.tabs(["🔍 하이라이팅된 답안", "📝 원본 답안"])
                        with tabs[0]:
                            st.markdown(r["highlighted_text"], unsafe_allow_html=True)
                            st.info("💡 하이라이트된 부분 위에 마우스를 올리면 해당 채점 항목을 볼 수 있습니다.")
                        with tabs[1]:
                            st.text_area("원본 답안", value=r.get("text", ""), height=400, disabled=True)
                        st.markdown("---")
