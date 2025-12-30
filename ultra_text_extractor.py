#!/usr/bin/env python3
"""
Ultra Think 모드: XML 추출 + Claude API 구조 분류
빠른 속도로 Chapter/Title/Subtitle/Lead 분류
"""

import json
import os
from pathlib import Path
from typing import List, Dict
import anthropic


def extract_xml_texts(pptx_path: str) -> List[Dict]:
    """
    기존 XML 기반 텍스트 추출 (integrated_pptx_checker.py의 로직 사용)
    """
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    import re

    texts = []

    try:
        with ZipFile(pptx_path, 'r') as zf:
            slide_files = sorted([
                f for f in zf.namelist()
                if f.startswith('ppt/slides/slide') and f.endswith('.xml')
            ], key=lambda x: int(re.search(r'slide(\d+)', x).group(1)))

            for slide_idx, slide_file in enumerate(slide_files):
                slide_num = slide_idx + 1

                with zf.open(slide_file) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    ns = {
                        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                        'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
                    }

                    slide_texts = []

                    # 각 paragraph별로 텍스트 추출
                    for sp in root.findall('.//p:sp', ns):
                        txBody = sp.find('.//p:txBody', ns)
                        if txBody is None:
                            continue

                        for para in txBody.findall('a:p', ns):
                            para_text = []
                            for t_elem in para.findall('.//a:t', ns):
                                if t_elem.text:
                                    para_text.append(t_elem.text)

                            text = ''.join(para_text).strip()
                            if text and len(text) > 2:
                                slide_texts.append(text)

                    texts.append({
                        'slide': slide_num,
                        'texts': slide_texts,
                        'source': 'xml'
                    })

    except Exception as e:
        print(f"❌ XML 추출 실패: {e}")
        return []

    return texts


