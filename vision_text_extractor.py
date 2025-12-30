#!/usr/bin/env python3
"""
Claude Vision API를 사용한 이미지 텍스트 추출
"""

import os
import base64
import tempfile
from pathlib import Path
from typing import List, Dict
import anthropic
from PyPDF2 import PdfReader, PdfWriter
import re


def extract_text_from_pdf(pdf_path: str, api_key: str = None, pages_per_chunk: int = 20) -> List[Dict]:
    """
    Claude Vision API로 PDF에서 텍스트 추출 (모든 페이지, 청크 단위 처리)

    Args:
        pdf_path: PDF 파일 경로
        api_key: Anthropic API 키
        pages_per_chunk: 한 번에 처리할 페이지 수 (기본 20)

    Returns:
        [
            {"page": 1, "texts": [...], "text_count": N},
            ...
        ]
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수를 설정하거나 api_key를 전달해주세요")

    # PDF 총 페이지 수 확인
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    print(f"📄 PDF 분석: 총 {total_pages}페이지")
    print(f"   청크 크기: {pages_per_chunk}페이지씩 처리")

    all_results = []
    client = anthropic.Anthropic(api_key=api_key)

    # 청크 단위로 분할 처리
    for chunk_start in range(0, total_pages, pages_per_chunk):
        chunk_end = min(chunk_start + pages_per_chunk, total_pages)
        chunk_num = (chunk_start // pages_per_chunk) + 1
        total_chunks = (total_pages + pages_per_chunk - 1) // pages_per_chunk

        print(f"\n🔍 청크 {chunk_num}/{total_chunks} 처리 중 (페이지 {chunk_start + 1}-{chunk_end})...")

        # 청크 PDF 생성
        writer = PdfWriter()
        for page_num in range(chunk_start, chunk_end):
            writer.add_page(reader.pages[page_num])

        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            writer.write(tmp_file)

        try:
            # 청크 PDF를 base64로 인코딩
            with open(tmp_path, 'rb') as f:
                pdf_data = base64.standard_b64encode(f.read()).decode('utf-8')

            # 단일 프롬프트: 상단 영역만 구조화, 나머지는 콘텐츠로 몰아서 처리
            prompt = f"""이 PDF 슬라이드에서 각 페이지의 텍스트를 추출해주세요.
(이 청크는 원본 PDF의 페이지 {chunk_start + 1}부터 {chunk_end}까지입니다)

**추출 규칙:**
1. **상단 영역 (페이지 상위 30%)만 구조화 추출:**
   - Chapter: 좌상단의 짧은 텍스트 (5-10자, 숫자 포함 가능)
   - Title: 중앙 상단의 큰 제목 텍스트 (10-30자)
   - Subtitle: 제목 바로 아래 부제목 (15-40자)
   - Lead: 본문 시작 부분의 첫 문단/리드 문장 (25자 이상)

2. **나머지 영역 (페이지 하위 70%):**
   - 모든 텍스트를 contents 배열에 한 번에 담기
   - 개별 텍스트를 나누지 말고 전체 내용을 문자열 배열로 반환

3. **해당 영역에 텍스트가 없으면 빈 문자열("")로 표2시**

**출력 형식 (JSON만 출력):**
```json
{{
  "pages": [
    {{
      "page": 1,
      "chapter": "01. 섹션" 또는 "",
      "title": "슬라이드 제목" 또는 "",
      "subtitle": "부제목" 또는 "",
      "lead": "리드 문장" 또는 "",
      "contents": ["본문 내용1", "본문 내용2", ...]
    }},
    {{
      "page": 2,
      ...
    }}
  ]
}}
```

