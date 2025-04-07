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

# -------------------- STEP 4: 전체 채점 및 하이라이팅 --------------------
if st.session_state.step == 4:
    if st.session_state.problem_text and st.session_state.problem_filename:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        
        # 피드백이 적용된 수정 기준이 있으면 그것을 사용, 없으면 원본 기준 사용
        rubric_text = st.session_state.modified_rubrics.get(rubric_key, 
                      st.session_state.generated_rubrics.get(rubric_key))

        if not rubric_text:
            st.warning("STEP 1에서 채점 기준을 먼저 생성해주세요.")
        elif not st.session_state.student_answers_data:
            st.warning("STEP 2에서 학생 답안을 먼저 업로드해주세요.")
        else:
            st.subheader("📊 채점 기준")
            st.markdown(rubric_text)

            # 하이라이팅 함수 정의
            def apply_highlight(text, grading_items):
                """
                학생 답안에서 평가 근거가 된 부분을 하이라이팅
                """
                highlighted_text = text
                
                # 근거 문장들을 찾아서 하이라이팅
                for item in grading_items:
                    evidence = item.get("근거문장", "")
                    if evidence and evidence in highlighted_text:
                        # 노란색 배경으로 하이라이팅
                        highlighted_text = highlighted_text.replace(
                            evidence,
                            f'<span style="background-color: #FFFF00;">{evidence}</span>'
                        )
                
                # 줄바꿈 보존
                highlighted_text = highlighted_text.replace('\n', '<br>')
                return highlighted_text

            if st.button("📥 전체 학생 채점 실행"):
                grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                st.session_state.all_grading_results = []
                st.session_state.highlighted_results = []
                
                progress_bar = st.progress(0)
                total_students = len(st.session_state.student_answers_data)
                
                with st.spinner("GPT가 전체 학생을 채점 중입니다..."):
                    for i, stu in enumerate(st.session_state.student_answers_data):
                        name, sid, answer = stu["name"], stu["id"], stu["text"]
                        
                        # GPT에게 채점 및 근거 문장 추출 요청
                        prompt = f"""
다음은 채점 기준입니다:
{rubric_text}

아래는 학생 답안입니다:
{answer}

채점을 수행하고 각 채점 항목별로 학생이 작성한 답안에서 근거가 된 문장이나 구절을 명확히 추출해주세요.
답변은 다음 JSON 형식으로 제공해주세요:

```json
{{
  "total_score": 점수 총합(정수),
  "feedback": "전체적인 총평",
  "grading_details": [
    {{
      "criterion": "채점 항목명",
      "max_score": 해당 항목 배점(정수),
      "given_score": 부여한 점수(정수),
      "explanation": "점수 부여 이유에 대한 설명",
      "evidence": "학생 답안에서 해당 점수 판단의 근거가 된 실제 문장 또는 구절(정확히 원문에서 추출)"
    }}
  ]
}}
```

중요: 
1. "evidence" 필드에는 반드시 원문에서 실제로 찾을 수 있는 텍스트를 그대로 복사해서 넣어주세요. 추상적인 설명이 아닌 실제 문장이어야 합니다.
2. 근거를 찾을 수 없는 경우에만 "evidence" 필드를 비워두세요.
3. 모든 JSON 필드 이름과 구조를 정확히 지켜주세요.
"""
                        # GPT 호출
                        result = grading_chain.invoke({"input": prompt})
                        
                        try:
                            # JSON 파싱
                            json_start = result["text"].find("{")
                            json_end = result["text"].rfind("}")
                            if json_start != -1 and json_end != -1:
                                json_content = result["text"][json_start:json_end+1]
                                data = json.loads(json_content)
                                
                                # 하이라이팅 적용
                                highlighted_answer = answer
                                for detail in data.get("grading_details", []):
                                    evidence = detail.get("evidence", "")
                                    if evidence and evidence in highlighted_answer:
                                        # 각 채점 항목에 대한 다른 색상 적용
                                        color = f"hsl({(hash(detail['criterion']) % 360)}, 80%, 80%)"
                                        highlighted_answer = highlighted_answer.replace(
                                            evidence,
                                            f'<span style="background-color: {color}; padding: 2px; border-radius: 3px;" title="{detail["criterion"]}: {detail["given_score"]}/{detail["max_score"]}점">{evidence}</span>'
                                        )
                                
                                # 줄바꿈 보존
                                highlighted_answer = highlighted_answer.replace('\n', '<br>')
                                
                                # 결과 저장
                                st.session_state.highlighted_results.append({
                                    "name": name,
                                    "id": sid,
                                    "score": data.get("total_score"),
                                    "feedback": data.get("feedback"),
                                    "highlighted_text": highlighted_answer,
                                    "grading_details": data.get("grading_details")
                                })
                                
                                # 원본 응답도 저장
                                st.session_state.all_grading_results.append({
                                    "name": name, 
                                    "id": sid,
                                    "data": data
                                })
                            else:
                                st.error(f"{name}({sid})의 채점 결과에서 JSON을 찾을 수 없습니다.")
                                
                        except Exception as e:
                            st.error(f"{name}({sid})의 채점 결과 처리 중 오류 발생: {str(e)}")
                            st.code(result["text"])
                        
                        # 진행률 업데이트
                        progress_bar.progress((i + 1) / total_students)
                
                progress_bar.empty()
                st.success(f"✅ 전체 학생({total_students}명) 채점 완료")

            # 결과 표시 섹션
            if st.session_state.highlighted_results:
                st.subheader("📋 전체 학생 채점 결과")
                
                # 학생 선택 필터
                all_students = [(f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']})")
                               for r in st.session_state.highlighted_results]
                selected_student = st.selectbox("🧑‍🎓 학생 선택", ["모든 학생 보기"] + all_students)
                
                scores = []
                
                # 선택된 학생 또는 모든 학생 결과 표시
                for r in st.session_state.highlighted_results:
                    student_label = f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']})"
                    
                    if selected_student == "모든 학생 보기" or selected_student == student_label:
                        st.markdown(f"### ✍️ {r['name']} ({r['id']}) - 총점: {r['score']}점")
                        
                        with st.expander("📝 채점 세부 내역", expanded=False):
                            for detail in r.get("grading_details", []):
                                st.markdown(f"""
                                **{detail.get('criterion')}** ({detail.get('given_score')}/{detail.get('max_score')}점)  
                                - 평가: {detail.get('explanation')}  
                                - 근거: _{detail.get('evidence', '(근거 없음)')}_ 
                                """)
                        
                        st.markdown(f"🗣️ **GPT 피드백:** {r['feedback']}")
                        
                        with st.expander("🧾 학생 답안 (하이라이팅 표시)", expanded=True):
                            st.markdown(r["highlighted_text"], unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        if r["score"] is not None:
                            scores.append(r["score"])
                
                # 점수 분포 시각화 (모든 학생 선택 시에만)
                if scores and selected_student == "모든 학생 보기":
                    st.subheader("📊 점수 분포")
                    fig, ax = plt.subplots(figsize=(10, 6))
                    
                    # 점수 범위에 맞게 bins 설정
                    min_score = min(scores)
                    max_score = max(scores)
                    bins = range(min_score, max_score + 2)
                    
                    # 히스토그램 생성
                    n, bins, patches = ax.hist(scores, bins=bins, edgecolor='black', alpha=0.7, align='left')
                    
                    # 평균선 추가
                    mean_score = sum(scores) / len(scores)
                    ax.axvline(mean_score, color='red', linestyle='dashed', linewidth=1)
                    ax.text(mean_score + 0.5, max(n) * 0.9, f'평균: {mean_score:.1f}점', color='red')
                    
                    # 축 및 제목 설정
                    ax.set_xlabel("점수")
                    ax.set_ylabel("학생 수")
                    ax.set_title("GPT 채점 점수 분포")
                    ax.set_xticks(range(min_score, max_score + 1))
                    ax.grid(axis='y', alpha=0.3)
                    
                    # 그래프 표시
                    st.pyplot(fig)
                    
                    # 기본 통계 정보 표시
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("평균 점수", f"{mean_score:.1f}점")
                    col2.metric("최고 점수", f"{max_score}점")
                    col3.metric("최저 점수", f"{min_score}점")
                    col4.metric("총 학생 수", f"{len(scores)}명")
                    
                    # 엑셀 다운로드 기능
                    excel_data = []
                    for r in st.session_state.highlighted_results:
                        if r["score"] is not None:
                            row = {
                                "학번": r["id"],
                                "이름": r["name"],
                                "총점": r["score"],
                                "피드백": r["feedback"]
                            }
                            # 각 채점 항목별 점수 추가
                            for detail in r.get("grading_details", []):
                                criterion = detail.get("criterion", "")
                                score = detail.get("given_score", 0)
                                row[criterion] = score
                            excel_data.append(row)
                    
                    if excel_data:
                        import pandas as pd
                        df = pd.DataFrame(excel_data)
                        
                        # 엑셀 파일로 변환
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            df.to_excel(writer, sheet_name='성적표', index=False)
                        
                        # 다운로드 버튼
                        st.download_button(
                            label="📊 성적표 엑셀 다운로드",
                            data=buffer.getvalue(),
                            file_name="AI_채점_결과.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
    else:
        st.warning("STEP 1에서 문제 업로드가 필요합니다.")
        if st.button("STEP 1로 이동"):
            st.session_state.step = 1
