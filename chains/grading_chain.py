from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import StrOutputParser
from config.llm_config import get_llm

llm = get_llm()

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "당신은 대학 시험을 채점하는 GPT입니다."),
    ("user", "{input}")
])

grading_chain = prompt_template | llm | StrOutputParser()

def grade_answer(prompt: str) -> str:
    try:
        if not prompt.strip():
            return "[오류] 프롬프트가 비어 있습니다."

        result = grading_chain.invoke({"input": prompt})
        return result
    except Exception as e:
        return f"[오류] GPT 호출 실패: {str(e)}"
