# text_cleaning.py
# 이 파일은 추출된 텍스트를 문단 단위로 정리하거나 들여쓰기를 적용하는 유틸 함수들을 포함합니다.

import re
import html

def clean_text_postprocess(text):
    """
    PDF에서 추출한 텍스트를 문단별로 정리하고 불필요한 줄을 제거합니다.
    """
    lines = text.split('\n')
    cleaned = []
    prev_blank = True  # 문단 시작 여부 체크용

    for line in lines:
        line = line.strip()
        # 스킵할 줄: 페이지 번호, 과제 제목, 학번 줄 등
        if re.search(r'DIGB226|Final Take-Home Exam|^\s*-\s*\d+\s*-$', line):
            continue
        if re.search(r'^\d{9,10}\s*[\uAC00-\uD7A3]+$', line):
            continue
        if not line:
            prev_blank = True
            continue

        # 새 문단 시작 시 빈 줄 추가
        if prev_blank:
            cleaned.append("")  # 빈 줄 넣기
        cleaned.append(line)
        prev_blank = False

    return "\n".join(cleaned)

def apply_indentation(text):
    """
    문단에 들여쓰기 및 스타일 적용하여 HTML 렌더링용으로 변환
    """
    lines = text.split('\n')
    html_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            html_lines.append("<br>")
            continue
        if re.match(r'^\d+(\.\d+)*\s', line):  # 1. / 1.1 / 2. 같은 제목
            html_lines.append(f"<p style='margin-bottom: 5px; font-weight: bold;'>{html.escape(line)}</p>")
        else:
            html_lines.append(f"<p style='padding-left: 20px; margin: 0;'>{html.escape(line)}</p>")
    return "\n".join(html_lines)
