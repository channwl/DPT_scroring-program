# llm_config.py
# 이 파일은 LLM을 초기화하는 함수입니다.
# API 키는 streamlit의 secrets 기능을 통해 안전하게 불러옵니다.
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import streamlit as st

# @st.cache_resource 데코레이터를 추가하여 LLM 인스턴스를 캐싱합니다.
# hash_funcs를 명시적으로 지정하여 Streamlit이 캐싱 키를 정확하게 생성하도록 합니다.
# ChatGoogleGenerativeAI 객체는 직접 해시하기 어렵기 때문에,
# 캐싱 대상의 id()를 사용하거나, 아니면 단순히 이 함수가 의존하는 입력(API 키, 모델명 등)을
# 캐싱 키의 일부로 간주하도록 유도할 수 있습니다. 여기서는 기본 동작을 따르되,
# LLM 인스턴스 자체가 아닌, 인스턴스를 생성하는 로직을 캐싱하는 효과를 가집니다.
@st.cache_resource(show_spinner="LLM을 초기화하는 중입니다...")
def get_llm():
    # Google API 키 설정
    # secrets를 사용하는 경우, secrets 변경 시 캐시가 무효화됩니다.
    genai.configure(api_key=st.secrets["google"]["API_KEY"])
    print("--- LLM 인스턴스 초기화 중 ---") # 이 메시지는 한 번만 출력되어야 합니다.
    # 채점 시스템에 최적화된 LLM 반환
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-04-17",
        temperature=0,
        convert_system_message_to_human=True
    )

# 이 부분은 ConversationSummaryMemory 초기화 시 get_llm()을 호출하는 app.py에서 처리해야 합니다.
# ConversationSummaryMemory 자체도 캐싱 대상이 될 수 있습니다.
# 하지만 메모리는 세션별 상태를 가져야 하므로, st.session_state에 직접 할당하는 것이 일반적입니다.
# LLM 인스턴스만 캐싱하도록 합니다.

# grading_chain.py 등 다른 파일에서는 get_llm() 호출 시 캐싱된 인스턴스를 사용하게 됩니다.
