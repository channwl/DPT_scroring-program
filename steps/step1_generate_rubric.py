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
    prompt = fprompt = f"""당신은 대학 시험을 채점하는 GPT입니다.

다음 문제에 대한 **세분화된 채점 기준**을 작성해 주세요.

📌 작성 규칙:
1. 각 문제에 대해 별도로 표를 만드세요. (문제 1, 문제 2, … 순서 유지)
2. 각 표는 반드시 다음 구조로 작성합니다:
   - 헤더: `| 채점 항목 | 배점 | 세부 기준 |`
   - 구분선: `|---|---|---|`
   - 각 행: `|`로 시작하고 `|`로 끝나며, 정확히 3열로 구성
3. 문제마다 배점 합계를 반드시 작성하세요.
   - 예: `**배점 총합: 4점**`
4. 세부 기준은 구체적이고 명확하게 설명해야 합니다.
5. **한글로만 작성**하고 영어는 절대 사용하지 마세요.

📘 예시 형식:
### 문제 1
| 채점 항목 | 배점 | 세부 기준 |
|-----------|------|------------|
| 개념 정의 | 1점 | 용어를 정확하게 정의하였는가 |
| 예시 설명 | 1점 | 적절한 예시를 통해 설명했는가 |

**배점 총합: 2점**

---

📄 문제 내용:
{text}
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