**중요:** JSON만 출력하고 설명은 생략하세요."""

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ],
                    }
                ],
            )

            # 응답 파싱
            response_text = message.content[0].text
            chunk_results = _parse_vision_json_response(response_text, chunk_start)

            all_results.extend(chunk_results)
            print(f"   ✅ {len(chunk_results)}개 페이지 추출 완료")

        finally:
            # 임시 파일 삭제
            os.unlink(tmp_path)

    print(f"\n✅ 전체 추출 완료: {len(all_results)}개 페이지")
    return all_results


def _parse_vision_json_response(response_text: str, page_offset: int = 0) -> List[Dict]:
    """
    Vision API JSON 응답 파싱 (단일 프롬프트 방식)

    Args:
        response_text: Claude API 응답 (JSON)
        page_offset: 페이지 번호 오프셋

    Returns:
        [{"page": N, "chapter": "...", "title": "...", ...}, ...]
    """
    import json

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
        return []

    results = []

    for page_data in data.get('pages', []):
        page_num = page_data.get('page', 1) + page_offset

        chapter = page_data.get("chapter", "")
        title = page_data.get("title", "")
        subtitle = page_data.get("subtitle", "")
        lead = page_data.get("lead", "")
        contents = page_data.get("contents", [])

        # text_count: 구조화된 필드 + 콘텐츠 개수
        text_count = sum([
            1 if chapter else 0,
            1 if title else 0,
            1 if subtitle else 0,
            1 if lead else 0,
            len(contents)
        ])

        results.append({
            "page": page_num,
            "chapter": chapter,
            "title": title,
            "subtitle": subtitle,
            "lead": lead,
            "contents": contents,
            "text_count": text_count
        })

    return results


def _parse_vision_response_with_structure(response_text: str, page_offset: int = 0) -> List[Dict]:
    """
    Claude Vision API 응답을 파싱하여 텍스트 순서 기반으로 구조 추론

    Args:
        response_text: Claude API 응답 텍스트
        page_offset: 페이지 번호 오프셋

    Returns:
        [
            {
                "page": N,
                "chapter": "...",
                "title": "...",
                "subtitle": "...",
                "lead": "...",
                "contents": [...],
                "texts": [...]
            },
            ...
        ]
    """
    results = []
    current_page = None
    current_texts = []

    for line in response_text.strip().split('\n'):
        line = line.strip()

        # 페이지 구분자 확인
        if line.startswith('[페이지') or line.startswith('[Page'):
            # 이전 페이지 저장
            if current_page is not None and current_texts:
                # 텍스트 순서 기반 구조 인식
                structure = _infer_structure_from_order(current_texts)

                results.append({
                    "page": current_page,
                    "chapter": structure.get("chapter", ""),
                    "title": structure.get("title", ""),
                    "subtitle": structure.get("subtitle", ""),
                    "lead": structure.get("lead", ""),
                    "contents": structure.get("contents", []),
                    "texts": current_texts,  # 원본 보존
                    "text_count": len(current_texts)
                })

            # 새 페이지 시작
            match = re.search(r'\d+', line)
            if match:
                relative_page = int(match.group())
                current_page = page_offset + relative_page
                current_texts = []
        elif line and current_page is not None:
            current_texts.append(line)

    # 마지막 페이지 저장
    if current_page is not None and current_texts:
        structure = _infer_structure_from_order(current_texts)

        results.append({
            "page": current_page,
            "chapter": structure.get("chapter", ""),
            "title": structure.get("title", ""),
            "subtitle": structure.get("subtitle", ""),
            "lead": structure.get("lead", ""),
            "contents": structure.get("contents", []),
            "texts": current_texts,
            "text_count": len(current_texts)
        })

    return results


def _infer_structure_from_order(texts: List[str]) -> Dict:
    """
    텍스트 배열의 순서와 길이를 기반으로 슬라이드 구조 추론

    규칙 (PPT 표준 레이아웃 가정):
    1. 첫 번째 짧은 텍스트 (≤8자) → Chapter
    2. 다음 중간 텍스트 (8-30자) → Title
    3. 다음 긴 텍스트 (15-50자) → Subtitle
    4. 다음 매우 긴 텍스트 (≥25자) → Lead
    5. 나머지 → Contents

    Args:
        texts: 읽기 순서대로 정렬된 텍스트 배열

    Returns:
        {"chapter": "...", "title": "...", "subtitle": "...", "lead": "...", "contents": [...]}
    """
    chapter = ""
    title = ""
    subtitle = ""
    lead = ""
    contents = []

    idx = 0

    # 1. Chapter 찾기 (첫 번째 짧은 텍스트)
    if idx < len(texts) and len(texts[idx]) <= 8:
        chapter = texts[idx]
        idx += 1

    # 2. Title 찾기 (다음 중간 텍스트)
    if idx < len(texts) and 8 < len(texts[idx]) <= 30:
        title = texts[idx]
        idx += 1
    elif idx < len(texts) and len(texts[idx]) <= 30:
        # Chapter 없이 Title부터 시작하는 경우
        title = texts[idx]
        idx += 1

    # 3. Subtitle 찾기 (다음 중간~긴 텍스트)
    if idx < len(texts) and 15 <= len(texts[idx]) <= 50:
        subtitle = texts[idx]
        idx += 1

    # 4. Lead 찾기 (다음 매우 긴 텍스트)
    if idx < len(texts) and len(texts[idx]) >= 25:
        lead = texts[idx]
        idx += 1

    # 5. Contents (나머지)
    contents = texts[idx:]

    return {
        "chapter": chapter,
        "title": title,
        "subtitle": subtitle,
        "lead": lead,
        "contents": contents
    }


def _parse_vision_response_with_bbox(response_text: str, page_offset: int = 0) -> List[Dict]:
    """
    Claude Vision API 응답 (bbox 포함)을 파싱하여 구조화된 슬라이드 데이터로 변환

    Args:
        response_text: Claude API 응답 텍스트 (JSON 형식)
        page_offset: 페이지 번호 오프셋 (청크 처리 시 사용)

    Returns:
        [
            {
                "page": N,
                "chapter": "...",
                "title": "...",
                "subtitle": "...",
                "lead": "...",
                "contents": [...],
                "text_blocks": [{"text": "...", "bbox": {...}, "role": "..."}]
            },
            ...
        ]
    """
    import json

    # JSON 추출 (```json...``` 또는 {...} 형태)
    json_str = response_text.strip()

    # 코드 블록 제거
    if '```json' in json_str:
        json_str = json_str.split('```json')[1].split('```')[0].strip()
    elif '```' in json_str:
        json_str = json_str.split('```')[1].split('```')[0].strip()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 파싱 실패, 텍스트만 추출합니다: {e}")
        # Fallback: 단순 텍스트 추출
        return _parse_vision_response_fallback(response_text, page_offset)

    results = []

    for page_data in data.get('pages', []):
        page_num = page_data.get('page_number', 1) + page_offset
        text_blocks = page_data.get('text_blocks', [])

        # bbox 기반 역할 분류
        slide_structure = _classify_text_roles(text_blocks)

        results.append({
            "page": page_num,
            "chapter": slide_structure.get("chapter", ""),
            "title": slide_structure.get("title", ""),
            "subtitle": slide_structure.get("subtitle", ""),
            "lead": slide_structure.get("lead", ""),
            "contents": slide_structure.get("contents", []),
            "text_blocks": text_blocks,  # 원본 데이터 보존
            "text_count": len(text_blocks)
        })

    return results


def _classify_text_roles(text_blocks: List[Dict]) -> Dict:
    """
    텍스트 블록들을 위치 정보(bbox)를 기반으로 역할 분류

    규칙:
    - Chapter: x < 0.15, y < 0.15, font_size=small (좌측 상단 작은 글씨)
    - Title: y < 0.2, font_size=large (상단 큰 글씨)
    - Subtitle: 0.2 < y < 0.35, font_size=medium (제목 아래 중간 크기)
    - Lead: 0.35 < y < 0.55, 긴 텍스트 (본문 첫 문단)
    - Contents: 나머지

    Args:
        text_blocks: [{"text": "...", "bbox": {"x": ..., "y": ..., ...}, "font_size": "..."}]

    Returns:
        {"chapter": "...", "title": "...", "subtitle": "...", "lead": "...", "contents": [...]}
    """
    chapter = ""
    title = ""
    subtitle = ""
    lead = ""
    contents = []

    for block in text_blocks:
        text = block.get('text', '').strip()
        bbox = block.get('bbox', {})
        font_size = block.get('font_size', 'medium')

        if not text or not bbox:
            continue

        x = bbox.get('x', 0.5)
        y = bbox.get('y', 0.5)

        # Chapter 판별: 좌측 상단 작은 글씨
        if x < 0.15 and y < 0.15 and font_size == 'small' and not chapter:
            chapter = text

        # Title 판별: 상단 큰 글씨
        elif y < 0.2 and font_size == 'large' and not title:
            title = text

        # Subtitle 판별: 제목 아래 중간 크기
        elif 0.2 <= y < 0.35 and font_size in ['medium', 'large'] and not subtitle:
            subtitle = text

        # Lead 판별: 본문 첫 문단 (긴 텍스트)
        elif 0.35 <= y < 0.6 and len(text) >= 25 and not lead:
            lead = text

        # Contents: 나머지
        else:
            contents.append(text)

    return {
        "chapter": chapter,
        "title": title,
        "subtitle": subtitle,
        "lead": lead,
        "contents": contents
    }


def _parse_vision_response_fallback(response_text: str, page_offset: int = 0) -> List[Dict]:
    """
    Fallback: JSON 파싱 실패 시 단순 텍스트 추출
    """
    results = []
    current_page = None
    current_texts = []

    for line in response_text.strip().split('\n'):
        line = line.strip()

        # 페이지 구분자 확인
        if line.startswith('[페이지') or line.startswith('[Page'):
            # 이전 페이지 저장
            if current_page is not None and current_texts:
                results.append({
                    "page": current_page,
                    "texts": current_texts,
                    "text_count": len(current_texts),
                    "chapter": "",
                    "title": "",
                    "subtitle": "",
                    "lead": "",
                    "contents": current_texts
                })

            # 새 페이지 시작 (오프셋 적용)
            match = re.search(r'\d+', line)
            if match:
                relative_page = int(match.group())
                current_page = page_offset + relative_page
                current_texts = []
        elif line and current_page is not None:
            current_texts.append(line)

    # 마지막 페이지 저장
    if current_page is not None and current_texts:
        results.append({
            "page": current_page,
            "texts": current_texts,
            "text_count": len(current_texts),
            "chapter": "",
            "title": "",
            "subtitle": "",
            "lead": "",
            "contents": current_texts
        })

    return results


def extract_text_from_image(image_path: str, api_key: str = None) -> Dict:
    """
    Claude Vision API로 이미지에서 텍스트 추출

    Args:
        image_path: 이미지 파일 경로
        api_key: Anthropic API 키 (None이면 환경변수 사용)

    Returns:
        {
            "texts": ["텍스트1", "텍스트2", ...],
            "raw_response": "Claude의 원본 응답"
        }
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY 환경변수를 설정하거나 api_key를 전달해주세요")

    # 이미지를 base64로 인코딩
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    # 이미지 타입 확인
    image_path = Path(image_path)
    ext = image_path.suffix.lower()
    media_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp"
    }
    media_type = media_type_map.get(ext, "image/png")

    # Claude API 호출
    client = anthropic.Anthropic(api_key=api_key)

    prompt = """이 슬라이드 이미지에서 모든 텍스트를 추출해주세요.

**중요 지침:**
1. 보이는 모든 텍스트를 빠짐없이 추출하세요
2. 텍스트의 원래 순서와 계층을 유지하세요
3. 제목, 본문, 작은 글씨까지 모두 포함하세요
4. 각 텍스트 블록을 별도의 줄로 구분하세요

**출력 형식:**
각 텍스트를 한 줄씩 출력하되, 빈 줄로 구분하지 마세요.
설명 없이 텍스트만 출력하세요."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )

    # 응답 파싱
    response_text = message.content[0].text

    # 텍스트를 줄 단위로 분리
    lines = response_text.strip().split('\n')
    texts = [line.strip() for line in lines if line.strip()]

    return {
        "texts": texts,
        "raw_response": response_text
    }


def extract_text_from_images_batch(image_paths: List[str], api_key: str = None) -> List[Dict]:
    """
    여러 이미지에서 텍스트를 배치로 추출

    Args:
        image_paths: 이미지 파일 경로 리스트
        api_key: Anthropic API 키

    Returns:
        [
            {"slide": 1, "texts": [...], "image_path": "..."},
            ...
        ]
    """
    results = []

    print(f"🔍 Claude Vision API로 {len(image_paths)}개 슬라이드 분석 중...")

    for i, image_path in enumerate(image_paths, 1):
        try:
            print(f"   [{i}/{len(image_paths)}] {Path(image_path).name} 분석 중...", end='')

            result = extract_text_from_image(image_path, api_key)

            results.append({
                "slide": i,
                "texts": result["texts"],
                "image_path": str(image_path),
                "text_count": len(result["texts"])
            })

            print(f" ✅ ({len(result['texts'])}개 텍스트)")

        except Exception as e:
            print(f" ❌ 오류: {e}")
            results.append({
                "slide": i,
                "texts": [],
                "image_path": str(image_path),
                "error": str(e)
            })

    print(f"\n✅ Vision 추출 완료: 총 {sum(r['text_count'] for r in results if 'text_count' in r)}개 텍스트")
    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법:")
        print("  python vision_text_extractor.py image.png  # 이미지에서 추출")
        print("  python vision_text_extractor.py file.pdf   # PDF에서 추출")
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        # PDF 파일인지 확인
        if file_path.lower().endswith('.pdf'):
            results = extract_text_from_pdf(file_path)
            print(f"\n✅ {len(results)}개 페이지 추출 완료\n")

            for page_data in results[:5]:  # 처음 5페이지만
                print(f"[페이지 {page_data['page']}] - {page_data['text_count']}개 텍스트")
                for i, text in enumerate(page_data['texts'][:5], 1):
                    print(f"  {i}. {text}")
                if len(page_data['texts']) > 5:
                    print(f"  ... 외 {len(page_data['texts']) - 5}개")
                print()

            if len(results) > 5:
                print(f"... 외 {len(results) - 5}개 페이지")
        else:
            result = extract_text_from_image(file_path)
            print(f"\n추출된 텍스트 ({len(result['texts'])}개):")
            print("=" * 50)
            for i, text in enumerate(result['texts'], 1):
                print(f"{i}. {text}")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
