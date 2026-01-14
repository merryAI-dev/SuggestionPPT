#!/usr/bin/env python3
"""
Claude API를 활용한 슬라이드 콘텐츠 생성 모듈
자연어 입력 → slides_data.json 형식 출력

핵심: 사용자가 제공한 콘텐츠를 최대한 보존하면서 슬라이드 구조로 변환
"""

import json
import os
import re
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("anthropic 패키지를 설치해주세요: pip install anthropic")
    raise


class SlideGenerator:
    """Claude API를 사용해 슬라이드 콘텐츠를 생성합니다."""

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: Anthropic API 키. 없으면 환경변수 ANTHROPIC_API_KEY 사용
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수를 설정하거나 api_key를 전달해주세요.")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.learning_data = self._load_learning_data()

    def _load_learning_data(self) -> dict:
        """학습 데이터를 로드합니다."""
        learning_path = Path(__file__).parent / "learning_data" / "patterns.json"
        if learning_path.exists():
            with open(learning_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _get_reference_examples(self) -> str:
        """학습 데이터에서 참조할 예시를 추출합니다."""
        examples = []
        doc_types = self.learning_data.get("document_types", {})

        for doc_type, info in doc_types.items():
            type_examples = info.get("examples", [])[:2]  # 각 유형별 2개씩
            for ex in type_examples:
                if ex.get("title") and ex.get("lead"):
                    examples.append({
                        "type": doc_type,
                        "chapter": ex.get("chapter", ""),
                        "title": ex.get("title", ""),
                        "lead": ex.get("lead", "")
                    })

        return json.dumps(examples[:6], ensure_ascii=False, indent=2) if examples else "[]"

    def _build_system_prompt(self) -> str:
        """강화된 시스템 프롬프트를 구성합니다."""
        reference_examples = self._get_reference_examples()

        return f"""당신은 전문 프레젠테이션 구조화 전문가입니다.

## 핵심 역할
사용자가 제공한 콘텐츠를 PPT 슬라이드 구조로 변환합니다.
**사용자의 원본 콘텐츠를 최대한 보존하면서** 슬라이드에 적합한 형태로 구조화하세요.

## 필수 글자수 제한 (매우 중요!)
- **chapter**: 최대 5글자 (예: "발견", "채용", "집중", "선배", "공유")
- **title**: 10~20글자 내외의 간결한 제목
- **subtitle**: 15~30글자, 타이틀을 보조하는 부제목 (없으면 빈 문자열)
- **lead**: 25~35글자, 줄바꿈(\\n) 없이 한 문장으로 작성

## 변환 원칙
1. **콘텐츠 보존**: 사용자가 작성한 핵심 내용, 용어, 표현을 그대로 유지
2. **구조 파악**: [대괄호]로 묶인 부분은 섹션/챕터로 인식
3. **계층 분석**: 들여쓰기, 번호, 기호로 구분된 내용은 하위 슬라이드로 분리
4. **자연 분할**: 내용이 많으면 자연스럽게 여러 슬라이드로 분할

## 슬라이드 구조 규칙
- **chapter**: 섹션 키워드만 (예: "01. 발견", "02. 채용") - 반드시 5글자 이내!
- **title**: 핵심 제목 (10~20글자)
- **subtitle**: 부제목 (15~30글자, 타이틀 보조 설명, 없으면 "")
- **lead**: 핵심 메시지 한 문장 (25~35글자, 줄바꿈 금지!)

## 참조 예시 (기존 문서 스타일)
{reference_examples}

## 출력 형식 (JSON만 출력)
```json
{{
  "slides": [
    {{"page": 1, "chapter": "", "title": "메인 타이틀", "subtitle": "부제목이 있으면 여기에", "lead": "핵심 메시지를 한 문장으로 간결하게 작성"}},
    {{"page": 2, "chapter": "01. 발견", "title": "Born-AI 세대 창업", "subtitle": "", "lead": "예비 창업팀 대상 해커톤 프로그램 운영"}}
  ]
}}
```

## 중요 규칙
1. chapter는 **반드시 5글자 이내** (번호 제외)
2. lead는 **줄바꿈 없이 한 문장**, 25~35글자
3. 사용자 콘텐츠의 핵심 키워드와 용어는 그대로 유지
4. JSON 외에 다른 텍스트는 출력하지 마세요
5. 슬라이드 수는 콘텐츠 양에 따라 자연스럽게 결정"""

    def _build_user_prompt(self, user_input: str) -> str:
        """사용자 프롬프트를 구성합니다."""
        return f"""다음 콘텐츠를 PPT 슬라이드 구조로 변환해주세요.

---
{user_input}
---

위 내용을 분석하여:
1. 자연스러운 섹션(chapter)으로 구분
2. 각 섹션 내 핵심 포인트를 개별 슬라이드로 분리
3. 원본 콘텐츠의 표현과 용어를 최대한 보존

JSON 형식으로 출력해주세요."""

    def generate(self, user_input: str) -> dict:
        """
        자연어 입력을 받아 슬라이드 데이터를 생성합니다.

        Args:
            user_input: 자연어 콘텐츠 (기획안, 아이디어, 메모 등)

        Returns:
            slides_data.json 형식의 딕셔너리
        """
        print("콘텐츠 분석 중...")

        # 프롬프트 구성
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(user_input)

        # Claude API 호출
        print("Claude API 호출 중...")
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # 응답 파싱
        response_text = response.content[0].text
        result = self._parse_response(response_text)

        print(f"슬라이드 {len(result['slides'])}개 생성 완료")
        return result

    def generate_lead_only(self, context: str, max_length: int = 35) -> str:
        """
        단일 슬라이드에 대한 리드문만 생성합니다.

        Args:
            context: 슬라이드 컨텍스트 (chapter + title + subtitle)
            max_length: 최대 글자수

        Returns:
            생성된 리드문 (25-35자, 한 줄, "합니다" 어미)
        """
        prompt = f"""다음 슬라이드의 핵심 메시지를 리드문으로 작성해주세요.

슬라이드 내용:
{context}

리드문 요구사항:
- {max_length}글자 이내
- 한 줄로 작성 (줄바꿈 금지)
- "~합니다" 또는 "~입니다" 어미 사용
- 슬라이드의 핵심 메시지를 담은 간결한 문장

리드문만 작성해주세요 (다른 설명 불필요):"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )

        lead = response.content[0].text.strip()
        lead = lead.strip('"\'')  # 따옴표 제거

        # 길이 검증
        if len(lead) > max_length:
            print(f"⚠️ 생성된 리드가 너무 깁니다 ({len(lead)}자), 재시도 중...")
            return self.generate_lead_only(context, max_length=max_length-5)

        return lead

    def _parse_response(self, response_text: str) -> dict:
        """Claude 응답에서 JSON을 추출하고 검증합니다."""
        # JSON 블록 추출
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            response_text = response_text[start:end].strip()

        # JSON 파싱
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            print(f"응답 텍스트:\n{response_text[:500]}")
            raise

        # 스키마 검증
        if "slides" not in data:
            raise ValueError("응답에 'slides' 필드가 없습니다")

        for i, slide in enumerate(data["slides"]):
            required_fields = ["page", "chapter", "title", "lead"]
            for field in required_fields:
                if field not in slide:
                    raise ValueError(f"슬라이드 {i+1}에 '{field}' 필드가 없습니다")
            # subtitle이 없으면 빈 문자열로 추가
            if "subtitle" not in slide:
                slide["subtitle"] = ""

        # font_settings 추가 (기본값 - 현대하모니 폰트, 시스템 등록명 사용)
        if "font_settings" not in data:
            data["font_settings"] = {
                "chapter": {"name": "HDharmonyB", "size": 16, "bold": False, "color": "#000000"},
                "title": {"name": "HDharmonyB", "size": 16, "bold": False, "color": "#000000"},
                "subtitle": {"name": "HDharmonyM", "size": 16, "bold": False, "color": "#000000"},
                "lead": {"name": "HDharmonyL", "size": 12, "color": "#000000"}
            }

        return data


def generate_slides(user_input: str, api_key: str = None) -> dict:
    """
    편의 함수: 자연어 입력으로 슬라이드 데이터 생성

    Args:
        user_input: 자연어 콘텐츠
        api_key: Anthropic API 키 (선택사항)

    Returns:
        slides_data.json 형식의 딕셔너리
    """
    generator = SlideGenerator(api_key=api_key)
    return generator.generate(user_input)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python generator.py '콘텐츠'")
        sys.exit(1)

    user_input = sys.argv[1]
    result = generate_slides(user_input)

    print("\n생성된 슬라이드 데이터:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
