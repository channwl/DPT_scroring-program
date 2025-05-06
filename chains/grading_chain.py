# grading_chain.py
# 이 파일은 LangChain 기반의 답안 채점 체인을 정의합니다.
# 채점 기준과 학생 답안을 기반으로 LLM이 마크다운 형식의 채점 결과를 출력합니다.

from langchain.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from config.llm_config import get_llm
import streamlit as st
import functools
import time

# 단일 LLM 인스턴스 및 체인 재사용
_grading_chain = None

# 결과 캐싱을 위한 딕셔너리
_result_cache = {}

def get_grading_chain():
    """
    채점 체인을 초기화하고 반환합니다. 한 번만 생성하고 재사용합니다.
    """
    global _grading_chain
    
    if _grading_chain is None:
        # GPT 모델 초기화 - 전역 인스턴스 재사용
        llm = get_llm()
        
        # 채점 체인 템플릿 - 메모리를 사용하지 않음
        grading_prompt_template = PromptTemplate.from_template("{input}")
        
        # 채점 체인 초기화
        _grading_chain = LLMChain(
            llm=llm,
            prompt=grading_prompt_template
        )
    
    return _grading_chain

# 요청 제한을 위한 속도 제어 기능
def rate_limit(min_interval=0.5):
    """API 요청 속도를 제한하는 데코레이터"""
    last_request_time = [0]  # 마지막 요청 시간을 추적하기 위한 리스트
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            elapsed = current_time - last_request_time[0]
            
            # 마지막 요청 이후 min_interval 초가 지나지 않았다면 대기
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            
            result = func(*args, **kwargs)
            last_request_time[0] = time.time()
            return result
        return wrapper
    return decorator

# 결과 캐싱 및 속도 제한 적용
@rate_limit(min_interval=0.5)  # API 호출 간 최소 0.5초 간격 유지
def grade_answer(prompt: str) -> str:
    """
    외부 호출용 래퍼 함수 - 캐싱 기능 포함
    동일한 질문에 대해 중복 API 호출을 방지합니다.
    """
    # 간단한 해시 키 생성 (실제 구현에서는 더 견고한 해시 사용 권장)
    cache_key = hash(prompt)
    
    # 캐시된 결과가 있으면 반환
    if cache_key in _result_cache:
        return _result_cache[cache_key]
    
    # 캐시된 결과가 없으면 API 호출
    chain = get_grading_chain()
    result = chain.invoke({"input": prompt})
    
    # 결과 캐싱 및 반환
    _result_cache[cache_key] = result["text"]
    return result["text"]
