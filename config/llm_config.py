# llm_config.py
# 이 파일은 LLM을 초기화하는 함수입니다.
# API 키는 streamlit의 secrets 기능을 통해 안전하게 불러옵니다.

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI

def get_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-04-17",
        temperature=0,
        convert_system_message_to_human=True,
        generation_config={
            "max_output_tokens": 2048,           # 생성 토큰 수 제한
            "max_thought_tokens": 256,           # 내부 사고 토큰 수
            "top_p": 1,
            "top_k": 1,
            "stop_sequences": [],
        }
    )


