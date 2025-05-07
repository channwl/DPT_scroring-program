# step1_generate_rubric.py
# 이 파일은 STEP 1: 문제 업로드 및 채점 기준 생성을 위한 Streamlit UI 및 실행 로직을 포함합니다.

import streamlit as st
from utils.pdf_utils import extract_text_from_pdf
from utils.pdf_utils import extract_text_with_image_ocr
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from config.llm_config import get_llm
from langchain_core.prompts import PromptTemplate

def generate_rubric(problem_text: str) -> str:
    template = """
당신은 대학 기말고사를 채점하는 전문가 GPT입니다.

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
7. 사진 파일이 있으면 OCR로 인식해주세요.

이제 채점 기준을 생성하세요.
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
    
    #OCR 포함 텍스트 추출
    text_pages = extract_text_with_image_ocr(file_bytes)
    text = "\n\n".join(text_pages)
    
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
