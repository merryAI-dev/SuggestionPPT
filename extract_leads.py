"""
PPTX 파일에서 리드문(Lead) 추출

리드문 특징:
- 슬라이드 하단 또는 본문에 위치
- 25-35자 내외의 요약 문장
- "~합니다", "~입니다" 어미 사용
- 핵심 메시지를 담은 문장
"""

import json
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from typing import List, Dict, Tuple
from collections import defaultdict


def extract_texts_with_position(pptx_path: Path) -> List[Dict]:
    """PPTX에서 텍스트와 위치 정보 추출"""
    slides_data = []

    try:
        with ZipFile(pptx_path, 'r') as zf:
            slide_files = sorted([
                f for f in zf.namelist()
                if f.startswith('ppt/slides/slide') and f.endswith('.xml')
            ], key=lambda x: int(re.search(r'slide(\d+)', x).group(1)))

            for slide_idx, slide_file in enumerate(slide_files):
                slide_num = slide_idx + 1
                texts = []

                with zf.open(slide_file) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    ns = {
                        'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
                        'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
                        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
                    }

                    # 모든 shape에서 텍스트 추출
                    for sp in root.findall('.//p:sp', ns):
                        # 텍스트 프레임 찾기
                        txBody = sp.find('.//p:txBody', ns)
                        if txBody is None:
                            continue

                        # 위치 정보 (있으면)
                        xfrm = sp.find('.//a:xfrm', ns)
                        y_pos = 0
                        if xfrm is not None:
                            off = xfrm.find('a:off', ns)
                            if off is not None:
                                y_pos = int(off.get('y', 0))

                        # 각 paragraph(줄)별로 텍스트 추출
                        for para in txBody.findall('a:p', ns):
                            para_text = []
                            for t_elem in para.findall('.//a:t', ns):
                                if t_elem.text:
                                    para_text.append(t_elem.text)

                            text = ''.join(para_text).strip()
                            if text and len(text) > 5:
                                texts.append({
                                    'text': text,
                                    'y_position': y_pos,
                                    'char_count': len(text)
                                })

                if texts:
                    slides_data.append({
                        'slide_num': slide_num,
                        'texts': texts
                    })

    except Exception as e:
        print(f"  ⚠️ {pptx_path.name} 처리 실패: {e}")

    return slides_data


