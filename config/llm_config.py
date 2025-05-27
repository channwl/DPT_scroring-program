# llm_config.py
# 이 파일은 GPT (OpenAI 기반 LLM)를 초기화하는 함수입니다.
# API 키는 streamlit의 secrets 기능을 통해 안전하게 불러옵니다.

from langchain.chat_models import ChatOpenAI
import streamlit as st

def get_llm():
    """
    GPT 모델 객체를 반환합니다. 기본 모델은 'gpt-4.1-mini'이며, 온도는 0으로 설정되어 있습니다.
    """
    return ChatOpenAI(
        openai_api_key=st.secrets["openai"]["API_KEY"],
        model_name="o3-2025-04-16",
        temperature=0
    )
