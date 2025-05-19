import streamlit as st
import tempfile
import os
import urllib.parse

from utils.pdf_utils import extract_text_from_pdf
from utils.file_info import sanitize_filename  # 이전에 수정한 파일에서 가져옴
from config.llm_config import get_llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser

# LangChain 기반 GPT 채점 기준 생성 체인 정의
llm = get_llm()
rubric_prompt_template = ChatPromptTemplate.from_messages([
    ("system", "당신은 대학 시험을 채점하는 전문가 GPT입니다."),
    ("user", "{input}")
])
rubric_chain = rubric_prompt_template | llm | StrOutputParser()

# ✅ 채점 기준 생성
def generate_rubric(problem_text: str) -> str:
    prompt = f"""
당신은 대학 시험을 채점하는 전문가 GPT입니다.
다음은 PDF에서 추출한 **실제 시험 문제 본문입니다.**
- 각 문제의 시작은 "1.", "2.", ..., "7."으로 되어 있습니다.
- 각 문제의 끝에는 "(4 points)", "(5 points)"처럼 배점이 괄호로 표시되어 있습니다.
---
📄 문제 본문:
{problem_text}
---
위 본문을 기반으로, 다음 지침에 따라 문제별 **채점 기준 마크다운 표**를 생성하세요.
📌 출력 지침:
1. 문제 번호와 배점을 그대로 반영하세요.
   - 예: 문제 1 (4점)
2. 각 문제는 아래 마크다운 표 형식을 따릅니다:
   | 채점 항목 | 배점 | 세부 기준 |
   |---|---|---|
   | ... | ... | ... |
3. 표 아래에는 다음 문장을 추가하세요:
   **배점 총합: X점**
4. 모든 문제 기준 작성 후 마지막에 아래와 같이 전체 점수를 작성하세요:
   → 전체 배점 총합: 30점
5. 모든 출력은 **한글로만** 작성하세요. 영어는 절대 사용하지 마세요.
6. 문제 수를 줄이거나 임의로 문제를 묶으면 안 됩니다.
이제 채점 기준을 생성하세요.
"""
    try:
        result = rubric_chain.invoke({"input": prompt})
        return result
    except Exception as e:
        st.error("❌ 채점 기준 생성 중 오류가 발생했습니다.")
        st.exception(e)
        return f"[오류] {str(e)}"

# ✅ STEP 1 실행 함수
def run_step1():
    st.subheader("📄 STEP 1: 문제 업로드 및 채점 기준 생성")
    problem_pdf = st.file_uploader("📄 문제 PDF 업로드", type="pdf", key="problem_upload")
    
    if problem_pdf:
        try:
            # 원본 파일명 저장 (디코딩)
            original_filename = urllib.parse.unquote(problem_pdf.name)
            
            # 🔐 안전한 파일명 생성 (file_info.py의 sanitize_filename 사용)
            safe_name = sanitize_filename(original_filename)
            st.session_state.problem_filename = safe_name
            
            # ✅ 임시 파일에 저장하여 한글 경로 우회
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(problem_pdf.getbuffer())  # getbuffer() 사용
                tmp_path = tmp_file.name
                
            # ✅ 문제 텍스트 추출
            text = extract_text_from_pdf(tmp_path)
            
            # 임시 파일 삭제
            try:
                os.unlink(tmp_path)
            except:
                pass  # 삭제 실패해도 계속 진행
                
            st.session_state.problem_text = text
            rubric_key = f"rubric_{safe_name}"
            
            st.subheader("📃 문제 내용")
            if not text.strip():
                st.warning("⚠️ PDF에서 텍스트가 추출되지 않았습니다.")
            else:
                st.write(text)
                
            if rubric_key not in st.session_state.generated_rubrics:
                if st.button("📐 채점 기준 생성"):
                    if not hasattr(st.session_state, 'rubric_memory'):
                        st.session_state.rubric_memory = {}
                    st.session_state.rubric_memory.clear()
                    
                    with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                        result = generate_rubric(text)
                        st.session_state.generated_rubrics[rubric_key] = result
                        st.success("✅ 채점 기준 생성 완료")
            else:
                if st.button("📐 채점 기준 재생성"):
                    confirm = st.checkbox("⚠️ 이미 생성된 채점 기준이 있습니다. 재생성하시겠습니까?")
                    if confirm:
                        if not hasattr(st.session_state, 'rubric_memory'):
                            st.session_state.rubric_memory = {}
                        st.session_state.rubric_memory.clear()
                        
                        with st.spinner("GPT가 채점 기준을 재생성 중입니다..."):
                            result = generate_rubric(text)
                            st.session_state.generated_rubrics[rubric_key] = result
                            st.success("✅ 채점 기준 재생성 완료")
                            
            if rubric_key in st.session_state.generated_rubrics:
                st.subheader("📊 채점 기준")
                st.markdown(st.session_state.generated_rubrics[rubric_key])
                
        except Exception as e:
            st.error(f"파일 처리 중 오류가 발생했습니다: {str(e)}")
            st.exception(e)
