# grading_chain.py
import streamlit as st
from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from config.llm_config import get_llm

_PROMPT = PromptTemplate.from_template("{input}")

def _get_chain():
    if "grading_chain" not in st.session_state:
        st.session_state.grading_chain = LLMChain(llm=get_llm(), prompt=_PROMPT)
    return st.session_state.grading_chain

def grade_answer(prompt: str) -> str:
    return _get_chain().invoke({"input": prompt})["text"]
