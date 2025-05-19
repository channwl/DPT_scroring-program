import os
import re

def extract_info_from_filename(filename):
    base_filename = os.path.splitext(os.path.basename(filename))[0]
    id_match = re.search(r'\d{6,10}', base_filename)
    student_id = id_match.group() if id_match else "UnknownID"

    name_candidates = re.findall(r'[가-힣]{2,5}', base_filename)
    exclude_words = {"기말", "중간", "과제", "시험", "수업", "레포트", "제출", "답안"}

    for name in name_candidates:
        if name not in exclude_words:
            return name, student_id

    # fallback
    return "UnknownName", student_id
