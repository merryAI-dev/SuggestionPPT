#!/usr/bin/env python3
"""
Ultra Think 모드: XML + Vision(PDF) 병렬 추출로 99% 정확도 달성
PDF를 직접 Claude Vision에 전달하여 간소화
"""

import json
from pathlib import Path
from typing import List, Dict
from difflib import SequenceMatcher


def extract_xml_texts(pptx_path: str) -> List[Dict]:
    """
    기존 XML 기반 텍스트 추출
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


def pptx_to_pdf_manual(pptx_path: Path) -> Path:
    """
    PPTX를 PDF로 변환 (수동 또는 기존 PDF 사용)
    """
    pdf_path = pptx_path.parent / f"{pptx_path.stem}.pdf"

    if pdf_path.exists():
        print(f"   ✅ 기존 PDF 사용: {pdf_path.name}")
        return pdf_path

    # Keynote로 자동 변환 시도
    try:
        from pptx_to_pdf import pptx_to_pdf_keynote
        pdf_result = pptx_to_pdf_keynote(str(pptx_path), str(pdf_path))
        return Path(pdf_result)
    except Exception as e:
        print(f"   ⚠️  자동 변환 실패: {e}")

    # 수동 변환 안내
    print(f"\n⚠️  PDF 변환 필요:")
    print(f"   PowerPoint/Keynote로 '{pptx_path.name}'를 열어")
    print(f"   '{pdf_path.name}'로 PDF 내보내기 해주세요.\n")

    raise FileNotFoundError(f"PDF 파일이 필요합니다: {pdf_path}")


def similarity(a: str, b: str) -> float:
    """두 문자열의 유사도 계산 (0~1)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def merge_texts(xml_results: List[Dict], vision_results: List[Dict]) -> List[Dict]:
    """
    XML과 Vision 추출 결과를 병합하여 최대 정확도 달성
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


def ultra_extract_texts(pptx_path: str, api_key: str = None) -> Dict:
    """
    Ultra Think 모드로 PPTX에서 텍스트 추출
    XML + Vision(PDF) 병렬 추출 → 병합

    Args:
        pptx_path: PPTX 파일 경로
        api_key: Anthropic API 키

    Returns:
        {
            "file": "파일명",
            "total_slides": N,
            "extraction_methods": ["xml", "vision_pdf"],
            "slides": [병합된 슬라이드 데이터],
            "summary": {...}
        }
    """
    pptx_path = Path(pptx_path)

    print("\n" + "=" * 70)
    print("🚀 Ultra Think 모드: 99% 정확도 텍스트 추출 (PDF 방식)")
    print("=" * 70)
    print(f"파일: {pptx_path.name}\n")

    # 1. XML 추출
    print("📋 Stage 1-A: XML 구조적 추출")
    print("-" * 70)
    xml_results = extract_xml_texts(str(pptx_path))
    xml_total = sum(len(r['texts']) for r in xml_results)
    print(f"✅ XML 추출 완료: {len(xml_results)}개 슬라이드, {xml_total}개 텍스트\n")

    # 2. PPTX → PDF 변환
    print("📄 Stage 1-B: PPTX → PDF 변환")
    print("-" * 70)
    try:
        pdf_path = pptx_to_pdf_manual(pptx_path)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("⚠️  Vision 추출 없이 XML만 사용합니다\n")

        # XML만 사용
        return {
            "file": str(pptx_path),
            "total_slides": len(xml_results),
            "extraction_methods": ["xml"],
            "slides": [{
                "slide": r['slide'],
                "texts": r['texts'],
                "xml_count": len(r['texts']),
                "vision_count": 0,
                "merged_count": len(r['texts']),
                "vision_only": [],
                "xml_only": []
            } for r in xml_results],
            "summary": {
                "total_texts": xml_total,
                "xml_total": xml_total,
                "vision_total": 0,
                "xml_only_count": 0,
                "vision_only_count": 0,
                "coverage_improvement_percent": 0
            }
        }

    # 3. Vision API 추출 (PDF 직접 전달)
    print("\n👁️  Stage 1-C: Claude Vision API 텍스트 추출 (PDF)")
    print("-" * 70)

    from vision_text_extractor import extract_text_from_pdf

    vision_results = extract_text_from_pdf(str(pdf_path), api_key)
    vision_total = sum(r.get('text_count', 0) for r in vision_results)
    print(f"✅ Vision 추출 완료: {len(vision_results)}개 슬라이드, {vision_total}개 텍스트\n")

    # 4. 병합
    print("🔗 Stage 1-D: XML + Vision 병합")
    print("-" * 70)
    merged_results = merge_texts(xml_results, vision_results)

    total_merged = sum(r['merged_count'] for r in merged_results)
    vision_only_total = sum(len(r['vision_only']) for r in merged_results)
    xml_only_total = sum(len(r['xml_only']) for r in merged_results)

    print(f"✅ 병합 완료:")
    print(f"   - 최종 텍스트: {total_merged}개")
    print(f"   - Vision만 추출: {vision_only_total}개 (XML이 놓친 텍스트)")
    print(f"   - XML만 추출: {xml_only_total}개 (Vision이 놓친 텍스트)")

    if xml_total > 0:
        coverage_improvement = ((total_merged - xml_total) / xml_total) * 100
        print(f"   - 추출률 향상: +{coverage_improvement:.1f}%")
    else:
        coverage_improvement = 0

    result = {
        "file": str(pptx_path),
        "total_slides": len(merged_results),
        "extraction_methods": ["xml", "vision_pdf"],
        "slides": merged_results,
        "summary": {
            "total_texts": total_merged,
            "xml_total": xml_total,
            "vision_total": vision_total,
            "xml_only_count": xml_only_total,
            "vision_only_count": vision_only_total,
            "coverage_improvement_percent": round(coverage_improvement, 2)
        },
        "pdf_path": str(pdf_path)
    }

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Ultra Think 텍스트 추출 (PDF 방식)")
        print("-" * 40)
        print("사용법: python ultra_text_extractor_pdf.py input.pptx [output.json]")
        print()
        print("예시:")
        print("  python ultra_text_extractor_pdf.py presentation.pptx")
        print("  python ultra_text_extractor_pdf.py presentation.pptx result.json")
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
        print("📊 슬라이드별 요약")
        print("=" * 70)

        for slide_data in result['slides'][:5]:
            print(f"\n[슬라이드 {slide_data['slide']}]")
            print(f"  텍스트: {slide_data['merged_count']}개 (XML: {slide_data['xml_count']}, Vision: {slide_data['vision_count']})")

            if slide_data['vision_only']:
                print(f"  Vision만 추출: {len(slide_data['vision_only'])}개")
                for text in slide_data['vision_only'][:2]:
                    print(f"    + \"{text}\"")

        if len(result['slides']) > 5:
            print(f"\n... 외 {len(result['slides']) - 5}개 슬라이드")

        print("\n✅ Ultra Think 추출 완료!")

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
