import streamlit as st
import random
import re
import io
import os
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate
import html
import pdfplumber

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


# -------------------------------
# PDF 텍스트 추출 함수
# -------------------------------
def extract_text_from_pdf(pdf_data):
    if isinstance(pdf_data, bytes):
        pdf_stream = io.BytesIO(pdf_data)
    else:
        pdf_stream = io.BytesIO(pdf_data.read())

    text = ""
    with pdfplumber.open(pdf_stream) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    return text

# -------------------------------
# 전처리: 문단 정리 및 불필요한 줄 제거
# -------------------------------
def clean_text_postprocess(text):
    lines = text.split('\n')
    cleaned = []
    prev_blank = True  # 문단 시작 여부 체크용

    for line in lines:
        line = line.strip()
        # 스킵할 줄: 페이지 번호, 과제 제목, 학번 줄 등
        if re.search(r'DIGB226|Final Take-Home Exam|^\s*-\s*\d+\s*-$', line):
            continue
        if re.search(r'^\d{9,10}\s*[\uAC00-\uD7A3]+$', line):
            continue
        if not line:
            prev_blank = True
            continue

        # 새 문단 시작 시 빈 줄 추가
        if prev_blank:
            cleaned.append("")  # 빈 줄 넣기
        cleaned.append(line)
        prev_blank = False

    return "\n".join(cleaned)


#파일명 추출
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


# -------------------------------
# 학생 PDF 처리 함수
# -------------------------------
def process_student_pdfs(pdf_files):
    answers, info = [], []
    for file in pdf_files:
        file.seek(0)
        file_bytes = file.read()

        # 텍스트 추출 후 문단 정리까지!
        text = extract_text_from_pdf(io.BytesIO(file_bytes))
        text = clean_text_postprocess(text)

        name, sid = extract_info_from_filename(file.name)
        if len(text.strip()) > 20:
            answers.append(text)
            info.append({'name': name, 'id': sid, 'text': text})

    st.session_state.student_answers_data = info
    return answers, info

#들여쓰기 처리
def apply_indentation(text):
    lines = text.split('\n')
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<br>")
            continue
        if re.match(r'^\d+(\.\d+)*\s', line):  # 1. / 1.1 / 2. 같은 제목
            html_lines.append(f"<p style='margin-bottom: 5px; font-weight: bold;'>{html.escape(line)}</p>")
        else:
            html_lines.append(f"<p style='padding-left: 20px; margin: 0;'>{html.escape(line)}</p>")
    return "\n".join(html_lines)

# 총점 추출 함수
def extract_total_score(grading_text):
    match = re.search(r'총점[:：]?\s*(\d+)\s*점', grading_text)
    return int(match.group(1)) if match else None

from difflib import get_close_matches
import html

def apply_highlight_fuzzy(text, evidences, threshold=0.75):
    """
    학생 답안에서 증거 문장을 fuzzy하게 매칭하여 하이라이팅하는 함수

    Args:
        text (str): 전체 학생 답안 텍스트
        evidences (list of str): 채점 기준에서 추출된 증거 문장들
        threshold (float): 유사도 매칭 기준 (0~1)

    Returns:
        str: HTML 형식으로 하이라이팅된 텍스트
    """
    lines = text.split('\n')
    used_indices = set()
    html_lines = []

    for line in lines:
        matched = False
        for idx, evidence in enumerate(evidences):
            matches = get_close_matches(evidence.strip(), [line.strip()], n=1, cutoff=threshold)
            if matches and idx not in used_indices:
                used_indices.add(idx)
                color = ["#FFD6D6", "#D6FFD6", "#D6D6FF", "#FFFFD6", "#FFD6FF", "#D6FFFF"][idx % 6]
                safe_line = html.escape(line)
                highlighted = f'<span style="background-color:{color}; padding:2px; border-radius:3px;">{safe_line}</span>'
                html_lines.append(highlighted)
                matched = True
                break
        if not matched:
            html_lines.append(html.escape(line))

    return "<br>".join(html_lines)


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
**STEP 4:** 전체 학생 자동 채점 + 하이라이팅
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

# STEP 2 - 학생 답안 -> 무작위 채점
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

