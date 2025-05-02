# step1_generate_rubric.py
# 이 파일은 STEP 1: 문제 업로드 및 채점 기준 생성을 위한 Streamlit UI 및 실행 로직을 포함합니다.

import streamlit as st
from utils.pdf_utils import extract_text_from_pdf
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from config.llm_config import get_llm


def generate_rubric(problem_text: str) -> str:
    """
    문제 내용을 기반으로 GPT가 채점 기준 마크다운 표를 생성합니다.
    """
    prompt = f"""당신은 대학 시험을 채점하는 GPT입니다.

다음 문제에 대한 채점 기준을 작성해 주세요.

문제:
{problem_text}

📌 작성 규칙 (아래 형식을 반드시 그대로 지킬 것!)
1. **반드시 마크다운 표**로 작성해주세요. 정확히 아래 구조를 따라야 합니다.
2. **헤더는 `| 채점 항목 | 배점 | 세부 기준 |` 이고**, 그 아래 구분선은 `|---|---|---|`로 시작해야 합니다.
3. **각 행은 반드시 |로 시작하고 |로 끝나야 하며**, 총 3개의 열을 포함해야 합니다.
4. 각 항목의 세부 기준은 **구체적으로**, **한글로만** 작성해주세요. 영어는 절대 사용하지 마세요.
5. 표 아래에 반드시 "**배점 총합: XX점**"을 작성하세요.

예시 형식:
| 채점 항목 | 배점 | 세부 기준 |
|---------|-----|---------|
| 항목 1 | 5점 | 세부 기준 설명 |
| 항목 2 | 10점 | 세부 기준 설명 |

**배점 총합: 15점**
"""
    llm = get_llm()
    chain = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{input}"))
    result = chain.invoke({"input": prompt})
    return result["text"]


def run_step1():
    st.subheader("📄 STEP 1: 문제 업로드 및 채점 기준 생성")

    problem_pdf = st.file_uploader("📄 문제 PDF 업로드", type="pdf", key="problem_upload")

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
            if st.button("📐 채점 기준 생성"):
                st.session_state.rubric_memory.clear()
                with st.spinner("GPT가 채점 기준을 생성 중입니다..."):
                    result = generate_rubric(text)
                    st.session_state.generated_rubrics[rubric_key] = result
                    st.success("✅ 채점 기준 생성 완료")
        else:
            if st.button("📐 채점 기준 재생성"):
                confirm = st.checkbox("⚠️ 이미 생성된 채점 기준이 있습니다. 재생성하시겠습니까?")
                if confirm:
                    st.session_state.rubric_memory.clear()
                    with st.spinner("GPT가 채점 기준을 재생성 중입니다..."):
                        result = generate_rubric(text)
                        st.session_state.generated_rubrics[rubric_key] = result
                        st.success("✅ 채점 기준 재생성 완료")

        if rubric_key in st.session_state.generated_rubrics:
            st.subheader("📊 채점 기준")
            st.markdown(st.session_state.generated_rubrics[rubric_key])
