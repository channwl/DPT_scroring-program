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
        model="gemini-2.5-pro-preview-03-25",  
        temperature=0.0,                          # 창의성 최소화 (정확한 채점)
        convert_system_message_to_human=True,
        generation_config={
            "max_output_tokens": 2048,            # 채점 결과 표 + 총평까지 충분한 길이
            "max_thought_tokens": 256,            # 내부 사고 토큰: 채점 판단에 적당
            "top_p": 0.9,                         # 확률 분포 누적값 (안정적이면서 약간 유연)
            "top_k": 1,                           # 확률 상위 k개만 고려 (결정적 출력)
            "stop_sequences": [],                 # 별도 중단 문장 없음
        }
    )


