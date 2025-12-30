"""
PPTX 단어 통일성 및 오타 검사 도구

기능:
1. 단어 통일성 검사 (같은 의미, 다른 표기)
2. 오타 검사 (한국어 맞춤법)
3. 용어 일관성 리포트 생성
4. Claude API를 활용한 고급 검사 (선택)

사용법:
    python pptx_checker.py input.pptx
    python pptx_checker.py input.pptx --fix  # 수정 제안 포함
    python pptx_checker.py input.pptx --claude  # Claude API 사용
"""

import sys
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from zipfile import ZipFile
from xml.etree import ElementTree as ET


# ============================================
# 통일성 검사용 용어 사전
# (같은 의미지만 다르게 쓰이는 표현들)
# ============================================

TERM_VARIANTS = {
    # 일반적인 혼용 표현
    "통일 표기": [
        ("스타트업", ["스타트 업", "스타트-업", "Start-up", "Start up", "startup"]),
        ("액셀러레이터", ["엑셀러레이터", "악셀러레이터", "Accelerator"]),
        ("인큐베이터", ["인큐베이션", "incubator"]),
        ("임팩트", ["Impact", "impact"]),
        ("소셜벤처", ["소셜 벤처", "Social Venture", "사회적벤처"]),
        ("비즈니스", ["비지니스", "Business"]),
        ("프로그램", ["프로그램", "Programme"]),
        ("네트워크", ["네트웍", "Network"]),
        ("플랫폼", ["플랫홈", "Platform"]),
        ("커뮤니티", ["커뮤니케이션", "Community"]),
        ("온라인", ["온-라인", "Online"]),
        ("오프라인", ["오프-라인", "Offline"]),
        ("데이터", ["데이타", "Data"]),
        ("컨설팅", ["컨설팅", "Consulting"]),
        ("멘토링", ["멘토링", "Mentoring"]),
        ("코칭", ["코칭", "Coaching"]),
        ("워크숍", ["워크샵", "Workshop"]),
        ("컨퍼런스", ["컨퍼런스", "Conference", "콘퍼런스"]),
        ("펠로", ["펠로우", "Fellow", "펠로우십"]),  # 펠로로 통일
        ("임팩트 앙트프러너십", ["기업가 정신", "기업가정신", "앙트레프레너십", "entrepreneurship"]),
    ],

    # H-온드림 관련 용어
    "H-온드림 용어": [
        ("H-온드림", ["H온드림", "H 온드림", "에이치온드림", "H-Ondream"]),
        ("스타트업 그라운드", ["스타트업그라운드", "Startup Ground"]),
        ("인큐베이팅 트랙", ["인큐베이팅트랙", "Incubating Track"]),
        ("액셀러레이팅 트랙", ["액셀러레이팅트랙", "Accelerating Track"]),
    ],

    # 숫자/단위 표기
    "숫자 표기": [
        ("억 원", ["억원", "억"]),
        ("만 원", ["만원"]),
        ("개월", ["개 월"]),
        ("년", ["년도"]),
    ],
}

# 자주 틀리는 맞춤법
COMMON_TYPOS = {
    "되있": "돼있",
    "되요": "돼요",
    "되서": "돼서",
    "됬": "됐",
    "않됩니다": "안 됩니다",
    "안돼요": "안 돼요",
    "할께": "할게",
    "할꺼": "할 거",
    "웬지": "왠지",
    "어떻게": "어떻게",  # 자주 틀리는 것들
    "갯수": "개수",
    "몇일": "며칠",
    "금새": "금세",
    "어의없": "어이없",
    "희안": "희한",
    "설레임": "설렘",
    "오랫만": "오랜만",
    "어떻해": "어떡해",
}

# 띄어쓰기 오류 패턴
SPACING_ERRORS = [
    (r"할수있", "할 수 있"),
    (r"해야할", "해야 할"),
    (r"하기위해", "하기 위해"),
    (r"함으로써", "함으로써"),
    (r"것입니다", "것입니다"),
    (r"합니다\.(?!\s)", "합니다. "),
]


