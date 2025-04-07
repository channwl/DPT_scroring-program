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
elif st.session_state.step == 4:
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

            # 하이라이팅 함수 정의 - 개선된 버전
            def apply_highlight(text, evidence_data):
                """
                학생 답안에서 평가 근거가 된 부분을 하이라이팅하고 채점 항목과 연결
                """
                import re
                highlighted_text = text
                
                # 줄바꿈 보존을 위해 임시 치환
                text_for_processing = text.replace('\n', '§LINE_BREAK§')
                
                # 각 채점 항목에 대해 근거 텍스트 하이라이팅
                for idx, item in enumerate(evidence_data):
                    criterion = item.get("criterion", "")
                    evidence = item.get("evidence", "")
                    given_score = item.get("given_score", 0)
                    max_score = item.get("max_score", 0)
                    
                    if evidence and len(evidence) > 5:  # 충분히 긴 텍스트만 처리
                        # 고유한 색상 생성 (HSL 색상 사용)
                        hue = (idx * 30) % 360
                        color = f"hsl({hue}, 80%, 85%)"
                        
                        # 툴팁에 표시할 정보
                        tooltip = f"{criterion} ({given_score}/{max_score}점)"
                        
                        # 정확한 일치 시도
                        evidence_processed = evidence.replace('\n', '§LINE_BREAK§')
                        if evidence_processed in text_for_processing:
                            # 정확한 일치가 있을 경우
                            replacement = f'<span style="background-color: {color}; padding: 2px; border-radius: 3px;" title="{tooltip}">{evidence}</span>'
                            text_for_processing = text_for_processing.replace(evidence_processed, f'§HIGHLIGHT_{idx}§')
                            highlighted_text = highlighted_text.replace(evidence, replacement)
                        else:
                            # 정확한 일치가 없을 경우 유사 텍스트 탐색
                            try:
                                # 특수문자 이스케이프 처리 및 공백 패턴 수정
                                pattern_text = re.escape(evidence_processed).replace('\\ ', '\\s+').replace('§LINE_BREAK§', '\\s*')
                                pattern = re.compile(pattern_text, re.DOTALL)
                                
                                # 정규식으로 유사한 텍스트 찾기
                                matched_texts = pattern.findall(text_for_processing)
                                
                                if matched_texts:
                                    for match in matched_texts:
                                        # 원래 텍스트로 변환
                                        original_match = match.replace('§LINE_BREAK§', '\n')
                                        replacement = f'<span style="background-color: {color}; padding: 2px; border-radius: 3px;" title="{tooltip}">{original_match}</span>'
                                        highlighted_text = highlighted_text.replace(original_match, replacement)
                            except Exception as e:
                                st.warning(f"하이라이팅 처리 중 오류 발생: {str(e)}")
                
                # 최종 텍스트에서 줄바꿈 HTML로 변환
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
                        
                        # GPT에게 채점 및 근거 문장 추출 요청 - 개선된 프롬프트
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
1. "evidence" 필드에는 반드시 학생 답안에서 실제로 찾을 수 있는 텍스트를 그대로 복사해서 넣어주세요.
2. 원문의 텍스트를 정확히 복사하세요. 단어를 바꾸거나 요약하지 마세요.
3. 근거를 찾을 수 없는 경우에만 "evidence" 필드를 비워두세요.
4. 채점 항목별로 관련된 모든 중요 문장을 찾아 "evidence" 필드에 기록해주세요.
5. 모든 JSON 필드 이름과 구조를 정확히 지켜주세요.
6. JSON만 반환해주세요. 다른 설명은 필요 없습니다.
"""
                        # GPT 호출
                        result = grading_chain.invoke({"input": prompt})
                        
                        try:
                            # 향상된 JSON 파싱
                            import re
                            # 코드 블록에서 JSON 추출 시도
                            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', result["text"])
                            if json_match:
                                json_content = json_match.group(1)
                            else:
                                # 코드 블록이 없으면 텍스트에서 직접 JSON 추출
                                json_start = result["text"].find("{")
                                json_end = result["text"].rfind("}")
                                if json_start != -1 and json_end != -1:
                                    json_content = result["text"][json_start:json_end+1]
                                else:
                                    raise ValueError("JSON 형식을 찾을 수 없습니다")
                                    
                            # JSON 파싱
                            data = json.loads(json_content)
                            
                            # 하이라이팅 적용 (grading_details 전체를 전달)
                            grading_details = data.get("grading_details", [])
                            highlighted_answer = apply_highlight(answer, grading_details)
                            
                            # 마크다운 테이블 생성
                            markdown_table = "| 채점 항목 | 배점 | 부여 점수 | 평가 내용 |\n"
                            markdown_table += "|---------|-----|---------|----------|\n"
                            
                            for detail in grading_details:
                                criterion = detail.get("criterion", "")
                                max_score = detail.get("max_score", 0)
                                given_score = detail.get("given_score", 0)
                                explanation = detail.get("explanation", "")
                                
                                markdown_table += f"| {criterion} | {max_score}점 | {given_score}점 | {explanation} |\n"
                            
                            # 총점 추가
                            total_score = data.get("total_score", 0)
                            markdown_table += f"\n**총점: {total_score}점**\n\n**피드백:** {data.get('feedback', '')}"
                            
                            # 결과 저장
                            st.session_state.highlighted_results.append({
                                "name": name,
                                "id": sid,
                                "score": total_score,
                                "feedback": data.get("feedback", ""),
                                "highlighted_text": highlighted_answer,
                                "markdown_table": markdown_table,
                                "grading_details": grading_details
                            })
                            
                            # 원본 JSON 응답도 저장
                            st.session_state.all_grading_results.append({
                                "name": name, 
                                "id": sid,
                                "data": data
                            })
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
                
                # 정렬 옵션
                sort_options = ["이름순", "학번순", "점수 높은순", "점수 낮은순"]
                sort_method = st.radio("정렬 방식", sort_options, horizontal=True)
                
                # 정렬 적용
                sorted_results = st.session_state.highlighted_results.copy()
                if sort_method == "이름순":
                    sorted_results.sort(key=lambda x: x["name"])
                elif sort_method == "학번순":
                    sorted_results.sort(key=lambda x: x["id"])
                elif sort_method == "점수 높은순":
                    sorted_results.sort(key=lambda x: x["score"] if x["score"] is not None else -1, reverse=True)
                elif sort_method == "점수 낮은순":
                    sorted_results.sort(key=lambda x: x["score"] if x["score"] is not None else float('inf'))
                
                # 학생 선택 필터 생성
                student_options = [(f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']})")
                                   for r in sorted_results]
                selected_student = st.selectbox("🧑‍🎓 학생 선택", ["모든 학생 보기"] + student_options)
                
                scores = []
                
                # 선택된 학생 또는 모든 학생 결과 표시
                for r in sorted_results:
                    student_label = f"{r['name']} ({r['id']}) - {r['score']}점" if r['score'] is not None else f"{r['name']} ({r['id']})"
                    
                    if selected_student == "모든 학생 보기" or selected_student == student_label:
                        st.markdown(f"### ✍️ {r['name']} ({r['id']}) - 총점: {r['score']}점")
                        
                        # 마크다운 테이블로 채점 결과 표시
                        st.markdown(r["markdown_table"])
                        
                        # 학생 답안 보기와 하이라이팅 보기를 분리하여 선택 가능하게 함
                        tabs = st.tabs(["🔍 하이라이팅된 답안", "📝 원본 답안"])
                        
                        with tabs[0]:
                            st.markdown(r["highlighted_text"], unsafe_allow_html=True)
                            st.info("💡 하이라이트된 부분 위에 마우스를 올리면 해당 채점 항목과 점수를 볼 수 있습니다.")
                        
                        with tabs[1]:
                            st.text_area("원본 답안", value=r.get("text", ""), height=300, disabled=True)
                        
                        # 교수자 피드백 입력 기능 추가
                        feedback_key = f"professor_feedback_{r['id']}"
                        professor_feedback = st.text_area(
                            "📝 교수자 피드백 (선택사항)",
                            value=st.session_state.get(feedback_key, ""),
                            key=feedback_key,
                            height=100
                        )
                        
                        # 피드백 저장 기능
                        if st.button("피드백 저장", key=f"save_feedback_{r['id']}"):
                            st.session_state[feedback_key] = professor_feedback
                            st.success("✅ 피드백이 저장되었습니다.")
                        
                        st.markdown("---")
                        
                        if r["score"] is not None:
                            scores.append(r["score"])
