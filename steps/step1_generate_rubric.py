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
    prompt = f"""당신은 대학 시험 문제에 대해 **문제별 세분화된 채점 기준을 작성하는 전문가 GPT**입니다.

다음의 지침에 따라 정확하게 채점 기준을 생성하세요:

1. 각 문제를 "문제 1", "문제 2", "문제 3"처럼 구분하세요.  
2. 각 문제에 대해 별도의 **마크다운 표**를 작성하세요.  
3. 표의 구조는 반드시 다음과 같이 고정합니다:  
   | 채점 항목 | 배점 | 세부 기준 |  
   |---|---|---|  
   | … | … | … |  
4. 각 표 아래에 "**배점 총합: X점**"을 반드시 작성하세요. (예: **배점 총합: 10점**)  
5. **세부 기준은 반드시 구체적으로 작성**하고, **절대 영어를 사용하지 마세요.**
6. 모든 문제에 대한 채점 기준을 누락 없이 작성하세요.
7. 모든 문제를 다 작성한 후, **전체 배점 총합**을 다음 형식으로 작성하세요:  
   → 전체 배점 총합: XX점

---

🧾 출력 예시:

문제 1

| 채점 항목 | 배점 | 세부 기준 |
|---|---|---|
| 핵심 개념 설명 | 5점 | 관련 이론을 정확하게 기술했는가 |
| 예시 활용 | 5점 | 실제 사례를 적절히 인용했는가 |

**배점 총합: 10점**

문제 2  
...

→ 전체 배점 총합: XX점

---

지금부터 위 지침을 따라 **완전한 채점 기준**을 생성하세요.
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
