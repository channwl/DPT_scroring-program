# rubric_chain.py
# 이 파일은 LangChain 기반의 채점 기준 생성을 담당하는 체인을 정의합니다.
# 문제 내용을 입력받아 마크다운 형식의 채점 기준표를 생성하는 GPT 프롬프트 체인입니다.

from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from langchain.memory import ConversationSummaryMemory
from config.llm_config import get_llm

# LLM 초기화 및 메모리 설정
llm = get_llm()
memory = ConversationSummaryMemory(
    llm=llm,
    memory_key="history",
    return_messages=True
)

# 채점 기준 생성을 위한 프롬프트 템플릿
rubric_prompt_template = PromptTemplate.from_template("""
{history}
{input}
""")

# 체인 정의
rubric_chain = LLMChain(
    llm=llm,
    prompt=rubric_prompt_template,
    memory=memory
)

# 외부에서 사용할 수 있도록 함수로 래핑

def generate_rubric(problem_text: str) -> str:
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
    result = rubric_chain.invoke({"input": prompt})
    return result["text"]

