# file_info.py
# 이 파일은 파일명을 기반으로 학생의 이름과 학번을 추출하는 유틸 함수입니다.
# 정규표현식을 사용해 이름(한글)과 학번(숫자)을 구분해 반환합니다.

import os
import re

def sanitize_filename(filename):
    # 파일명에서 한글, 공백, 특수기호 제거 → 안정적인 영어+숫자만 남기기
    name = os.path.basename(filename)
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    return safe_name

def extract_info_from_filename(filename):
    """
    파일명을 기반으로 이름과 학번을 추출합니다.
    예: "202312345 김채점 기말과제.pdf" → ("김채점", "202312345")
    """
    # 👇 파일명 정규화 처리
    filename = sanitize_filename(filename)
    base_filename = os.path.splitext(filename)[0]

    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"

    name_candidates = re.findall(r'[가-힣]{2,5}', base_filename)
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}
    for name in name_candidates:
        if name not in exclude_words:
            return name, student_id

    return "UnknownName", student_id

