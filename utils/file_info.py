import os
import re
import urllib.parse

def extract_info_from_filename(filename):
    """
    파일명에서 이름(한글)과 학번(숫자)을 추출합니다.
    예: "DIGB225_Assignment_2_202312345_김채점.pdf" → ("김채점", "202312345")
    """
    # URL 인코딩된 파일명을 디코딩
    decoded_filename = urllib.parse.unquote(filename)
    
    # 파일명 정규화 (경로에서 파일명만 추출)
    base_filename = os.path.splitext(os.path.basename(decoded_filename))[0]
    
    # 학번 추출 (6~10자리 숫자)
    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"
    
    # 이름 추출 (한글 2~5자)
    name_candidates = re.findall(r'[가-힣]{2,5}', base_filename)
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}
    
    # 후보 이름 중 제외 단어가 아닌 첫 번째 이름 반환
    for name in name_candidates:
        if name not in exclude_words:
            return name, student_id
    
    return "UnknownName", student_id

def sanitize_filename(filename):
    """
    파일명에서 특수문자를 제거하고 안전한 형태로 변환
    """
    # URL 인코딩된 파일명을 디코딩
    decoded_filename = urllib.parse.unquote(filename)
    
    # 파일명과 확장자 분리
    base_name, extension = os.path.splitext(os.path.basename(decoded_filename))
    
    # 파일명에서 안전하지 않은 문자 제거 또는 대체
    sanitized_base = re.sub(r'[\\/*?:"<>|]', '_', base_name)
    
    return sanitized_base + extension
