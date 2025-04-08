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

# 마크다운 표 파싱 함수 개선
def parse_markdown_grading_table(text):
    # 마크다운 표 추출
    table_match = re.search(r"\| *채점 항목 *\|.*?\n\|[-\s|]+\n(\|.*?\n)+", text, re.DOTALL)
    if not table_match:
        # 표가 없을 경우 더 유연한 방식으로 다시 시도
        table_match = re.search(r"\|.*?채점 항목.*?\|.*?\n(\|.*?\n)+", text, re.DOTALL)
        if not table_match:
            raise ValueError("마크다운 표를 찾을 수 없습니다.")
    
    table_text = table_match.group()
    # 표 헤더와 구분선 제외하고 각 행을 처리
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    
    # 헤더 분석하여 열 이름 추출
    header = lines[0]
    header_cells = [cell.strip() for cell in header.strip('|').split('|')]
    
    # 구분선 건너뛰기
    data_lines = [line for line in lines[2:] if re.match(r'^\|.*\|$', line)]
    
    rows = []
    for line in data_lines:
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        if len(cells) == len(header_cells):
            row_dict = {header_cells[i]: cells[i] for i in range(len(header_cells))}
            rows.append(row_dict)
    
    # 총점 찾기
    total_score_match = re.search(r"총점[:：]?\s*(\d+)\s*점", text)
    total_score = int(total_score_match.group(1)) if total_score_match else None
    
    # 총평 찾기
    feedback_match = re.search(r"총평[:：]?\s*([^\n]+)", text)
    feedback = feedback_match.group(1).strip() if feedback_match else ""
    
    return rows, total_score, feedback

# 하이라이팅 함수 개선
def apply_highlight(text, evidence_list):
    highlighted_text = text
    
    # 답안 텍스트 정규화 (공백, 개행 등 처리)
    normalized_text = re.sub(r'\s+', ' ', text).strip()
    
    # 각 근거를 찾고 하이라이트 적용
    for idx, evidence_dict in enumerate(evidence_list):
        # 평가 근거 필드의 이름(채점 결과에 따라 '평가 근거' 또는 '세부 평가' 등으로 다를 수 있음)
        evidence_key = next((k for k in evidence_dict.keys() if '근거' in k or '평가' in k), None)
        if not evidence_key:
            continue
            
        evidence = evidence_dict[evidence_key]
        if pd.isna(evidence) or not evidence or len(str(evidence).strip()) < 5:
            continue
            
        # 근거 문장 정규화
        evidence_text = str(evidence).strip()
        normalized_evidence = re.sub(r'\s+', ' ', evidence_text)
        
        # 근거 문장 내 핵심 키워드 추출
        keywords = re.findall(r'[가-힣a-zA-Z0-9]{2,}', normalized_evidence)
        keywords = [k for k in keywords if len(k) > 1 and k not in ['있습니다', '하였습니다', '하였고', '있고', '했으며', '했습니다']]
        
        if not keywords:
            continue
            
        # 각 키워드에 대한 색상 지정
        color = f"hsl({(idx * 45) % 360}, 70%, 85%)"
        
        # 원본 문장에서 키워드 주변 문맥을 찾아 하이라이트
        for keyword in keywords:
            # 키워드를 포함하는 문장 찾기
            sentence_pattern = r'[^.!?]*' + re.escape(keyword) + r'[^.!?]*[.!?]'
            matches = re.finditer(sentence_pattern, normalized_text, re.IGNORECASE)
            
            for match in matches:
                sentence = match.group(0).strip()
                if len(sentence) > 10:  # 의미 있는 문장인지 확인
                    # 원본 텍스트에서 해당 문장 찾기
                    sentence_index = highlighted_text.find(sentence)
                    if sentence_index != -1:
                        tooltip = f"근거: {evidence_text}"
                        highlighted_sentence = f'<span style="background-color: {color}; padding: 2px; border-radius: 3px;" title="{tooltip}">{sentence}</span>'
                        highlighted_text = highlighted_text[:sentence_index] + highlighted_sentence + highlighted_text[sentence_index + len(sentence):]
    
    return highlighted_text.replace('\n', '<br>')

