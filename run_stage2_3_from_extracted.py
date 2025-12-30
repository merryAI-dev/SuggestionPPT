"""
Stage 2-3만 실행 (이미 추출된 텍스트 사용)
기존 샘플링 방식 유지, 범위만 확대
"""

import json
import sys
from pathlib import Path

# integrated_pptx_checker에서 필요한 함수들 임포트
from integrated_pptx_checker import (
    check_with_finetuned_model,
    check_with_rules,
    merge_issues,
    review_with_claude,
    generate_final_report,
    save_report_as_excel
)

def run_stage2_3_from_extracted(extracted_json_path: str, pptx_path: str, output_path: str):
    """추출된 텍스트로 Stage 2-3만 실행"""

    extracted_json_path = Path(extracted_json_path)
    pptx_path = Path(pptx_path)
    output_path_str = str(output_path)

    # 추출된 텍스트 로드
    print("\n" + "=" * 70)
    print("📂 추출된 텍스트 로드")
    print("=" * 70)

    with open(extracted_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    texts = data['texts']
    print(f"✅ {len(texts)}개 텍스트 로드 완료")

    # 출력 형식 감지
    if output_path_str.endswith('.xlsx'):
        output_format = 'excel'
        json_output_path = output_path_str.rsplit('.', 1)[0] + '.json'
    else:
        output_format = 'json'
        json_output_path = output_path_str

    # Stage 2: 파인튜닝 + 규칙 기반 (샘플링 300개)
    print("\n" + "=" * 70)
    print("🔬 Stage 2: 파인튜닝 모델 + 규칙 기반 검사")
    print("=" * 70)

    model_path = "./qwen3-spelling-checker/final"
    model_issues = check_with_finetuned_model(texts, model_path)
    rule_issues = check_with_rules(pptx_path)
    merged_issues = merge_issues(model_issues, rule_issues)

    # Stage 3: Claude API 검토 (샘플링 200개)
    claude_result = review_with_claude(pptx_path, texts, merged_issues)

    # 최종 리포트
    report = generate_final_report(pptx_path, texts, merged_issues, claude_result, Path(json_output_path))

    # Excel 저장
    if output_format == 'excel':
        save_report_as_excel(report, output_path_str, all_texts=texts)

    print("\n" + "=" * 70)
    print("✅ Stage 2-3 완료!")
    print("=" * 70)

    return report


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Stage 2-3 실행 (추출된 텍스트 사용)")
        print("-" * 40)
        print("사용법: python run_stage2_3_from_extracted.py <extracted.json> <original.pptx> <output.xlsx>")
        print()
        print("예시:")
        print("  python run_stage2_3_from_extracted.py test_extracted_texts.json test.pptx test_report.xlsx")
        sys.exit(0)

    extracted_json = sys.argv[1]
    pptx_file = sys.argv[2]
    output_file = sys.argv[3]

    run_stage2_3_from_extracted(extracted_json, pptx_file, output_file)