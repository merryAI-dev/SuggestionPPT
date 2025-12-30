"""
한국어 맞춤법/통일성 검사용 파인튜닝 데이터셋 생성

PPTX 파일에서 텍스트를 추출하고, 인위적으로 오류를 삽입하여
(오류 문장, 수정 문장) 쌍의 학습 데이터를 생성합니다.

사용법:
    python build_spelling_dataset.py
"""

import json
import random
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from typing import List, Tuple

# ============================================
# 오류 생성 규칙
# ============================================

# 1. 맞춤법 오류 (틀린 표현 → 맞는 표현)
SPELLING_ERRORS = {
    # 자주 틀리는 맞춤법
    "돼요": "되요",
    "돼서": "되서",
    "됐": "됬",
    "안 됩니다": "않됩니다",
    "안 돼요": "안돼요",
    "할게": "할께",
    "할 거": "할꺼",
    "왠지": "웬지",
    "개수": "갯수",
    "며칠": "몇일",
    "금세": "금새",
    "어이없": "어의없",
    "희한": "희안",
    "설렘": "설레임",
    "오랜만": "오랫만",
    "어떡해": "어떻해",
    "깨끗이": "깨끗히",
    "일찍이": "일찍히",
    "가까이": "가깝게",
    "대로": "데로",
    "든지": "던지",
    "로서": "로써",
    "로써": "로서",
}

# 2. 띄어쓰기 오류
SPACING_ERRORS = {
    "할 수 있": "할수있",
    "해야 할": "해야할",
    "하기 위해": "하기위해",
    "것 같": "것같",
    "수 있": "수있",
    "중 하나": "중하나",
    "더 이상": "더이상",
    "그 동안": "그동안",
    "이 외에": "이외에",
}

# 3. 용어 통일성 오류 (표준 → 비표준)
TERM_VARIANTS = {
    "스타트업": ["스타트 업", "스타트-업", "Start-up"],
    "액셀러레이터": ["엑셀러레이터", "악셀러레이터"],
    "임팩트": ["Impact", "impact"],
    "소셜벤처": ["소셜 벤처", "Social Venture"],
    "비즈니스": ["비지니스", "Business"],
    "프로그램": ["프로그램", "Programme"],
    "네트워크": ["네트웍", "Network"],
    "플랫폼": ["플랫홈", "Platform"],
    "커뮤니티": ["커뮤니케이션", "Community"],
    "데이터": ["데이타", "Data"],
    "컨설팅": ["컨설팅", "Consulting"],
    "멘토링": ["멘토링", "Mentoring"],
    "워크숍": ["워크샵", "Workshop"],
    "펠로우": ["펠로", "Fellow"],
    "H-온드림": ["H온드림", "H 온드림"],
    "억 원": ["억원"],
    "만 원": ["만원"],
}

# 4. 조사 오류
PARTICLE_ERRORS = {
    "을": "를",
    "를": "을",
    "이": "가",
    "가": "이",
    "은": "는",
    "는": "은",
}


def extract_texts_from_pptx(pptx_path: Path) -> List[str]:
    """PPTX에서 텍스트 추출"""
    texts = []

    try:
        with ZipFile(pptx_path, 'r') as zf:
            slide_files = [
                f for f in zf.namelist()
                if f.startswith('ppt/slides/slide') and f.endswith('.xml')
            ]

            for slide_file in slide_files:
                with zf.open(slide_file) as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}

                    for t_elem in root.findall('.//a:t', ns):
                        if t_elem.text and len(t_elem.text.strip()) > 5:
                            texts.append(t_elem.text.strip())
    except Exception as e:
        print(f"  ⚠️ {pptx_path.name} 처리 실패: {e}")

    return texts


def introduce_spelling_error(text: str) -> Tuple[str, str, str]:
    """맞춤법 오류 삽입"""
    for correct, wrong in SPELLING_ERRORS.items():
        if correct in text:
            error_text = text.replace(correct, wrong, 1)
            return error_text, text, "맞춤법"
    return None, None, None


def introduce_spacing_error(text: str) -> Tuple[str, str, str]:
    """띄어쓰기 오류 삽입"""
    for correct, wrong in SPACING_ERRORS.items():
        if correct in text:
            error_text = text.replace(correct, wrong, 1)
            return error_text, text, "띄어쓰기"
    return None, None, None


def introduce_term_error(text: str) -> Tuple[str, str, str]:
    """용어 통일성 오류 삽입"""
    for standard, variants in TERM_VARIANTS.items():
        if standard in text:
            variant = random.choice(variants)
            error_text = text.replace(standard, variant, 1)
            return error_text, text, "용어통일"
    return None, None, None


def create_training_example(wrong: str, correct: str, error_type: str) -> dict:
    """학습 데이터 형식으로 변환"""

    # 방법 1: 프롬프트-완성 형식 (SFT용)
    messages = [
        {
            "role": "user",
            "content": f"다음 문장의 맞춤법과 용어 통일성을 검사하고 수정해주세요:\n\n{wrong}"
        },
        {
            "role": "assistant",
            "content": f"수정된 문장:\n{correct}\n\n수정 유형: {error_type}"
        }
    ]

    return {
        "messages": messages,
        "wrong": wrong,
        "correct": correct,
        "error_type": error_type,
    }


