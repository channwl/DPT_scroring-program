# llm_config.py
# 이 파일은 LLM을 초기화하는 함수입니다.
# API 키는 streamlit의 secrets 기능을 통해 안전하게 불러옵니다.

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import streamlit as st

def get_llm():
    # Google API 키 설정
    genai.configure(api_key=st.secrets["google"]["API_KEY"])

    # 채점 시스템에 최적화된 LLM 반환
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",  
        temperature=0,                          
        convert_system_message_to_human=True
    )


