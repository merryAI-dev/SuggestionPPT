#!/usr/bin/env python3
"""
CSV를 slides_data.json 형식으로 변환
리드문과 내용구성을 분리하고, 담당자 필드 추가
"""

import csv
import json
import re
from pathlib import Path


def parse_lead_content(raw_text: str) -> tuple[str, str]:
    """
    Lead 필드에서 리드문과 내용구성을 분리

    Returns:
        (리드문, 내용구성)
    """
    if not raw_text or not raw_text.strip():
        return "", ""

    text = raw_text.strip()

    # [리드문]과 [내용구성] 또는 [내용 구성] 패턴으로 분리
    lead = ""
    content = ""

    # 리드문 추출
    lead_match = re.search(r'\[리드문\]\s*(.*?)(?=\[내용\s*구성\]|\Z)', text, re.DOTALL)
    if lead_match:
        lead = lead_match.group(1).strip()

    # 내용구성 추출
    content_match = re.search(r'\[내용\s*구성\]\s*(.*)', text, re.DOTALL)
    if content_match:
        content = content_match.group(1).strip()

    # [리드문] 태그가 없는 경우 전체를 리드문으로 처리
    if not lead_match and not content_match:
        lead = text

    # 리드문에서 줄바꿈 제거 (한 문장으로)
    lead = re.sub(r'\s*\n\s*', ' ', lead).strip()

    return lead, content


def convert_csv_to_json(csv_path: str, output_path: str = None):
    """CSV를 JSON으로 변환"""

    if output_path is None:
        output_path = Path(csv_path).stem + "_slides.json"

    slides = []
    page_num = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # 분량 확인 (0이면 간지, 빈 값도 처리)
            quantity_str = row.get('분량', '').strip()
            quantity = int(quantity_str) if quantity_str.isdigit() else 0

            # 분량이 0이면 간지 페이지
            is_divider = (quantity == 0)

            # 담당자
            manager = row.get('담당', '').strip()

            # Chapter, Title, Subtitle (줄바꿈 제거)
            chapter = row.get('Chapter', '').strip()
            subtitle = re.sub(r'\s*\n\s*', ' ', row.get('Subtitle', '')).strip()
            title = re.sub(r'\s*\n\s*', ' ', row.get('Title', '')).strip()

            # Lead 파싱 (리드문/내용구성 분리)
            raw_lead = row.get('Lead', '')
            lead, content_structure = parse_lead_content(raw_lead)

            # 분량만큼 슬라이드 생성 (최소 1개)
            slide_count = max(1, quantity)

            for i in range(slide_count):
                page_num += 1

                slide = {
                    "page": page_num,
                    "chapter": chapter,
                    "title": title,
                    "subtitle": subtitle,
                    "lead": lead,
                    "content": content_structure,  # 내용구성
                    "manager": manager,  # 담당자
                    "is_divider": is_divider  # 간지 여부
                }

                slides.append(slide)

    # JSON 구조
    result = {
        "font_settings": {
            "chapter": {"name": "현대하모니 B", "size": 16, "bold": False, "color": "#000000"},
            "title": {"name": "현대하모니 B", "size": 16, "bold": False, "color": "#000000"},
            "subtitle": {"name": "현대하모니 M", "size": 16, "bold": False, "color": "#000000"},
            "lead": {"name": "현대하모니 L", "size": 13, "color": "#000000"},
            "content": {"name": "현대하모니 L", "size": 10, "color": "#333333"},
            "manager": {"name": "현대하모니 L", "size": 9, "color": "#666666"}
        },
        "slides": slides
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"변환 완료: {output_path}")
    print(f"총 {len(slides)}개 슬라이드 생성")

    # 통계
    dividers = sum(1 for s in slides if s.get('is_divider'))
    with_content = sum(1 for s in slides if s.get('content'))
    with_lead = sum(1 for s in slides if s.get('lead'))

    print(f"- 간지 페이지: {dividers}개")
    print(f"- 리드문 있는 슬라이드: {with_lead}개")
    print(f"- 내용구성 있는 슬라이드: {with_content}개")

    return result


if __name__ == "__main__":
    import sys

    csv_file = sys.argv[1] if len(sys.argv) > 1 else "26년(14기) H-온드림 제안서 마스터시트 - 보람 작업용.csv"
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    convert_csv_to_json(csv_file, output_file)
