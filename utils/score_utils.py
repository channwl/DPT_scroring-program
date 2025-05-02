# score_utils.py
# 이 파일은 GPT 채점 결과에서 총점, 근거 문장, 총평을 추출하는 유틸 함수입니다.

import re

def extract_total_score(grading_text):
    """
    채점 결과 텍스트에서 총점을 추출합니다.
    예: "**총점: 23점**" → 23
    """
    match = re.search(r'총점[:：]?\s*(\d+)\s*점', grading_text)
    return int(match.group(1)) if match else None

def extract_evidence_sentences(grading_text):
    """
    채점 결과에서 근거 문장(Evidence) 항목만 따로 추출합니다.
    각 항목당 최대 3개 문장을 정규표현식으로 분리
    """
    evidence_sentences = []
    evidence_match = re.search(r'\*\*근거 문장:\*\*\s*([\s\S]*?)(?=\*\*총점|\Z)', grading_text)
    if evidence_match:
        evidence_text = evidence_match.group(1)
        for line in evidence_text.split('\n'):
            match = re.search(r'"(.*?)"', line)
            if match:
                evidence_sentences.append(match.group(1))
    return evidence_sentences

def extract_summary_feedback(grading_text):
    """
    채점 결과에서 총평 텍스트만 추출합니다.
    예: "**총평:** ..." → "..."
    """
    feedback_match = re.search(r'\*\*총평:\*\*\s*(.*?)(?=\Z|\n\n)', grading_text)
    return feedback_match.group(1) if feedback_match else ""