# STEP 4 - 전체 학생 채점 및 근거 문장 확인
elif st.session_state.step == 4:
    rubric_key = f"rubric_{st.session_state.problem_filename}"
    
    # 최종 채점 기준 (수정된 것이 있으면 수정된 것, 없으면 원본)
    rubric_text = st.session_state.modified_rubrics.get(rubric_key, st.session_state.generated_rubrics.get(rubric_key))

    if not rubric_text:
        st.warning("채점 기준이 없습니다. STEP 1을 먼저 진행하세요.")
    elif not st.session_state.student_answers_data:
        st.warning("학생 답안이 없습니다. STEP 2를 먼저 진행하세요.")
    else:
        st.subheader("📊 채점 기준")
        st.markdown(rubric_text)

        if st.button("📝 전체 학생 채점 실행"):
            st.session_state.highlighted_results = []
            progress_bar = st.progress(0)
            total_students = len(st.session_state.student_answers_data)
            
            with st.spinner("GPT가 채점 중입니다..."):
                for i, student in enumerate(st.session_state.student_answers_data):
                    name, sid, answer = student["name"], student["id"], student["text"]
                    
                    # GPT 채점 프롬프트
                    prompt = f"""
다음은 채점 기준입니다:
다음은 채점 기준입니다:
{rubric_text}

아래는 학생({name}, {sid})의 답안입니다:
{answer}

---

채점을 진행하기 전에 예시를 먼저 확인하세요:

=============================  
[예시 채점 기준]

| 채점 항목 | 배점 | 세부 기준 |
|----------|-----|-----------|
| 인공신경망(ANN)의 기본 개념 설명 | 5점 | 뉴런, 가중치, 활성화 함수 등의 개념을 포함해 설명했는가 |
| 딥러닝과 머신러닝의 차이 설명 | 5점 | 특징 또는 학습 방식의 차이를 명확히 서술했는가 |
| 역전파 알고리즘의 작동 원리 설명 | 10점 | 오차 계산 → 가중치 갱신 과정을 단계적으로 설명했는가 |

[예시 학생 답안]

딥러닝은 인공신경망을 기반으로 한 학습 방식이다.  
ANN은 입력을 받아 가중치를 곱한 후, 활성화 함수를 거쳐 출력을 생성한다.  
머신러닝은 사람이 특징을 설계해야 하지만, 딥러닝은 스스로 특징을 학습한다.  
역전파는 출력과 실제값의 오차를 계산한 뒤, 그 오차를 네트워크의 가중치에 따라 역으로 전달하며 학습한다.  

[예시 채점 결과]

| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|-------------------------|------|------------|--------------------------|
| 인공신경망(ANN)의 기본 개념 설명 | 5점 | 5점 | "ANN은 입력을 받아 가중치를 곱한 후, 활성화 함수를 거쳐 출력을 생성한다."  
| 딥러닝과 머신러닝의 차이 설명 | 5점 | 5점 | "머신러닝은 사람이 특징을 설계해야 하지만, 딥러닝은 스스로 특징을 학습한다."  
| 역전파 알고리즘의 작동 원리 설명 | 10점 | 10점 | "역전파는 출력과 실제값의 오차를 계산한 뒤, 그 오차를 네트워크의 가중치에 따라 역으로 전달하며 학습한다."  

**근거 문장:**
- "ANN은 입력을 받아 가중치를 곱한 후, 활성화 함수를 거쳐 출력을 생성한다."
- "머신러닝은 사람이 특징을 설계해야 하지만, 딥러닝은 스스로 특징을 학습한다."
- "역전파는 출력과 실제값의 오차를 계산한 뒤, 그 오차를 네트워크의 가중치에 따라 역으로 전달하며 학습한다."

**총점: 20점**  
**총평:** 학생은 주요 개념을 모두 정확히 이해하고 서술하였다.

=============================

위와 같은 형식을 참고하여, 아래의 실제 학생 답안에 대해 채점을 진행해주세요.

⚠️ 주의사항:
- 근거 문장은 반드시 학생이 실제 작성한 문장에서 그대로 발췌해야 합니다.
- 요약, 의역, 재구성 없이 "원문 그대로"를 사용하세요.
- 평가 근거는 채점 항목별로 명확히 연결되어야 하며, 구체적인 문장을 들어 설명해야 합니다.

---

이제 아래 실제 학생 답안을 평가하세요:

[실제 채점 시작 ↓↓↓]
"""
                    
                    # 채점 실행
                    grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                    result = grading_chain.invoke({"input": prompt})
                    grading_result = result["text"]
                    
                    # 근거 문장 추출
                    evidence_sentences = []
                    evidence_match = re.search(r'\*\*근거 문장:\*\*\s*([\s\S]*?)(?=\*\*총점|\Z)', grading_result)
                    if evidence_match:
                        evidence_text = evidence_match.group(1)
                        for line in evidence_text.split('\n'):
                            match = re.search(r'"(.*?)"', line)
                            if match:
                                evidence_sentences.append(match.group(1))
                    
                    # 총점 추출
                    total_score = None
                    score_match = re.search(r'\*\*총점: (\d+)점\*\*', grading_result)
                    if score_match:
                        total_score = int(score_match.group(1))
                    
                    # 총평 추출
                    feedback = ""
                    feedback_match = re.search(r'\*\*총평:\*\* (.*?)(?=\Z|\n\n)', grading_result)
                    if feedback_match:
                        feedback = feedback_match.group(1)
                    
                    # 결과 저장 (하이라이팅 제외)
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

        # 채점 결과 표시
        if st.session_state.highlighted_results:
            # 점수 순으로 정렬
            sorted_results = sorted(
                st.session_state.highlighted_results, 
                key=lambda x: x["score"] if x["score"] is not None else 0,
                reverse=True
            )
            
            st.subheader("📋 전체 학생 채점 결과")

            # 요약 테이블
            summary_data = [
                {"이름": r["name"], "학번": r["id"], "점수": r["score"] if r["score"] is not None else "N/A"} 
                for r in sorted_results
            ]
            
            st.subheader("📊 학생별 점수 요약")
            st.table(summary_data)
            
            # 각 학생별 상세 결과
            st.subheader("📝 학생별 상세 답안 및 채점")

            for idx, result in enumerate(sorted_results):
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