def build_dataset(inputdata_dir: Path, output_path: Path) -> List[dict]:
    """데이터셋 생성"""
    print("=" * 60)
    print("📚 한국어 맞춤법 검사 데이터셋 생성")
    print("=" * 60)

    # 1. PPTX에서 텍스트 추출
    print("\n[1/3] PPTX 파일에서 텍스트 추출 중...")
    all_texts = []

    pptx_files = list(inputdata_dir.glob("*.pptx"))
    print(f"  발견된 PPTX 파일: {len(pptx_files)}개")

    for pptx_file in pptx_files:
        if pptx_file.name.startswith("~$"):  # 임시 파일 제외
            continue
        texts = extract_texts_from_pptx(pptx_file)
        all_texts.extend(texts)
        print(f"  - {pptx_file.name}: {len(texts)}개 텍스트")

    print(f"  총 추출된 텍스트: {len(all_texts)}개")

    # 2. 오류 데이터 생성
    print("\n[2/3] 학습 데이터 생성 중...")
    dataset = []

    error_functions = [
        introduce_spelling_error,
        introduce_spacing_error,
        introduce_term_error,
    ]

    for text in all_texts:
        # 텍스트가 너무 짧거나 길면 제외
        if len(text) < 10 or len(text) > 200:
            continue

        # 각 오류 유형 적용 시도
        for error_func in error_functions:
            wrong, correct, error_type = error_func(text)
            if wrong and wrong != correct:
                example = create_training_example(wrong, correct, error_type)
                dataset.append(example)

    # 3. 추가 합성 데이터 생성 (오류-수정 쌍)
    print("\n[3/3] 합성 데이터 추가 중...")

    synthetic_examples = [
        # 맞춤법 예시
        ("이 프로젝트가 성공적으로 됬습니다.", "이 프로젝트가 성공적으로 됐습니다.", "맞춤법"),
        ("내일 회의에서 발표할께요.", "내일 회의에서 발표할게요.", "맞춤법"),
        ("몇일 후에 결과가 나옵니다.", "며칠 후에 결과가 나옵니다.", "맞춤법"),
        ("금새 해결될 것 같습니다.", "금세 해결될 것 같습니다.", "맞춤법"),
        ("설레임을 감출 수 없었다.", "설렘을 감출 수 없었다.", "맞춤법"),
        ("오랫만에 만나서 반갑습니다.", "오랜만에 만나서 반갑습니다.", "맞춤법"),

        # 띄어쓰기 예시
        ("이 문제를 해결할수있습니다.", "이 문제를 해결할 수 있습니다.", "띄어쓰기"),
        ("성공하기위해 노력합니다.", "성공하기 위해 노력합니다.", "띄어쓰기"),
        ("이것이 중요한것같습니다.", "이것이 중요한 것 같습니다.", "띄어쓰기"),
        ("더이상 지체할 수 없습니다.", "더 이상 지체할 수 없습니다.", "띄어쓰기"),

        # 용어 통일 예시
        ("스타트 업 생태계가 성장하고 있습니다.", "스타트업 생태계가 성장하고 있습니다.", "용어통일"),
        ("엑셀러레이터 프로그램에 참여했습니다.", "액셀러레이터 프로그램에 참여했습니다.", "용어통일"),
        ("소셜 벤처 지원 사업을 진행합니다.", "소셜벤처 지원 사업을 진행합니다.", "용어통일"),
        ("비지니스 모델을 개선했습니다.", "비즈니스 모델을 개선했습니다.", "용어통일"),
        ("플랫홈 개발이 완료되었습니다.", "플랫폼 개발이 완료되었습니다.", "용어통일"),
        ("총 10억원을 투자받았습니다.", "총 10억 원을 투자받았습니다.", "용어통일"),
        ("H온드림 프로그램에 선발되었습니다.", "H-온드림 프로그램에 선발되었습니다.", "용어통일"),
        ("워크샵을 개최할 예정입니다.", "워크숍을 개최할 예정입니다.", "용어통일"),

        # 복합 오류 예시
        ("스타트 업이 성공할수있도록 지원합니다.", "스타트업이 성공할 수 있도록 지원합니다.", "복합"),
        ("엑셀러레이터 프로그램이 곧 시작될께요.", "액셀러레이터 프로그램이 곧 시작될게요.", "복합"),
    ]

    for wrong, correct, error_type in synthetic_examples:
        example = create_training_example(wrong, correct, error_type)
        dataset.append(example)

    # 중복 제거
    seen = set()
    unique_dataset = []
    for item in dataset:
        key = (item["wrong"], item["correct"])
        if key not in seen:
            seen.add(key)
            unique_dataset.append(item)

    dataset = unique_dataset

    # 데이터셋 저장
    print(f"\n📊 생성된 데이터셋 통계:")
    print(f"  - 총 샘플 수: {len(dataset)}개")

    # 오류 유형별 통계
    error_counts = {}
    for item in dataset:
        error_type = item["error_type"]
        error_counts[error_type] = error_counts.get(error_type, 0) + 1

    for error_type, count in error_counts.items():
        print(f"  - {error_type}: {count}개")

    # JSON 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"\n💾 데이터셋 저장: {output_path}")

    # Hugging Face 형식으로도 저장 (JSONL)
    jsonl_path = output_path.with_suffix('.jsonl')
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f"💾 JSONL 저장: {jsonl_path}")

    return dataset


def main():
    # 경로 설정
    base_dir = Path(__file__).parent
    inputdata_dir = base_dir / "inputdata"
    output_path = base_dir / "learning_data" / "spelling_dataset.json"

    # learning_data 디렉토리 생성
    output_path.parent.mkdir(exist_ok=True)

    # 데이터셋 생성
    dataset = build_dataset(inputdata_dir, output_path)

    print("\n" + "=" * 60)
    print("✅ 데이터셋 생성 완료!")
    print("=" * 60)
    print("\n다음 단계: 파인튜닝 실행")
    print("  python finetune_spelling_mps.py")


if __name__ == "__main__":
    main()
