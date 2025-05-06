# llm_config.py
# 이 파일은 LLM을 초기화하는 함수입니다.
# API 키는 streamlit의 secrets 기능을 통해 안전하게 불러옵니다.

import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import streamlit as st
import functools

# LLM 인스턴스 캐싱 - 전역 변수를 사용하여 LLM을 한 번만 초기화
_LLM_INSTANCE = None

@functools.lru_cache(maxsize=1)
def get_llm():
    """
    LLM 인스턴스를 반환하는 함수 - 메모이제이션(memoization) 패턴 적용
    한 번만 초기화하고 재사용하도록 캐싱됨
    """
    global _LLM_INSTANCE
    
    if _LLM_INSTANCE is None:
        # Google API 키 설정
        genai.configure(api_key=st.secrets["google"]["API_KEY"])
        
        # 채점 시스템에 최적화된 LLM 반환
        _LLM_INSTANCE = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",  # 속도와 성능의 균형을 위한 모델
            temperature=0,             # 일관된 결과를 위해 온도 0 사용
            convert_system_message_to_human=True,
            max_retries=2,             # 재시도 횟수 제한
            request_timeout=60,        # 타임아웃 설정
            streaming=False            # 배치 처리에는 스트리밍이 불필요
        )
    
    return _LLM_INSTANCE
