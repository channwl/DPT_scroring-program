# file_info.py
# 이 파일은 파일명을 기반으로 학생의 이름과 학번을 추출하는 유틸 함수입니다.
# 정규표현식을 사용해 이름(한글)과 학번(숫자)을 구분해 반환합니다.

import os
import re

def extract_info_from_filename(filename):
    """
    파일명에서 이름, 학번, 원본 파일명을 추출합니다.
    - 이름: 한글 2~5자 중 제외어가 아닌 것
    - 학번: 가장 긴 8~10자리 숫자를 우선적으로 추출
    - 원본 파일명: 확장자를 제외한 전체 이름
    """
    base_filename = os.path.splitext(os.path.basename(filename))[0]

    # 8~10자리 숫자 중 가장 마지막 등장하는 것을 학번으로 간주 (보통 맨 뒤에 있음)
    id_matches = re.findall(r'\d{8,10}', base_filename)
    student_id = id_matches[-1] if id_matches else "UnknownID"

    # 한글 이름 후보 추출
    name_candidates = re.findall(r'[가-힣]{2,5}', base_filename)
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안", "Assignment"}

    # 제외어 제거 후 학번 포함 문자열 제거
    valid_names = [
        name for name in name_candidates
        if name not in exclude_words and name not in student_id
    ]

    # 가장 뒤에 등장한 유효한 한글 문자열을 이름으로 추정
    name = valid_names[-1] if valid_names else "UnknownName"

    return name, student_id, base_filename
