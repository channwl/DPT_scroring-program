# llm_config.py
import streamlit as st
import google.generativeai as genai
from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI

@lru_cache(maxsize=1)          # ① 테스트·스크립트 실행에서도 한 번만
def _make_llm():
    genai.configure(api_key=st.secrets["google"]["API_KEY"])
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0,
        streaming=True,         # ② 토큰이 오자마자 바로 화면에
        convert_system_message_to_human=True,
    )

@st.cache_resource(show_spinner=False)     # ③ Streamlit 세션당 딱 한 번
def get_llm():
    return _make_llm()

# 선택 - Warm-up(권장): 앱 실행 직후 1-token dummy 호출 → 콜드스타트 0 초화
def warm_up():
    _ = get_llm().invoke({"messages": [{"role":"user","content":"ping"}]})
