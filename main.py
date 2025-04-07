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
st.set_page_config(page_title="상호작용 채점 시스템", layout="wide")
st.title("🎓 Interactiion AI 채점 시스템")

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
        "last_grading_result": None,
        "last_selected_student": None,
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

# -------------------- STEP 1: 문제 업로드 및 채점 기준 생성 --------------------
if st.session_state.step == 1:
    problem_pdf = st.file_uploader("📄 문제 PDF 업로드", type="pdf")
    if problem_pdf:
        file_bytes = problem_pdf.read()
        st.session_state.problem_pdf_bytes = file_bytes
        st.session_state.problem_filename = problem_pdf.name
        text = extract_text_from_pdf(file_bytes)
        st.session_state.problem_text = text
        rubric_key = f"rubric_{problem_pdf.name}"

        st.subheader("📃 문제 내용")
        st.write(text)

        if rubric_key not in st.session_state.generated_rubrics:
            prompt = f"""
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
            if st.button("📐 채점 기준 생성"):
                st.session_state.rubric_memory.clear()
                rubric_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"), memory=st.session_state.rubric_memory)
                with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                    result = rubric_chain.invoke({"input": prompt})
                    st.session_state.generated_rubrics[rubric_key] = result["text"]
                    st.success("✅ 채점 기준 생성 완료")

        if rubric_key in st.session_state.generated_rubrics:
            st.subheader("📊 채점 기준")
            st.markdown(st.session_state.generated_rubrics[rubric_key])

# -------------------- STEP 2: 무작위 채점 --------------------
elif st.session_state.step == 2:
    rubric_key = f"rubric_{st.session_state.problem_filename}"
    rubric_text = st.session_state.generated_rubrics.get(rubric_key)

    if not st.session_state.problem_text:
        st.warning("STEP 1에서 문제를 먼저 업로드해주세요.")
    else:
        st.subheader("📃 문제 내용")
        st.write(st.session_state.problem_text)

        if rubric_text:
            st.subheader("📊 채점 기준")
            st.markdown(rubric_text)

        student_pdfs = st.file_uploader("📥 학생 답안 PDF 업로드 (여러 개 가능)", type="pdf", accept_multiple_files=True)

        if student_pdfs:
            st.session_state.student_answers_data.clear()
            answers = []
            for file in student_pdfs:
                file.seek(0)
                text = extract_text_from_pdf(file.read())
                name, sid = extract_info_from_filename(file.name)
                if len(text.strip()) > 20:
                    st.session_state.student_answers_data.append({"name": name, "id": sid, "text": text})
                    answers.append(text)

            if st.button("🎯 무작위 채점 실행") and rubric_text:
                idx = random.randint(0, len(st.session_state.student_answers_data) - 1)
                stu = st.session_state.student_answers_data[idx]
                answer = stu["text"]
                prompt = f"""
다음은 채점 기준입니다:
{rubric_text}

그리고 아래는 학생 답안입니다:
{answer}

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
                grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                with st.spinner("GPT가 채점 중입니다..."):
                    result = grading_chain.invoke({"input": prompt})
                    st.session_state.last_grading_result = result["text"]
                    st.session_state.last_selected_student = stu
                    st.success("✅ 채점 완료")

    if st.session_state.last_grading_result and st.session_state.last_selected_student:
        s = st.session_state.last_selected_student
        st.subheader(f"📋 채점 결과 - {s['name']} ({s['id']})")
        st.markdown(st.session_state.last_grading_result)

# -------------------- STEP 3: 피드백 기반 채점 기준 수정 --------------------
elif st.session_state.step == 3:
    rubric_key = f"rubric_{st.session_state.problem_filename}"
    if not st.session_state.problem_text:
        st.warning("STEP 1에서 문제를 먼저 업로드해주세요.")
    elif rubric_key not in st.session_state.generated_rubrics:
        st.warning("STEP 1에서 채점 기준을 먼저 생성해주세요.")
    else:
        st.subheader("📊 원본 채점 기준")
        st.markdown(st.session_state.generated_rubrics[rubric_key])
        if st.button("♻️ 피드백 반영"):
            feedback = st.session_state.feedback_text
            prompt = f"""
기존 채점 기준:
{st.session_state.generated_rubrics[rubric_key]}

피드백:
{feedback}

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
            feedback_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
            with st.spinner("GPT가 기준을 수정 중입니다..."):
                updated = feedback_chain.invoke({"input": prompt})
                st.session_state.modified_rubrics[rubric_key] = updated["text"]
                st.success("✅ 채점 기준 수정 완료")

        if rubric_key in st.session_state.modified_rubrics:
            st.subheader("🆕 수정된 채점 기준")
            st.markdown(st.session_state.modified_rubrics[rubric_key])


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
