import streamlit as st
import PyPDF2
import random
import re
import io
import os
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate

#Streamlit 페이지 설정
st.set_page_config(page_title="AI 채점 시스템", layout="wide")
st.title("🎓 AI 기반 자동 채점 시스템 - by DPT")


# GPT 연결 및 초기화
llm = ChatOpenAI(
    openai_api_key=st.secrets["openai"]["API_KEY"],
    model_name="gpt-4o",
    temperature=0
)

#세션 상태 초기화 함수
#페이지가 새로고침 될때마다 변수를 잃어버리기 때문에, 다음과 같은 변수를 session_state에 넣어줌
#값이 유지되는 결과가 나타남
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
        "last_selected_student": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value #이 부분
            
initialize_session_state()

#LangChain 프롬포트 및 체인 설정
#rubric_chain : 채점 기준을 생성할때 사용하는 체인
prompt_template = PromptTemplate.from_template("{history}\n{input}")
rubric_chain = LLMChain(
    llm=llm,
    prompt=prompt_template,
    memory=st.session_state.rubric_memory
)

# PDF 텍스트 추출
def extract_text_from_pdf(pdf_data):
    if isinstance(pdf_data, bytes):
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
    else:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_data.read()))
    return "".join([page.extract_text() or "" for page in reader.pages])

#파일 이름 추출
def extract_info_from_filename(filename):
    base_filename = os.path.splitext(filename)[0]
    
    # 파일명을 언더스코어(_)로 분리
    parts = base_filename.split('_')
    
    # 마지막 두 부분이 학번과 이름일 가능성이 높음
    if len(parts) >= 2:
        # 마지막 부분이 한글 이름인지 확인
        if re.match(r'^[가-힣]{2,5}$', parts[-1]):
            student_name = parts[-1]
        else:
            # 한글 이름 패턴 찾기
            name_match = re.search(r'[가-힣]{2,5}', parts[-1])
            student_name = name_match.group() if name_match else "UnknownName"
        
        # 뒤에서 두 번째 부분이 학번인지 확인 (숫자로만 구성)
        if len(parts) >= 3 and re.match(r'^\d{6,10}$', parts[-2]):
            student_id = parts[-2]
        else:
            # 학번 패턴 찾기
            id_match = re.search(r'\d{6,10}', base_filename)
            student_id = id_match.group() if id_match else "UnknownID"
            
        return student_name, student_id
    
    # 언더스코어 분리로 처리되지 않는 경우를 위한 backup 처리
    # 학번 추출 (6-10자리 숫자)
    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"
    
    # 이름 추출 (2-5자 한글)
    name_match = re.search(r'[가-힣]{2,5}', base_filename)
    student_name = name_match.group() if name_match else "UnknownName"
    
    return student_name, student_id

#여러 학생 PDF를 읽고, 이름/학번/답안 텍스트를 저장
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

# 사이드바
with st.sidebar:
    st.markdown("## 📘 채점 흐름")

    if st.button("1️⃣ 문제 업로드 및 채점 기준 생성"):
        st.session_state.step = 1
    if st.button("2️⃣ 학생 답안 업로드 및 무작위 채점"):
        st.session_state.step = 2
    if st.button("3️⃣ 교수자 피드백 입력"):
        st.session_state.step = 3

    st.markdown("### 📝 교수자 피드백", unsafe_allow_html=True)
    feedback = st.text_area("채점 기준 수정 피드백", value=st.session_state.feedback_text, key="sidebar_feedback")
    
    # 피드백 텍스트 업데이트
    st.session_state.feedback_text = feedback

    st.markdown("---")
    st.caption("🚀 본 시스템은 **DPT 팀**이 개발한 교수자 지원 도구입니다.")
    st.caption("채점 기준 수립과 일관된 채점을 돕기 위해 설계되었습니다.")

# 사용법 안내
with st.expander("ℹ️ 사용법 보기"):
    st.markdown("""
### 📝 사용법 안내

이 시스템은 교수자의 채점 업무를 보조하기 위해 만들어졌습니다.  
아래의 3단계를 따라 사용하시면 됩니다.

---

#### STEP 1: 문제 업로드 및 채점 기준 생성
1. 문제 PDF를 업로드합니다.
2. `📐 채점 기준 생성` 버튼을 클릭하면, GPT가 자동으로 채점 기준을 생성해줍니다.
3. 생성된 기준은 마크다운 표로 확인할 수 있습니다.

---

#### STEP 2: 학생 답안 업로드 및 무작위 채점
1. 여러 학생의 PDF 답안 파일을 업로드합니다.
2. `🎯 무작위 채점 실행` 버튼을 클릭하면, 한 명의 학생 답안을 GPT가 자동으로 채점해줍니다.
3. 채점 결과는 항목별 점수와 간단한 피드백이 포함된 표로 출력됩니다.

---

#### STEP 3: 교수자 피드백 입력 및 채점 기준 수정
1. 사이드바에 있는 `📝 교수자 피드백` 입력란에 개선하고 싶은 내용을 작성합니다.
2. `♻️ 피드백 반영` 버튼을 누르면, GPT가 수정된 채점 기준을 새로 생성해줍니다.

---

💡 이 시스템은 채점 기준 수립과 일관된 평가를 도와줍니다.  
🚀 GPT-4o 모델을 기반으로 하고 있으며, 채점 결과는 참고용입니다.
""")


# 단계 안내 및 버튼
st.markdown(f"### 현재 단계: STEP {st.session_state.step}")

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
