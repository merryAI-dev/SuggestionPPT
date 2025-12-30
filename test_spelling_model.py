"""
파인튜닝된 맞춤법 검사 모델 테스트

PPTX 파일에서 텍스트를 추출하고 맞춤법을 검사합니다.
"""

import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re
from typing import List, Dict

import torch
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer


def extract_texts_from_pptx(pptx_path: Path) -> List[Dict]:
    """PPTX에서 텍스트 추출"""
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
                            if text and len(text) > 5:
                                texts.append({
                                    'slide': slide_num,
                                    'text': text,
                                    'char_count': len(text)
                                })

    except Exception as e:
        print(f"❌ PPTX 처리 실패: {e}")
        return []

    return texts


def check_spelling(model, tokenizer, text: str, device: str = "mps") -> Dict:
    """맞춤법 검사"""

    # 프롬프트 생성 (더 명확하게)
    prompt = f"다음 문장의 맞춤법과 용어 통일성을 검사해주세요. 문제가 없으면 '문제 없음'이라고만 답하세요:\n\n{text}"

    messages = [
        {"role": "user", "content": prompt}
    ]

    # 토크나이징
    text_input = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(text_input, return_tensors="pt").to(device)

    # 생성 (temperature 낮춤)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.1,  # 더 결정적으로
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    # 디코딩
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # 응답에서 assistant 부분만 추출
    if "assistant" in response:
        response = response.split("assistant")[-1].strip()

    # <think> 태그 제거
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

    # 결과 파싱
    has_issue = False
    corrected = None
    issue_type = None

    if "문제 없음" in response or "문제없음" in response:
        has_issue = False
    elif "수정된 문장" in response:
        has_issue = True
        # "수정된 문장:" 다음 부분 추출
        match = re.search(r'수정된 문장[:\s]*\n([^\n]+)', response)
        if match:
            corrected = match.group(1).strip()

        # 수정 유형 추출
        if "맞춤법" in response:
            issue_type = "맞춤법"
        elif "띄어쓰기" in response:
            issue_type = "띄어쓰기"
        elif "용어통일" in response:
            issue_type = "용어통일"

    return {
        'has_issue': has_issue,
        'corrected': corrected,
        'issue_type': issue_type,
        'raw_response': response
    }


def main():
    pptx_path = Path("/Users/boram/Desktop/11월/pptMaker/온드림 1차 합본_1208.pptx")
    model_path = "./qwen3-spelling-checker/final"

    print("=" * 70)
    print("📝 PPTX 맞춤법 검사 (파인튜닝 모델)")
    print("=" * 70)
    print(f"파일: {pptx_path.name}")
    print(f"모델: {model_path}")
    print()

    # 1. PPTX 텍스트 추출
    print("[1/3] PPTX 텍스트 추출 중...")
    texts = extract_texts_from_pptx(pptx_path)

    if not texts:
        print("❌ 텍스트를 찾을 수 없습니다.")
        return

    print(f"   추출된 텍스트: {len(texts)}개")

    # 너무 긴 텍스트나 짧은 텍스트 필터링
    texts = [t for t in texts if 10 <= t['char_count'] <= 100]
    print(f"   검사 대상: {len(texts)}개 (10-100자)")

    # 샘플링 (너무 많으면)
    if len(texts) > 50:
        import random
        texts = random.sample(texts, 50)
        print(f"   샘플링: 50개로 제한")

    # 2. 모델 로드
    print("\n[2/3] 모델 로딩 중...")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"   디바이스: {device}")

    try:
        model = AutoPeftModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True,
        )
        model.to(device)
        model.eval()

        tokenizer = AutoTokenizer.from_pretrained(model_path)
        print(f"   모델 로드 완료")

    except Exception as e:
        print(f"❌ 모델 로드 실패: {e}")
        return

    # 3. 맞춤법 검사
    print("\n[3/3] 맞춤법 검사 중...")
    print("=" * 70)

    issues_found = []

    for idx, item in enumerate(texts, 1):
        text = item['text']
        slide_num = item['slide']

        try:
            result = check_spelling(model, tokenizer, text, device)

            if result['has_issue'] and result['corrected']:
                # 실제 변경사항이 있는지 확인
                if result['corrected'] != text:
                    print(f"\n[{idx}/{len(texts)}] 슬라이드 {slide_num} - ⚠️ 수정 제안")
                    print(f"  원문: {text}")
                    print(f"  수정: {result['corrected']}")
                    print(f"  유형: {result['issue_type']}")

                    issues_found.append({
                        'slide': slide_num,
                        'original': text,
                        'corrected': result['corrected'],
                        'type': result['issue_type']
                    })
                else:
                    print(f"[{idx}/{len(texts)}] 슬라이드 {slide_num} - ✅ 문제 없음")
            else:
                print(f"[{idx}/{len(texts)}] 슬라이드 {slide_num} - ✅ 문제 없음")

        except Exception as e:
            print(f"❌ 검사 실패: {e}")

    # 결과 요약
    print("\n" + "=" * 70)
    print("📊 검사 결과 요약")
    print("=" * 70)
    print(f"총 검사: {len(texts)}개")
    print(f"수정 제안: {len(issues_found)}개")

    if issues_found:
        print("\n📝 수정이 필요한 항목:")
        for issue in issues_found[:20]:  # 최대 20개만 표시
            print(f"\n슬라이드 {issue['slide']} [{issue['type']}]:")
            print(f"  원문: {issue['original']}")
            print(f"  수정: {issue['corrected']}")

        if len(issues_found) > 20:
            print(f"\n... 외 {len(issues_found) - 20}개")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
