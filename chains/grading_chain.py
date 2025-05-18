from langchain_core.prompts import ChatPromptTemplate
from config.llm_config import get_llm

llm = get_llm()

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "당신은 대학 시험을 채점하는 전문가 GPT입니다."),
    ("user", "{input}")
])

def grade_answer(prompt: str) -> str:
    try:
        chain = prompt_template | llm  # StrOutputParser 제거
        result = chain.invoke({"input": prompt})

        # OpenAIChat returns BaseMessage
        if hasattr(result, "content"):
            return result.content
        elif isinstance(result, str):
            return result
        return str(result)
    except Exception as e:
        return f"[오류] GPT 호출 실패: {str(e)}"
