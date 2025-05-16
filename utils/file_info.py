# file_info.py
# 이 파일은 파일명을 기반으로 학생의 이름과 학번을 추출하는 유틸 함수입니다.
# 정규표현식을 사용해 이름(한글)과 학번(숫자)을 구분해 반환합니다.

import os
import re

def extract_info_from_filename(filename):
    """
    파일명을 기반으로 이름과 학번을 추출합니다.
    예: "202312345 김채점 기말과제.pdf" → ("김채점", "202312345")
    """
    base_filename = os.path.splitext(os.path.basename(filename))[0]

    # 학번 추출 (6~10자리 숫자)
    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"

    # 이름 후보 추출 (한글 2~5글자) + 제외 단어 필터링
    name_candidates = [part for part in re.findall(r'[가-힣]{2,5}', base_filename) if part not in student_id]
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}
    for name in name_candidates:
        if name not in exclude_words:
            return name, student_id

    return "UnknownName", student_id
