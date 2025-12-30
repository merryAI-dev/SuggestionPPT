#!/usr/bin/env python3
"""
PPT 자동 생성 파이프라인
자연어 입력 → Claude API → slides_data.json → output.pptx
"""

import json
import sys
from pathlib import Path

from generator import SlideGenerator
from ppt_generator import generate_pptx


def run(user_input: str, output_path: str = "output.pptx", template_path: str = "tem.pptx"):
    """
    전체 파이프라인 실행

    Args:
        user_input: 자연어 요청 (예: "H-온드림 2026년 제안서 만들어줘")
        output_path: 출력 PPTX 파일 경로
        template_path: 템플릿 PPTX 파일 경로

    Returns:
        생성된 PPTX 파일 경로
    """
    print("=" * 60)
    print("PPT 자동 생성 파이프라인")
    print("=" * 60)
    print(f"\n입력: {user_input}\n")

    # 1. Claude API로 슬라이드 데이터 생성
    print("[1/3] 슬라이드 콘텐츠 생성 중...")
    generator = SlideGenerator()
    slides_data = generator.generate(user_input)

    # 2. JSON 파일로 저장
    json_path = "slides_data_generated.json"
    print(f"\n[2/3] JSON 저장 중... ({json_path})")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(slides_data, f, ensure_ascii=False, indent=2)

    # 3. PPTX 생성
    print(f"\n[3/3] PPTX 생성 중... ({output_path})")
    generate_pptx(template_path, json_path, output_path)

    print("\n" + "=" * 60)
    print(f"완료! 생성된 파일: {output_path}")
    print(f"슬라이드 수: {len(slides_data['slides'])}개")
    print("=" * 60)

    return output_path


def main():
    """CLI 메인 함수"""
    if len(sys.argv) < 2:
        print("PPT 자동 생성 도구")
        print("-" * 40)
        print("사용법: python pipeline.py '자연어 요청' [출력파일]")
        print()
        print("예시:")
        print("  python pipeline.py 'H-온드림 2026년 제안서 만들어줘'")
        print("  python pipeline.py '신한 스퀘어브릿지 결과보고서' result.pptx")
        print("  python pipeline.py '아산 두어스 기획안 10페이지로'")
        print()
        print("지원 문서 유형:")
        print("  - 제안서")
        print("  - 결과보고서")
        print("  - 기획안")
        print("  - 백서")
        print("  - 중장기계획")
        print("  - 컨설팅보고서")
        sys.exit(0)

    user_input = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) >= 3 else "output.pptx"

    run(user_input, output_path)


if __name__ == "__main__":
    main()
