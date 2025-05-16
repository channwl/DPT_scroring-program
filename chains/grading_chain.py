# grading_chain.py
# 이 파일은 LangChain 기반의 답안 채점 체인을 정의합니다.
# 채점 기준과 학생 답안을 기반으로 GPT가 마크다운 형식의 채점 결과를 출력합니다.

from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from config.llm_config import get_llm

# GPT 모델 초기화
llm = get_llm()

# 채점 체인은 메모리를 사용하지 않음 (단발성 평가)
grading_prompt_template = PromptTemplate.from_template("""
{input}
""")

grading_chain = LLMChain(
    llm=llm,
    prompt=grading_prompt_template
)

# 외부 호출용 래퍼 함수
def grade_answer(prompt: str) -> str:
    try:
        if not prompt.strip():
            raise ValueError("❗ 프롬프트가 비어 있습니다.")

        result = grading_chain.invoke({"input": prompt})
        return result.get("text", "❗ 응답에 'text' 키가 없습니다.")

    except Exception as e:
        # 오류 메시지를 Streamlit 로그 및 화면에 출력
        st.error("❌ 채점 중 오류가 발생했습니다.")
        st.exception(e)  # Streamlit에 전체 traceback 출력
        return f"[오류] {str(e)}"