class PPTXChecker:
    """PPTX 문서 검사 도구"""

    def __init__(self, pptx_path: str):
        self.pptx_path = Path(pptx_path)
        self.texts = []  # [(slide_num, shape_id, text), ...]
        self.issues = []  # 발견된 문제들
        self.word_counts = Counter()  # 단어 빈도수

    def extract_text(self) -> list:
        """PPTX에서 모든 텍스트 추출"""
        print(f"\n📖 텍스트 추출 중: {self.pptx_path.name}")

        with ZipFile(self.pptx_path, 'r') as zf:
            slide_files = sorted([
                f for f in zf.namelist()
                if f.startswith('ppt/slides/slide') and f.endswith('.xml')
            ])

            for slide_file in slide_files:
                slide_num = int(re.search(r'slide(\d+)', slide_file).group(1))

                with zf.open(slide_file) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    # 네임스페이스 처리
                    ns = {
                        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                        'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'
                    }

                    # 모든 텍스트 요소 찾기
                    for shape_idx, t_elem in enumerate(root.findall('.//a:t', ns)):
                        if t_elem.text and t_elem.text.strip():
                            text = t_elem.text.strip()
                            self.texts.append((slide_num, shape_idx, text))

                            # 단어 카운트
                            words = re.findall(r'[가-힣]+|[a-zA-Z]+', text)
                            self.word_counts.update(words)

        print(f"   추출된 텍스트 블록: {len(self.texts)}개")
        print(f"   고유 단어 수: {len(self.word_counts)}개")

        return self.texts

    def check_term_consistency(self) -> list:
        """용어 통일성 검사"""
        print("\n🔍 용어 통일성 검사 중...")

        issues = []
        all_text = " ".join([t[2] for t in self.texts])

        for category, term_list in TERM_VARIANTS.items():
            for standard, variants in term_list:
                found_variants = []

                # 표준 표현 찾기
                if standard.lower() in all_text.lower():
                    found_variants.append(standard)

                # 변형 표현 찾기
                for variant in variants:
                    if variant.lower() in all_text.lower():
                        found_variants.append(variant)

                # 여러 표현이 혼용되면 문제
                if len(set(found_variants)) > 1:
                    # 어느 슬라이드에서 발견됐는지 찾기
                    locations = []
                    for slide_num, _, text in self.texts:
                        for var in found_variants:
                            if var.lower() in text.lower():
                                locations.append(f"슬라이드 {slide_num}")
                                break

                    issues.append({
                        "type": "용어 불일치",
                        "category": category,
                        "found": list(set(found_variants)),
                        "recommended": standard,
                        "locations": list(set(locations))[:5],  # 최대 5개만 표시
                    })

        self.issues.extend(issues)
        print(f"   발견된 불일치: {len(issues)}건")
        return issues

    def check_typos(self) -> list:
        """맞춤법 오류 검사"""
        print("\n✏️ 맞춤법 검사 중...")

        issues = []

        for slide_num, shape_idx, text in self.texts:
            # 일반 오타 검사
            for wrong, correct in COMMON_TYPOS.items():
                if wrong in text:
                    issues.append({
                        "type": "맞춤법 오류",
                        "slide": slide_num,
                        "wrong": wrong,
                        "correct": correct,
                        "context": text[:50] + "..." if len(text) > 50 else text,
                    })

            # 띄어쓰기 오류 검사
            for pattern, correct in SPACING_ERRORS:
                if re.search(pattern, text):
                    issues.append({
                        "type": "띄어쓰기 오류",
                        "slide": slide_num,
                        "pattern": pattern,
                        "correct": correct,
                        "context": text[:50] + "..." if len(text) > 50 else text,
                    })

        self.issues.extend(issues)
        print(f"   발견된 오류: {len(issues)}건")
        return issues

    def check_number_format(self) -> list:
        """숫자/단위 표기 일관성 검사"""
        print("\n🔢 숫자 표기 검사 중...")

        issues = []
        all_text = " ".join([t[2] for t in self.texts])

        # 억원 vs 억 원
        if "억원" in all_text and "억 원" in all_text:
            issues.append({
                "type": "표기 불일치",
                "category": "금액 단위",
                "found": ["억원", "억 원"],
                "recommended": "억 원 (띄어쓰기 권장)",
            })

        # 만원 vs 만 원
        if "만원" in all_text and "만 원" in all_text:
            issues.append({
                "type": "표기 불일치",
                "category": "금액 단위",
                "found": ["만원", "만 원"],
                "recommended": "만 원 (띄어쓰기 권장)",
            })

        # 연도 표기 (21년 vs 2021년)
        short_years = re.findall(r"(?<!\d)(\d{2})년", all_text)
        full_years = re.findall(r"(20\d{2})년", all_text)
        if short_years and full_years:
            issues.append({
                "type": "표기 불일치",
                "category": "연도",
                "found": [f"{y}년" for y in short_years[:3]] + [f"{y}년" for y in full_years[:3]],
                "recommended": "연도 표기 통일 필요 (예: 2024년 또는 24년)",
            })

        self.issues.extend(issues)
        print(f"   발견된 불일치: {len(issues)}건")
        return issues

    def generate_report(self, output_path: str = None) -> dict:
        """검사 결과 리포트 생성"""
        print("\n" + "=" * 60)
        print("📋 검사 결과 리포트")
        print("=" * 60)

        report = {
            "file": str(self.pptx_path),
            "summary": {
                "total_text_blocks": len(self.texts),
                "unique_words": len(self.word_counts),
                "total_issues": len(self.issues),
            },
            "issues_by_type": defaultdict(list),
            "frequent_words": self.word_counts.most_common(20),
        }

        # 이슈 분류
        for issue in self.issues:
            report["issues_by_type"][issue["type"]].append(issue)

        # 요약 출력
        print(f"\n📊 요약:")
        print(f"   - 검사된 텍스트 블록: {report['summary']['total_text_blocks']}개")
        print(f"   - 고유 단어 수: {report['summary']['unique_words']}개")
        print(f"   - 발견된 문제: {report['summary']['total_issues']}건")

        # 이슈별 상세
        print(f"\n🔍 발견된 문제:")
        for issue_type, items in report["issues_by_type"].items():
            print(f"\n   [{issue_type}] - {len(items)}건")
            for item in items[:5]:  # 각 유형별 최대 5개만 출력
                if "wrong" in item:
                    print(f"      • '{item['wrong']}' → '{item['correct']}' (슬라이드 {item['slide']})")
                elif "found" in item:
                    print(f"      • {item['found']} → '{item['recommended']}'")

        # 자주 사용된 단어
        print(f"\n📈 자주 사용된 단어 (Top 10):")
        for word, count in report["frequent_words"][:10]:
            print(f"   - {word}: {count}회")

        # JSON 저장
        if output_path:
            # defaultdict를 일반 dict로 변환
            report["issues_by_type"] = dict(report["issues_by_type"])
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n💾 리포트 저장: {output_path}")

        return report

    def run_all_checks(self) -> dict:
        """모든 검사 실행"""
        self.extract_text()
        self.check_term_consistency()
        self.check_typos()
        self.check_number_format()
        return self.generate_report()


