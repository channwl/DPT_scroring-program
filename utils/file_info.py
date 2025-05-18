import os
import re

# ✅ 정규화 함수 통합
def sanitize_filename(filename):
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)

def extract_info_from_filename(filename):
    """
    파일명에서 이름(한글)과 학번(숫자)을 추출합니다.
    자동으로 sanitize 처리도 포함합니다.
    예: "DIGB225_Assignment_2_202312345_김채점.pdf" → ("김채점", "202312345")
    """
    # ✅ filename 정규화 먼저 적용 (공백, 한글 등 제거)
    safe_filename = sanitize_filename(filename)
    base_filename = os.path.splitext(os.path.basename(safe_filename))[0]

    # 학번 추출 (6~10자리 숫자)
    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"

    # 이름 추출 (한글 2~5자) → 원본에서 찾는 게 나음 (safe_filename은 한글 제거됨)
    original_base = os.path.splitext(os.path.basename(filename))[0]
    name_candidates = re.findall(r'[가-힣]{2,5}', original_base)
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}

    for name in name_candidates:
        if name not in exclude_words:
            return name, student_id

    return "UnknownName", student_id