def is_lead_candidate(text: str) -> Tuple[bool, str]:
    """리드문 후보인지 판단 - 완전한 문장만 선별"""

    # 길이 체크 (25-60자)
    if len(text) < 25 or len(text) > 70:
        return False, "길이 부적합"

    # 제외 패턴 (서브타이틀/부제목/구어체 스타일 제외)
    exclude_patterns = [
        r'^\d+$',  # 숫자만
        r'^[A-Za-z\s]+$',  # 영어만
        r'^\d{4}[년\.]',  # 날짜로 시작
        r'^[\d,]+\s*(원|억|만)',  # 금액
        r'^(목차|Contents|CONTENTS)',
        r'^(Chapter|CHAPTER|01\.|02\.|03\.)',
        r'^\*',  # 주석
        r'^https?://',  # URL
        r'@',  # 이메일
        r'\|',  # 파이프 (서브타이틀 구분자)
        r'^Q\d+\.',  # 질문 번호
        r'^\(\d+\)',  # (1), (2) 등
        r'^➊|^➋|^➌|^▼|^l\s',  # 불릿 포인트
        r'^\d+\.\s',  # 1. 2. 3. 등 번호
        r'Phase\d|Track|트랙',  # 프로그램 트랙명
        r'총\s*[\d.]+억',  # 금액 표현
        r':$',  # 콜론으로 끝남 (제목 스타일)
        r'^[^가-힣]*$',  # 한글 없음
        # 구어체/설문응답 제외
        r'좋았습니다|좋았어요|좋았고',  # 설문 응답
        r'감사합니다|감사드립니다',  # 인사말
        r'아쉬웠|아쉬운 것|부족한 것',  # 피드백
        r'힐링|고생|수고',  # 구어체
        r'너무 너무|너무너무',  # 강조 구어체
        r'했으면 좋겠|으면 좋겠',  # 희망 구어체
        r'^"',  # 인용문
    ]

    for pattern in exclude_patterns:
        if re.search(pattern, text):
            return False, f"제외 패턴: {pattern}"

    # 필수 조건: 완전한 문장 어미로 끝나야 함
    lead_endings = ['합니다', '입니다', '됩니다', '습니다', '겠습니다', '있습니다',
                    '합니다.', '입니다.', '됩니다.', '습니다.', '겠습니다.', '있습니다.',
                    '하겠습니다', '하겠습니다.', '드립니다', '드립니다.']

    has_proper_ending = False
    matched_ending = None
    for ending in lead_endings:
        if text.endswith(ending):
            has_proper_ending = True
            matched_ending = ending
            break

    if not has_proper_ending:
        return False, "문장 어미 없음 (리드문은 ~합니다/~입니다로 끝나야 함)"

    # 리드문 특징 점수
    score = 3  # 어미가 맞으면 기본 3점
    reasons = [f"어미: {matched_ending}"]

    # 키워드 체크 (가산점)
    lead_keywords = ['통해', '위해', '함께', '새로운', '혁신', '성장', '지원',
                     '만들어', '이끌어', '실현', '추진', '달성', '제공', '창출',
                     '확대', '강화', '구축', '도약', '선도', '발전', '나아가',
                     '목표', '비전', '가치', '의미', '중요', '핵심', '전략']
    for keyword in lead_keywords:
        if keyword in text:
            score += 1
            reasons.append(f"키워드: {keyword}")
            if score >= 5:  # 최대 점수 제한
                break

    # 글자수 적정성 (30-50자가 이상적)
    if 30 <= len(text) <= 50:
        score += 1
        reasons.append("적정 길이")

    is_lead = score >= 3
    return is_lead, f"점수: {score}, {', '.join(reasons)}"


def extract_leads(inputdata_dir: Path) -> List[Dict]:
    """모든 PPTX에서 리드문 추출"""

    print("=" * 70)
    print("📝 PPTX 리드문 추출")
    print("=" * 70)

    all_leads = []
    stats = defaultdict(int)

    pptx_files = sorted(inputdata_dir.glob("*.pptx"))
    pptx_files = [f for f in pptx_files if not f.name.startswith("~$")]

    print(f"\n발견된 PPTX 파일: {len(pptx_files)}개\n")

    for pptx_file in pptx_files:
        print(f"\n{'─' * 60}")
        print(f"📂 {pptx_file.name}")
        print(f"{'─' * 60}")

        slides_data = extract_texts_with_position(pptx_file)
        file_leads = []

        for slide in slides_data:
            slide_num = slide['slide_num']

            # y_position으로 정렬 (아래쪽에 있는 텍스트가 리드문일 가능성 높음)
            sorted_texts = sorted(slide['texts'], key=lambda x: -x['y_position'])

            for text_info in sorted_texts:
                text = text_info['text']
                is_lead, reason = is_lead_candidate(text)

                if is_lead:
                    lead_data = {
                        'file': pptx_file.name,
                        'slide': slide_num,
                        'text': text,
                        'char_count': len(text),
                        'reason': reason
                    }
                    file_leads.append(lead_data)
                    all_leads.append(lead_data)
                    stats['total'] += 1

        # 파일별 리드문 출력
        if file_leads:
            print(f"\n  추출된 리드문 {len(file_leads)}개:")
            for i, lead in enumerate(file_leads[:10], 1):  # 최대 10개만 표시
                print(f"  {i:2d}. [슬라이드 {lead['slide']:2d}] ({lead['char_count']:2d}자)")
                print(f"      \"{lead['text']}\"")
            if len(file_leads) > 10:
                print(f"      ... 외 {len(file_leads) - 10}개")
        else:
            print("  리드문 없음")

    return all_leads