# STEP 4 개선
elif st.session_state.step == 4:
    if st.session_state.problem_text and st.session_state.problem_filename:
        rubric_key = f"rubric_{st.session_state.problem_filename}"
        # 수정된 채점 기준이 있으면 그것을 사용, 없으면 원본 사용
        rubric_text = st.session_state.modified_rubrics.get(rubric_key, st.session_state.generated_rubrics.get(rubric_key))

        if not rubric_text:
            st.warning("STEP 1에서 채점 기준을 먼저 생성해주세요.")
            if st.button("STEP 1로 이동"):
                st.session_state.step = 1
        elif not st.session_state.student_answers_data:
            st.warning("STEP 2에서 학생 답안을 먼저 업로드해주세요.")
            if st.button("STEP 2로 이동"):
                st.session_state.step = 2
        else:
            st.subheader("📊 채점 기준")
            st.markdown(rubric_text)
            
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("📥 전체 학생 채점 실행", use_container_width=True):
                    grading_chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
                    st.session_state.all_grading_results = []
                    st.session_state.highlighted_results = []
                    progress_bar = st.progress(0)
                    
                    # 진행 상황 표시를 위한 컨테이너
                    status_container = st.empty()
                    total_students = len(st.session_state.student_answers_data)

                    with st.spinner("GPT가 전체 학생을 채점 중입니다..."):
                        for i, stu in enumerate(st.session_state.student_answers_data):
                            name, sid, answer = stu["name"], stu["id"], stu["text"]
                            
                            # 진행 상황 표시
                            status_container.text(f"채점 중: {name}({sid}) - {i+1}/{total_students}")

                            # 채점 프롬프트 개선
                            prompt = f"""
다음은 채점 기준입니다:
{rubric_text}

아래는 학생({name}, {sid})의 답안입니다:
{answer}

이 기준에 따라 다음과 같은 형식으로 채점해 주세요. 

1. 반드시 정확히 마크다운 표 형식을 지켜 주세요.
2. '평가 근거' 열에는 학생 답안의 **구체적인 문장이나 내용**을 인용하여 채점 근거를 명시해주세요.
3. 평가 근거는 가능한 한 학생 답안에서 찾을 수 있는 구체적인 문장을 인용해야 합니다.

| 채점 항목 | 배점 | 부여 점수 | 평가 근거 |
|----------|-----|-----------|-----------|
| 이해도 | 10 | 8 | "학생이 작성한 '개념A는 B와 C로 구성된다'라는 문장에서 개념은 설명했지만 일부 용어 오용" |
| 논리성 | 5 | 5 | "학생이 작성한 '첫째... 둘째... 셋째...' 구조로 주장의 일관성을 유지함" |

총점: 13점  
총평: 전반적으로 잘 작성했지만 약간의 오해가 있습니다.
"""
                            try:
                                result = grading_chain.invoke({"input": prompt})
                                grading_text = result["text"]
                                
                                # 채점 표 파싱
                                table_rows, total_score, feedback = parse_markdown_grading_table(grading_text)
                                
                                # 하이라이팅 적용
                                highlighted_answer = apply_highlight(answer, table_rows)
                                
                                # 마크다운 테이블 재구성
                                if table_rows and len(table_rows) > 0:
                                    header_keys = table_rows[0].keys()
                                    markdown_table = "| " + " | ".join(header_keys) + " |\n"
                                    markdown_table += "|" + "|".join(["---" for _ in header_keys]) + "|\n"
                                    
                                    for row in table_rows:
                                        markdown_table += "| " + " | ".join([str(row.get(k, "")) for k in header_keys]) + " |\n"
                                    
                                    markdown_table += f"\n**총점: {total_score}점**\n\n**총평:** {feedback}"
                                else:
                                    markdown_table = grading_text
                                
                                # 결과 저장
                                st.session_state.highlighted_results.append({
                                    "name": name,
                                    "id": sid,
                                    "score": total_score,
                                    "feedback": feedback,
                                    "highlighted_text": highlighted_answer,
                                    "markdown_table": markdown_table,
                                    "text": answer,
                                    "raw_grading": grading_text  # 디버깅용 원본 채점 결과 저장
                                })
                                
                            except Exception as e:
                                st.error(f"{name}({sid})의 채점 결과 처리 중 오류 발생: {str(e)}")
                                st.code(result["text"] if 'result' in locals() else "결과 없음")
                                
                                # 오류가 발생해도 진행은 계속
                                st.session_state.highlighted_results.append({
                                    "name": name,
                                    "id": sid,
                                    "score": None,
                                    "feedback": f"채점 오류: {str(e)}",
                                    "highlighted_text": answer.replace('\n', '<br>'),
                                    "markdown_table": "채점 처리 중 오류가 발생했습니다.",
                                    "text": answer,
                                    "raw_grading": result["text"] if 'result' in locals() else "결과 없음"
                                })

                            # 진행 상황 업데이트
                            progress_bar.progress((i + 1) / total_students)

                        # 채점 완료 후 통계 계산
                        valid_scores = [r["score"] for r in st.session_state.highlighted_results if r["score"] is not None]
                        if valid_scores:
                            avg_score = sum(valid_scores) / len(valid_scores)
                            highest = max(valid_scores)
                            lowest = min(valid_scores)
                            status_container.text(f"채점 완료: 평균 {avg_score:.1f}점 (최고: {highest}점, 최저: {lowest}점)")
                        else:
                            status_container.text("채점 완료: 유효한 점수 없음")
                            
                        progress_bar.empty()
                        st.success(f"✅ 전체 학생({total_students}명) 채점 완료")
            
            # 채점 결과 표시 부분
            if st.session_state.highlighted_results:
                st.subheader("📈 점수 분포")
                
                # 점수 분포 시각화
                scores = [r["score"] for r in st.session_state.highlighted_results if r["score"] is not None]
                if scores:
                    fig, ax = plt.subplots(figsize=(8, 4))
                    
                    # 히스토그램
                    bins = range(0, max(scores) + 5, 5)  # 5점 단위로 구간 설정
                    ax.hist(scores, bins=bins, color='skyblue', edgecolor='black', alpha=0.7)
                    
                    # 평균선
                    mean_score = sum(scores) / len(scores)
                    ax.axvline(mean_score, color='red', linestyle='dashed', linewidth=1, label=f'평균: {mean_score:.1f}점')
                    
                    ax.set_xlabel('점수')
                    ax.set_ylabel('학생 수')
                    ax.set_title('학생 점수 분포')
                    ax.legend()
                    ax.grid(True, linestyle='--', alpha=0.7)
                    
                    # 그래프 표시
                    st.pyplot(fig)
                
                st.subheader("📋 전체 학생 채점 결과")
                
                # 정렬 옵션
                sort_options = ["이름순", "학번순", "점수 높은순", "점수 낮은순"]
                sort_method = st.radio("정렬 방식", sort_options, horizontal=True)
                
                # 결과 정렬
                sorted_results = st.session_state.highlighted_results.copy()
                if sort_method == "이름순":
                    sorted_results.sort(key=lambda x: x["name"])
                elif sort_method == "학번순":
                    sorted_results.sort(key=lambda x: x["id"])
                elif sort_method == "점수 높은순":
                    # None 값은 맨 뒤로
                    sorted_results.sort(key=lambda x: (x["score"] is None, -x["score"] if x["score"] is not None else 0))
                elif sort_method == "점수 낮은순":
                    # None 값은 맨 뒤로
                    sorted_results.sort(key=lambda x: (x["score"] is None, x["score"] if x["score"] is not None else float('inf')))
                
                # 학생 선택 옵션 생성
                student_options = [
                    (f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']}) - 채점 오류") 
                    for r in sorted_results
                ]
                
                # CSV 다운로드 기능
                if st.session_state.highlighted_results:
                    csv_data = []
                    for r in st.session_state.highlighted_results:
                        csv_data.append({
                            "이름": r['name'],
                            "학번": r['id'],
                            "점수": r['score'] if r['score'] is not None else "오류",
                            "총평": r['feedback']
                        })
                    
                    csv_df = pd.DataFrame(csv_data)
                    csv = csv_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        label="📊 채점 결과 CSV 다운로드",
                        data=csv,
                        file_name="채점결과.csv",
                        mime="text/csv",
                    )
                
                # 학생 선택 및 결과 표시
                selected_student = st.selectbox("🧑‍🎓 학생 선택", ["모든 학생 보기"] + student_options)
                
                for i, r in enumerate(sorted_results):
                    label = f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']}) - 채점 오류"
                    if selected_student == "모든 학생 보기" or selected_student == label:
                        st.markdown(f"### ✍️ {r['name']} ({r['id']}) {' - 총점: ' + str(r['score']) + '점' if r['score'] is not None else ' - 채점 오류'}")
                        st.markdown(r["markdown_table"])
                        
                        # 답안 표시 방식 개선
                        tabs = st.tabs(["🔍 하이라이팅된 답안", "📝 원본 답안", "🧾 채점 디버그"])
                        with tabs[0]:
                            if "<span style=" in r["highlighted_text"]:
                                st.markdown(r["highlighted_text"], unsafe_allow_html=True)
                                st.info("💡 하이라이트된 부분에 마우스를 올리면 해당 채점 근거를 볼 수 있습니다.")
                            else:
                                st.warning("하이라이트할 수 있는 근거를 찾지 못했습니다.")
                                st.markdown(r["highlighted_text"].replace('\n', '<br>'), unsafe_allow_html=True)
                                
                        with tabs[1]:
                            st.text_area(
                                f"원본 답안 - {r['name']} ({r['id']})",
                                value=r.get("text", ""),
                                height=400,
                                disabled=True,
                                key=f"text_area_{r['id']}_{i}"  # 고유 키 사용
                            )
                        
                        with tabs[2]:
                            st.code(r.get("raw_grading", "채점 정보 없음"))
                            
                        st.markdown("---")
