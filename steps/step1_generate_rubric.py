# step1_generate_rubric.py
# 이 파일은 STEP 1: 문제 업로드 및 채점 기준 생성을 위한 Streamlit UI 및 실행 로직을 포함합니다.

import streamlit as st
from utils.pdf_utils import extract_text_from_pdf
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from config.llm_config import get_llm
from langchain_core.prompts import PromptTemplate

def generate_rubric(problem_text: str) -> str:
    template = """
당신은 대학 시험 문제에 대해 **문제별 세분화된 채점 기준을 작성하는 전문가 GPT**입니다.

아래 문제 본문을 읽고, 각 문제에 대해 **정확하고 구체적인 채점 기준 마크다운 표**를 생성하세요.

📄 문제 본문:
{problem_text}

📌 작성 지침:
1. 문제 번호와 배점은 문제 본문에서 **정확히 추출하여 반영**하세요.
   ...
"""

    prompt = PromptTemplate(
        input_variables=["problem_text"],
        template=template
    )

    llm = get_llm()
    chain = LLMChain(llm=llm, prompt=prompt)
    result = chain.invoke({"problem_text": problem_text})

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
