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
{rubric_text}

아래는 학생({name}, {sid})의 답안입니다:
{answer}

이 기준에 따라 채점 결과를 아래 형식으로 작성하세요.

---
## ✅ 예시를 먼저 확인하세요  (✋ 실제 채점 전 반드시 읽기!)

### [예시 채점 기준]  
| 채점 항목 | 배점 | 세부 기준 |
|----------------------------|------|-------------------------------------------------------------------|
| 지도학습과 비지도학습의 차이 설명 | 5점 | 두 학습 방법의 정의·라벨 유무·대표 알고리즘을 명확히 설명했는가 |
| KNN 알고리즘 설명 | 5점 | 작동 원리(거리 기반), 주요 수식, 하이퍼파라미터(K) 언급 여부 |
| 분류 모델 성능 지표(Accuracy·Precision·Recall) 설명 | 5점 | 각 지표의 정의·수식·한계점을 구체적으로 기술했는가 |

### [예시 학생 답안]  
지도학습은 **라벨이 포함된 데이터**를 사용해 모델을 학습시키는 방식이고,  
비지도학습은 라벨 없이 **데이터 내 패턴을 발견**한다. 대표적으로 K‑Means가 있다.  

K‑Nearest Neighbors(KNN)는 **새로운 샘플과 학습 샘플 간의 거리를 계산**하여  
가장 가까운 K개의 이웃의 다수결로 클래스를 결정한다.  
거리 측정에는 유클리드·맨해튼 거리가 흔히 쓰이며, **K 값은 하이퍼파라미터**다.  

모델 성능 평가는 Accuracy(전체 정답률), Precision(정답 중 실제 양성 비율),  
Recall(실제 양성 중 모델이 맞힌 비율)을 사용한다. **불균형 데이터**에서는  
Accuracy가 높아도 성능을 과대평가할 수 있다.

### [예시 채점 결과]  
| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|--------------------------------|------|-----------|--------------------------------------------------------------|
| 지도학습과 비지도학습의 차이 설명 | 5점 | 5점 | 라벨 유무·대표 알고리즘(K‑Means)까지 정확히 언급함 |
| KNN 알고리즘 설명               | 5점 | 4점 | 하이퍼파라미터(K) 언급 O, 수식 언급 X → 일부 부족 |
| 분류 모델 성능 지표 설명        | 5점 | 5점 | 세 지표 정의·한계(불균형 데이터)까지 명확히 설명 |

**근거 문장(Evidence):**  
- *지도/비지도*: "지도학습은 라벨이 포함된 데이터를 사용해 모델을 학습시키는 방식이고, 비지도학습은 라벨 없이 데이터 내 패턴을 발견한다."  
- *KNN*: "K‑Nearest Neighbors(KNN)는 새로운 샘플과 학습 샘플 간의 거리를 계산하여 가장 가까운 K개의 이웃의 다수결로 클래스를 결정한다."  
- *성능 지표*: "불균형 데이터에서는 Accuracy가 높아도 성능을 과대평가할 수 있다."

**총점: 14점 / 15점**  
**총평:** 핵심 개념을 충실히 서술했으나 KNN 수식 예시는 생략됨. 👏

---

## ✍️ 실제 채점 결과를 아래 형식으로 작성하세요

1. **마크다운 표**  
| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|-----------|-----|-----------|-----------|
| 항목1 …   | …   | …         | … |

2. **근거 문장(Evidence)**  
각 항목별로 최대 3개, 반드시 학생 답안에서 **직접 발췌**한 문장을 쌍따옴표로 기재하세요.

3. **총점과 총평**  
**총점: XX점**  
**총평:** …

⚠️ 주의  
- 근거 문장은 원문 그대로! 요약·의역 금지.  
- 항목별 점수·근거의 논리적 대응 관계를 유지하세요.  
- 표·헤더·굵은 글씨 등 **마크다운 형식**을 엄격히 지켜 출력하세요.
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
