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
    result = grading_chain.invoke({"input": prompt})
    return result["text"]