def similarity(a: str, b: str) -> float:
    """두 문자열의 유사도 계산 (0~1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def merge_texts(xml_results: List[Dict], vision_results: List[Dict]) -> List[Dict]:
    """
    XML과 Vision 추출 결과를 병합하여 최대 정확도 달성

    병합 전략:
    1. XML과 Vision 결과를 슬라이드별로 매칭
    2. 중복 제거 (유사도 0.85 이상인 텍스트는 동일로 간주)
    3. Vision에만 있는 텍스트 추가 (XML이 놓친 텍스트)
    4. XML에만 있는 텍스트도 유지

    Returns:
        [
            {
                "slide": 1,
                "texts": ["텍스트1", "텍스트2", ...],
                "xml_count": N,
                "vision_count": M,
                "merged_count": K,
                "vision_only": [...],  # Vision에만 있던 텍스트
                "xml_only": [...]      # XML에만 있던 텍스트
            },
            ...
        ]
    """
    merged_results = []

    for i in range(max(len(xml_results), len(vision_results))):
        slide_num = i + 1

        xml_data = xml_results[i] if i < len(xml_results) else {"texts": []}
        vision_data = vision_results[i] if i < len(vision_results) else {"texts": []}

        xml_texts = xml_data.get("texts", [])
        vision_texts = vision_data.get("texts", [])

        # 병합 로직
        merged_texts = []
        vision_only = []
        xml_only = []

        # 1. XML 텍스트를 기준으로 시작
        for xml_text in xml_texts:
            merged_texts.append(xml_text)

            # Vision에 유사한 텍스트가 있는지 확인
            found_in_vision = False
            for vision_text in vision_texts:
                if similarity(xml_text, vision_text) >= 0.85:
                    found_in_vision = True
                    break

            if not found_in_vision:
                xml_only.append(xml_text)

        # 2. Vision에만 있는 텍스트 추가
        for vision_text in vision_texts:
            # XML에 유사한 텍스트가 없는지 확인
            found_in_xml = False
            for xml_text in xml_texts:
                if similarity(vision_text, xml_text) >= 0.85:
                    found_in_xml = True
                    break

            if not found_in_xml:
                merged_texts.append(vision_text)
                vision_only.append(vision_text)

        merged_results.append({
            "slide": slide_num,
            "texts": merged_texts,
            "xml_count": len(xml_texts),
            "vision_count": len(vision_texts),
            "merged_count": len(merged_texts),
            "vision_only": vision_only,
            "xml_only": xml_only
        })

    return merged_results


def _classify_structure_with_claude(xml_results: List[Dict], api_key: str = None) -> List[Dict]:
    """
    XML 추출 결과를 Claude API로 구조 분류

    Args:
        xml_results: [{"slide": 1, "texts": [...]}, ...]
        api_key: Anthropic API 키

    Returns:
        [{"page": 1, "chapter": "...", "title": "...", ...}, ...]
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수를 설정하거나 api_key를 전달해주세요")

    client = anthropic.Anthropic(api_key=api_key)

    # XML 결과를 JSON으로 변환
    input_data = []
    for result in xml_results:
        input_data.append({
            "page": result["slide"],
            "texts": result["texts"]
        })

    # Claude API 호출
    prompt = f"""다음은 PPTX 슬라이드에서 추출한 텍스트입니다.
각 슬라이드의 텍스트를 **순서와 길이**를 기반으로 구조 분류해주세요.

**분류 규칙:**
1. **Chapter**: 첫 번째로 나오는 짧은 텍스트 (5-15자, 숫자 포함 가능)
   - 예: "01. 발견", "PART 1", "채용", "Insight"

2. **Title**: 다음에 나오는 중간 길이 텍스트 (10-40자)
   - 예: "H-온드림 2026년 제안서", "임팩트 스타트업 생태계"

3. **Subtitle**: 제목 다음의 중간~긴 텍스트 (15-60자)
   - 예: "사회문제 해결을 위한 혁신적 접근"

4. **Lead**: 본문 시작 부분의 긴 텍스트 (25자 이상)
   - 예: "H-온드림은 지난 5년간 임팩트 스타트업 생태계에서..."

5. **Contents**: 나머지 모든 텍스트를 배열로

**중요:**
- 해당 항목이 없으면 빈 문자열("")로 표시
- 순서대로 분류 (첫 번째 짧은 것 → Chapter, 다음 중간 것 → Title...)
- Contents는 모든 나머지 텍스트를 포함
- Chapter가 없으면 Title부터 시작 가능

**입력 데이터:**
```json
{json.dumps(input_data, ensure_ascii=False, indent=2)}
```

**출력 형식 (JSON만):**
```json
{{
  "slides": [
    {{
      "page": 1,
      "chapter": "01. 섹션" 또는 "",
      "title": "슬라이드 제목" 또는 "",
      "subtitle": "부제목" 또는 "",
      "lead": "리드 문장" 또는 "",
      "contents": ["내용1", "내용2", ...]
    }},
    ...
  ]
}}
```

JSON만 출력하세요."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16384,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    # 응답 파싱
    response_text = message.content[0].text
    return _parse_claude_response(response_text, xml_results)


def _parse_claude_response(response_text: str, xml_results: List[Dict]) -> List[Dict]:
    """
    Claude API 응답 파싱

    Args:
        response_text: Claude API 응답
        xml_results: 원본 XML 추출 결과 (raw_texts 추가용)

    Returns:
        [{"page": N, "chapter": "...", ...}, ...]
    """
    # JSON 추출
    json_str = response_text.strip()

    if '```json' in json_str:
        json_str = json_str.split('```json')[1].split('```')[0].strip()
    elif '```' in json_str:
        json_str = json_str.split('```')[1].split('```')[0].strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 파싱 실패: {e}")
        print(f"   응답 샘플: {response_text[:200]}...")
        # Fallback: XML 결과만 반환
        return _fallback_xml_results(xml_results)

    results = []

    for slide_data in data.get('slides', []):
        page = slide_data.get('page', 1)

        # 원본 XML 텍스트 추가
        raw_texts = []
        for xml_result in xml_results:
            if xml_result['slide'] == page:
                raw_texts = xml_result['texts']
                break

        results.append({
            "page": page,
            "chapter": slide_data.get("chapter", ""),
            "title": slide_data.get("title", ""),
            "subtitle": slide_data.get("subtitle", ""),
            "lead": slide_data.get("lead", ""),
            "contents": slide_data.get("contents", []),
            "raw_texts": raw_texts,
            "text_count": len(raw_texts)
        })

    return results


def _fallback_xml_results(xml_results: List[Dict]) -> List[Dict]:
    """
    Claude 파싱 실패 시 XML 결과만 반환
    """
    results = []
    for result in xml_results:
        results.append({
            "page": result["slide"],
            "chapter": "",
            "title": "",
            "subtitle": "",
            "lead": "",
            "contents": result["texts"],
            "raw_texts": result["texts"],
            "text_count": len(result["texts"])
        })
    return results


def ultra_extract_texts(pptx_path: str, api_key: str = None) -> Dict:
    """
    Ultra Think 모드로 PPTX에서 텍스트 추출
    XML 추출 → Claude API 구조 분류

    Args:
        pptx_path: PPTX 파일 경로
        api_key: Anthropic API 키

    Returns:
        {
            "file": "파일명",
            "total_slides": N,
            "slides": [
                {
                    "page": 1,
                    "chapter": "...",
                    "title": "...",
                    "subtitle": "...",
                    "lead": "...",
                    "contents": [...],
                    "raw_texts": [...]
                },
                ...
            ]
        }
    """
    pptx_path = Path(pptx_path)

    print("\n" + "=" * 70)
    print("🚀 Ultra Think 모드: XML + Claude API 구조 분류")
    print("=" * 70)
    print(f"파일: {pptx_path.name}\n")

    # 1. XML 추출 (빠름)
    print("📋 Stage 1: XML 텍스트 추출")
    print("-" * 70)
    xml_results = extract_xml_texts(str(pptx_path))
    xml_total = sum(len(r['texts']) for r in xml_results)
    print(f"✅ XML 추출 완료: {len(xml_results)}개 슬라이드, {xml_total}개 텍스트\n")

    # 2. Claude API로 구조 분류 (빠름)
    print("🤖 Stage 2: Claude API 구조 분류")
    print("-" * 70)
    print("   Chapter / Title / Subtitle / Lead 자동 분류 중...")

    structured_results = _classify_structure_with_claude(xml_results, api_key)
    print(f"✅ 구조 분류 완료: {len(structured_results)}개 슬라이드\n")

    result = {
        "file": str(pptx_path),
        "total_slides": len(structured_results),
        "slides": structured_results
    }

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Ultra Think 텍스트 추출")
        print("-" * 40)
        print("사용법: python ultra_text_extractor.py input.pptx [output.json]")
        print()
        print("예시:")
        print("  python ultra_text_extractor.py presentation.pptx")
        print("  python ultra_text_extractor.py presentation.pptx result.json")
        sys.exit(0)

    pptx_file = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        result = ultra_extract_texts(pptx_file)

        # JSON 저장
        if output_json:
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 결과 저장: {output_json}")

        # 슬라이드별 요약
        print("\n" + "=" * 70)
        print("📊 슬라이드별 구조 분류 결과")
        print("=" * 70)

        for slide_data in result['slides'][:5]:  # 처음 5개만
            print(f"\n[페이지 {slide_data['page']}]")
            print(f"  Chapter: \"{slide_data.get('chapter', '')}\"")
            print(f"  Title: \"{slide_data.get('title', '')}\"")
            print(f"  Subtitle: \"{slide_data.get('subtitle', '')}\"")
            lead = slide_data.get('lead', '')
            print(f"  Lead: \"{lead[:50]}...\"" if len(lead) > 50 else f"  Lead: \"{lead}\"")
            print(f"  Contents: {len(slide_data.get('contents', []))}개 항목")

        if len(result['slides']) > 5:
            print(f"\n... 외 {len(result['slides']) - 5}개 슬라이드")

        print("\n✅ Ultra Think 추출 완료!")

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