def analyze_lead_patterns(leads: List[Dict]) -> Dict:
    """리드문 패턴 분석"""

    print("\n" + "=" * 70)
    print("📊 리드문 패턴 분석")
    print("=" * 70)

    analysis = {
        'total_count': len(leads),
        'avg_length': 0,
        'length_distribution': {},
        'common_endings': {},
        'common_keywords': {},
        'style_patterns': []
    }

    if not leads:
        print("분석할 리드문이 없습니다.")
        return analysis

    # 1. 길이 분석
    lengths = [l['char_count'] for l in leads]
    analysis['avg_length'] = sum(lengths) / len(lengths)

    print(f"\n1. 길이 분석")
    print(f"   평균: {analysis['avg_length']:.1f}자")
    print(f"   최소: {min(lengths)}자, 최대: {max(lengths)}자")

    # 길이 분포
    for l in leads:
        bucket = (l['char_count'] // 5) * 5
        key = f"{bucket}-{bucket+4}자"
        analysis['length_distribution'][key] = analysis['length_distribution'].get(key, 0) + 1

    print(f"\n   길이 분포:")
    for bucket in sorted(analysis['length_distribution'].keys()):
        count = analysis['length_distribution'][bucket]
        bar = "█" * (count // 2)
        print(f"   {bucket:>10}: {count:3d} {bar}")

    # 2. 어미 분석
    endings = ['합니다', '입니다', '됩니다', '습니다', '겠습니다', '있습니다',
               '합니다.', '입니다.', '됩니다.']

    print(f"\n2. 어미 분석")
    for ending in endings:
        count = sum(1 for l in leads if l['text'].endswith(ending))
        if count > 0:
            analysis['common_endings'][ending] = count
            pct = count / len(leads) * 100
            print(f"   {ending}: {count}개 ({pct:.1f}%)")

    # 3. 키워드 빈도
    keywords = ['통해', '위해', '함께', '새로운', '혁신', '성장', '지원',
                '만들어', '실현', '추진', '달성', '제공', '창출', '확대',
                '강화', '구축', '도약', '선도', '임팩트', '가치']

    print(f"\n3. 자주 사용되는 키워드")
    keyword_counts = {}
    for kw in keywords:
        count = sum(1 for l in leads if kw in l['text'])
        if count > 0:
            keyword_counts[kw] = count

    for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1])[:10]:
        pct = count / len(leads) * 100
        print(f"   {kw}: {count}개 ({pct:.1f}%)")

    analysis['common_keywords'] = keyword_counts

    # 4. 스타일 패턴 추출
    print(f"\n4. 대표 리드문 예시 (스타일 참고용)")

    # 적정 길이의 좋은 예시 선별
    good_examples = [l for l in leads if 25 <= l['char_count'] <= 40]
    good_examples = sorted(good_examples, key=lambda x: x['char_count'])

    seen_patterns = set()
    for lead in good_examples:
        # 첫 5글자로 패턴 중복 체크
        pattern = lead['text'][:5]
        if pattern not in seen_patterns:
            seen_patterns.add(pattern)
            analysis['style_patterns'].append(lead['text'])
            print(f"   • \"{lead['text']}\" ({lead['char_count']}자)")
            if len(analysis['style_patterns']) >= 20:
                break

    return analysis


def main():
    base_dir = Path(__file__).parent
    inputdata_dir = base_dir / "inputdata"
    output_dir = base_dir / "learning_data"
    output_dir.mkdir(exist_ok=True)

    # 1. 리드문 추출
    leads = extract_leads(inputdata_dir)

    # 2. 패턴 분석
    analysis = analyze_lead_patterns(leads)

    # 3. 결과 저장
    output_path = output_dir / "extracted_leads.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'leads': leads,
            'analysis': analysis
        }, f, ensure_ascii=False, indent=2)

    print(f"\n" + "=" * 70)
    print(f"✅ 리드문 추출 완료!")
    print(f"   총 {len(leads)}개 리드문 추출")
    print(f"   저장 위치: {output_path}")
    print("=" * 70)

    return leads, analysis


if __name__ == "__main__":
    main()
