# grading_chain.py
# 이 파일은 LangChain 기반의 답안 채점 체인을 정의합니다.
# 채점 기준과 학생 답안을 기반으로 GPT가 마크다운 형식의 채점 결과를 출력합니다.

from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from config.llm_config import get_llm

# GPT 모델 초기화
llm = get_llm()

# 프롬프트 정의
grading_prompt_template = PromptTemplate.from_template("""
{input}
""")

# RunnableSequence 방식으로 체인 구성
grading_chain = grading_prompt_template | llm | StrOutputParser()

# 외부 호출용 래퍼 함수
def grade_answer(prompt: str) -> str:
    return grading_chain.invoke({"input": prompt})

