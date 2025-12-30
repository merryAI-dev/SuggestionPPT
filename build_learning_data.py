#!/usr/bin/env python3
"""
학습 데이터 빌드 스크립트
inputdata/의 PPTX/PDF 파일들을 분석하여 learning_data/patterns.json을 생성합니다.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from extractor import extract_all_from_directory, analyze_slide_structure


def analyze_chapter_format(all_data: list) -> dict:
    """챕터 형식 패턴을 분석합니다."""
    formats = defaultdict(int)

    for doc in all_data:
        if doc["format"] != "pptx":
            continue

        for slide in doc["content"].get("slides", []):
            for text in slide.get("texts", []):
                # 다양한 챕터 패턴 감지
                if re.match(r"^\d{2}\.\s*.+", text):
                    formats["##. 한글명"] += 1
                elif re.match(r"^\d+\.\s*.+", text):
                    formats["#. 한글명"] += 1
                elif re.match(r"^[IVX]+\.\s*.+", text):
                    formats["로마숫자. 한글명"] += 1

    # 가장 많이 사용된 형식
    if formats:
        most_common = max(formats.items(), key=lambda x: x[1])
        return {"pattern": most_common[0], "count": most_common[1]}

    return {"pattern": "##. 한글명", "count": 0}


def analyze_text_lengths(all_data: list) -> dict:
    """제목과 리드 텍스트의 평균 길이를 분석합니다."""
    title_lengths = []
    lead_lengths = []

    for doc in all_data:
        if doc["format"] != "pptx":
            continue

        for slide in doc["content"].get("slides", []):
            structure = analyze_slide_structure(slide)

            if structure["title"]:
                title_lengths.append(len(structure["title"]))
            if structure["lead"]:
                lead_lengths.append(len(structure["lead"]))

    return {
        "title_avg_length": int(sum(title_lengths) / len(title_lengths)) if title_lengths else 15,
        "lead_avg_length": int(sum(lead_lengths) / len(lead_lengths)) if lead_lengths else 50
    }


def is_quality_example(example: dict) -> bool:
    """예시가 품질 기준을 충족하는지 확인합니다."""
    title = example.get("title", "")
    lead = example.get("lead", "")

    # 노이즈 패턴 체크
    noise_patterns = [
        r"^[‹›\d#]+$",
        r"ⓒ\s*\d{4}",
        r"©\s*\d{4}",
        r"All rights reserved",
        r"^[IVXivx]+$",
        r"^\d+$",
    ]

    for pattern in noise_patterns:
        if re.search(pattern, title, re.IGNORECASE) or re.search(pattern, lead, re.IGNORECASE):
            return False

    # 최소 길이 체크
    if len(title) < 5 or len(lead) < 10:
        return False

    # title과 lead가 너무 유사하면 제외
    if title == lead:
        return False

    return True


def extract_examples_by_type(all_data: list) -> dict:
    """문서 유형별 고품질 예시를 추출합니다."""
    examples_by_type = defaultdict(list)

    for doc in all_data:
        if doc["format"] != "pptx":
            continue

        doc_type = doc["type"]

        # 처음 20개 슬라이드에서 검색 (더 많은 후보 확보)
        for slide in doc["content"].get("slides", [])[:20]:
            structure = analyze_slide_structure(slide)

            if structure["title"] and structure["lead"]:
                example = {
                    "chapter": structure["chapter"] or "",
                    "title": structure["title"].strip(),
                    "lead": structure["lead"][:150].strip()  # 리드문 더 길게 유지
                }

                # 품질 체크
                if not is_quality_example(example):
                    continue

                # 중복 방지 (title 기준)
                existing_titles = [e["title"] for e in examples_by_type[doc_type]]
                if example["title"] not in existing_titles:
                    examples_by_type[doc_type].append(example)

    # 각 유형별 최대 5개 예시만 유지
    return {k: v[:5] for k, v in examples_by_type.items()}


def analyze_typical_sections(all_data: list) -> dict:
    """문서 유형별 전형적인 섹션 구조를 분석합니다."""
    sections_by_type = defaultdict(list)

    for doc in all_data:
        if doc["format"] != "pptx":
            continue

        doc_type = doc["type"]
        chapters = []

        for slide in doc["content"].get("slides", []):
            for text in slide.get("texts", []):
                # 챕터 패턴 추출
                match = re.match(r"^[\d]{1,2}\.\s*(.+)$", text)
                if match:
                    chapter_name = match.group(1).strip()
                    if chapter_name and chapter_name not in chapters:
                        chapters.append(chapter_name)

        if chapters:
            sections_by_type[doc_type].extend(chapters)

    # 각 유형별 자주 등장하는 섹션 추출
    result = {}
    for doc_type, sections in sections_by_type.items():
        # 빈도 계산
        section_count = defaultdict(int)
        for s in sections:
            section_count[s] += 1

        # 상위 8개 섹션
        top_sections = sorted(section_count.items(), key=lambda x: -x[1])[:8]
        result[doc_type] = [s[0] for s in top_sections]

    return result


def calculate_avg_slides(all_data: list) -> dict:
    """문서 유형별 평균 슬라이드 수를 계산합니다."""
    slides_by_type = defaultdict(list)

    for doc in all_data:
        if doc["format"] == "pptx":
            slides_by_type[doc["type"]].append(doc["content"]["slide_count"])
        elif doc["format"] == "pdf":
            slides_by_type[doc["type"]].append(doc["content"]["page_count"])

    return {
        doc_type: int(sum(counts) / len(counts))
        for doc_type, counts in slides_by_type.items()
        if counts
    }


def build_learning_data(input_dir: str, output_path: str):
    """학습 데이터를 빌드하고 저장합니다."""
    print("=" * 50)
    print("학습 데이터 빌드 시작")
    print("=" * 50)

    # 1. 모든 파일 추출
    all_data = extract_all_from_directory(input_dir)

    if not all_data:
        print("추출된 데이터가 없습니다.")
        return

    # 2. 패턴 분석
    print("\n패턴 분석 중...")

    chapter_format = analyze_chapter_format(all_data)
    text_lengths = analyze_text_lengths(all_data)
    typical_sections = analyze_typical_sections(all_data)
    avg_slides = calculate_avg_slides(all_data)
    examples = extract_examples_by_type(all_data)

    # 3. 학습 데이터 구조화
    learning_data = {
        "metadata": {
            "source_count": len(all_data),
            "sources": [d["source"] for d in all_data]
        },
        "style_patterns": {
            "chapter_format": chapter_format["pattern"],
            "title_avg_length": text_lengths["title_avg_length"],
            "lead_avg_length": text_lengths["lead_avg_length"]
        },
        "document_types": {}
    }

    # 문서 유형별 데이터 정리
    for doc_type in set(d["type"] for d in all_data):
        learning_data["document_types"][doc_type] = {
            "avg_slides": avg_slides.get(doc_type, 20),
            "typical_sections": typical_sections.get(doc_type, []),
            "examples": examples.get(doc_type, [])
        }

    # 4. 저장
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(learning_data, f, ensure_ascii=False, indent=2)

    print(f"\n학습 데이터 저장 완료: {output_path}")
    print(f"- 총 {len(all_data)}개 문서 분석")
    print(f"- {len(learning_data['document_types'])}개 문서 유형 감지")

    # 요약 출력
    print("\n문서 유형별 통계:")
    for doc_type, info in learning_data["document_types"].items():
        print(f"  [{doc_type}]")
        print(f"    평균 슬라이드: {info['avg_slides']}개")
        print(f"    전형적 섹션: {', '.join(info['typical_sections'][:5]) if info['typical_sections'] else '없음'}")
        print(f"    예시 수: {len(info['examples'])}개")


if __name__ == "__main__":
    build_learning_data(
        input_dir="inputdata",
        output_path="learning_data/patterns.json"
    )