def check_with_claude(pptx_path: str, texts: list) -> dict:
    """Claude API를 사용한 고급 검사 (선택적) - 문맥 기반 용어 검사 포함"""
    try:
        import anthropic
        import os
    except ImportError:
        print("❌ anthropic 패키지가 필요합니다: pip install anthropic")
        return {}

    print("\n🤖 Claude API로 고급 검사 중...")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다")
        return {}

    client = anthropic.Anthropic(api_key=api_key)

    # 텍스트 샘플 준비 (토큰 제한 고려)
    sample_text = "\n".join([f"[슬라이드 {s}] {t}" for s, _, t in texts[:100]])

    prompt = f"""다음은 H-온드림 임팩트 스타트업 지원 프로그램 PPT 문서에서 추출한 텍스트입니다.

**특별 규칙 (문맥 기반 검사 필수):**
1. "펠로우" → "펠로"로 모두 변경
2. "기업가 정신" → "임팩트 앙트프러너십"으로 변경
3. "스타트업" → 문맥을 보고 "임팩트 스타트업"으로 변경해야 할지 판단
   - 임팩트/소셜 관련 맥락에서 사용된 경우: "임팩트 스타트업"으로 변경
   - 일반적인 스타트업 생태계 언급인 경우: 변경하지 않음
   - 예: "임팩트를 만드는 스타트업" → "임팩트 스타트업"
   - 예: "스타트업 생태계" → 변경 안 함

아래 항목들을 검사해주세요:

1. **용어 통일성 (특별 규칙 우선 적용)**:
   - 위 특별 규칙에 따른 변경 사항
   - 같은 의미인데 다르게 표기된 단어들 (예: 스타트 업, Start-up, 스타트업)

2. **맞춤법/문법 오류**:
   - 잘못된 표현
   - 띄어쓰기 오류

3. **어색한 문장**:
   - 자연스럽지 않은 표현

텍스트:
{sample_text}

JSON 형식으로 응답해주세요:
{{
  "context_based_issues": [
    {{
      "slide": 슬라이드 번호,
      "original": "원본 문장",
      "suggested": "제안 문장",
      "reason": "변경 이유 (특별 규칙 또는 일반 규칙)",
      "term": "변경된 용어"
    }}
  ],
  "term_issues": [{{"found": "...", "recommended": "...", "reason": "..."}}],
  "grammar_issues": [{{"wrong": "...", "correct": "...", "slide": ...}}],
  "style_issues": [{{"issue": "...", "suggestion": "..."}}]
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        # JSON 부분만 추출 (코드 블록이 있을 수 있음)
        content = response.content[0].text
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)
        print("   ✅ Claude 분석 완료")

        # 결과 요약 출력
        if "context_based_issues" in result and result["context_based_issues"]:
            print(f"\n   📝 문맥 기반 용어 변경 제안: {len(result['context_based_issues'])}건")
            for issue in result["context_based_issues"][:5]:
                print(f"      [슬라이드 {issue['slide']}] '{issue['term']}' 변경 제안")

        return result
    except json.JSONDecodeError:
        print("   ⚠️ Claude 응답 파싱 실패")
        print(f"   응답: {response.content[0].text[:200]}...")
        return {"raw_response": response.content[0].text}


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("PPTX 문서 검사 도구")
        print("-" * 40)
        print("사용법: python pptx_checker.py <input.pptx> [옵션]")
        print()
        print("옵션:")
        print("  --claude    Claude API로 고급 검사 (ANTHROPIC_API_KEY 필요)")
        print("  --output    결과 JSON 파일 경로 지정")
        print()
        print("예시:")
        print("  python pptx_checker.py presentation.pptx")
        print("  python pptx_checker.py presentation.pptx --claude")
        print("  python pptx_checker.py presentation.pptx --output report.json")
        sys.exit(0)

    pptx_path = sys.argv[1]
    use_claude = "--claude" in sys.argv

    # 출력 파일 경로
    output_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]
    else:
        output_path = pptx_path.replace(".pptx", "_check_report.json")

    # 검사 실행
    checker = PPTXChecker(pptx_path)
    report = checker.run_all_checks()

    # Claude 고급 검사 (선택)
    if use_claude:
        claude_result = check_with_claude(pptx_path, checker.texts)
        report["claude_analysis"] = claude_result

    # 리포트 저장
    if output_path:
        report["issues_by_type"] = dict(report.get("issues_by_type", {}))
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n💾 전체 리포트 저장: {output_path}")

    print("\n✅ 검사 완료!")


if __name__ == "__main__":
    main()
