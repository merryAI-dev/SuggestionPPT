#!/usr/bin/env python3
"""
PPTX 템플릿 XML 형식 추출기
템플릿 파일을 분석하여 스타일 정보(폰트, 색상, 위치, 크기)를 추출합니다.
"""

import json
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


# XML 네임스페이스
NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'
}


@dataclass
class TextStyle:
    """텍스트 스타일 정보"""
    font_name: str = "Arial"
    font_size: int = 14  # 포인트
    bold: bool = False
    italic: bool = False
    color: str = "#000000"  # HEX 색상
    alignment: str = "left"  # left, center, right


@dataclass
class ShapeInfo:
    """Shape 정보"""
    name: str
    placeholder_type: str  # chapter, title, subtitle, lead
    x: int  # EMU (English Metric Units)
    y: int
    width: int
    height: int
    text: str
    style: TextStyle


def emu_to_pt(emu: int) -> float:
    """EMU를 포인트로 변환 (1pt = 12700 EMU)"""
    return emu / 12700


def extract_color(rPr_elem) -> str:
    """rPr 요소에서 색상 추출"""
    # solidFill > srgbClr (직접 RGB)
    srgb = rPr_elem.find('.//a:srgbClr', NS)
    if srgb is not None:
        return f"#{srgb.get('val', '000000')}"

    # solidFill > schemeClr (테마 색상)
    scheme = rPr_elem.find('.//a:schemeClr', NS)
    if scheme is not None:
        scheme_map = {
            'dk1': '#000000',
            'lt1': '#FFFFFF',
            'dk2': '#44546A',
            'lt2': '#E7E6E6',
            'accent1': '#4472C4',
            'accent2': '#ED7D31',
            'tx1': '#000000',
            'tx2': '#44546A',
            'bg1': '#FFFFFF',
            'bg2': '#E7E6E6',
        }
        return scheme_map.get(scheme.get('val'), '#000000')

    return "#000000"


def extract_text_style(sp_elem) -> TextStyle:
    """Shape 요소에서 텍스트 스타일 추출"""
    style = TextStyle()

    # txBody 찾기
    txBody = sp_elem.find('.//p:txBody', NS)
    if txBody is None:
        return style

    # 첫 번째 run의 속성 가져오기
    rPr = txBody.find('.//a:rPr', NS)
    if rPr is not None:
        # 폰트 크기 (100분의 1 포인트 단위)
        sz = rPr.get('sz')
        if sz:
            style.font_size = int(int(sz) / 100)

        # 굵게
        style.bold = rPr.get('b') == '1'

        # 기울임
        style.italic = rPr.get('i') == '1'

        # 색상
        style.color = extract_color(rPr)

        # 폰트 이름
        latin = rPr.find('a:latin', NS)
        if latin is not None:
            style.font_name = latin.get('typeface', 'Arial')

    # 정렬
    pPr = txBody.find('.//a:pPr', NS)
    if pPr is not None:
        algn = pPr.get('algn', 'l')
        style.alignment = {'l': 'left', 'ctr': 'center', 'r': 'right'}.get(algn, 'left')

    return style


def detect_placeholder_type(text: str, shape_name: str) -> Optional[str]:
    """텍스트나 shape 이름으로 placeholder 타입 감지"""
    text_lower = text.lower().strip()
    name_lower = shape_name.lower()

    if 'chapter' in text_lower or 'chapter' in name_lower:
        return 'chapter'
    elif 'subtitle' in text_lower or 'subtitle' in name_lower:
        return 'subtitle'
    elif 'title' in text_lower or 'title' in name_lower:
        return 'title'
    elif 'lead' in text_lower or 'lead' in name_lower:
        return 'lead'

    return None


def extract_shapes_from_slide(xml_content: bytes) -> list[ShapeInfo]:
    """슬라이드 XML에서 Shape 정보 추출"""
    shapes = []
    root = ET.fromstring(xml_content)

    for sp in root.findall('.//p:sp', NS):
        # Shape 이름
        cNvPr = sp.find('.//p:cNvPr', NS)
        shape_name = cNvPr.get('name', '') if cNvPr is not None else ''

        # 텍스트 추출
        texts = []
        for t in sp.findall('.//a:t', NS):
            if t.text:
                texts.append(t.text)
        text = ''.join(texts).strip()

        if not text:
            continue

        # placeholder 타입 감지
        placeholder_type = detect_placeholder_type(text, shape_name)
        if not placeholder_type:
            continue

        # 위치/크기 추출
        xfrm = sp.find('.//a:xfrm', NS)
        if xfrm is None:
            continue

        off = xfrm.find('a:off', NS)
        ext = xfrm.find('a:ext', NS)

        x = int(off.get('x', 0)) if off is not None else 0
        y = int(off.get('y', 0)) if off is not None else 0
        width = int(ext.get('cx', 0)) if ext is not None else 0
        height = int(ext.get('cy', 0)) if ext is not None else 0

        # 스타일 추출
        style = extract_text_style(sp)

        shapes.append(ShapeInfo(
            name=shape_name,
            placeholder_type=placeholder_type,
            x=x, y=y, width=width, height=height,
            text=text,
            style=style
        ))

    return shapes


def extract_template_style(template_path: str) -> dict:
    """
    템플릿에서 전체 스타일 정보 추출

    Returns:
        {
            "template": "파일명",
            "slide_width": 12192000,  # EMU
            "slide_height": 6858000,
            "placeholders": {
                "chapter": { "x": ..., "y": ..., "style": {...} },
                "title": { ... },
                "subtitle": { ... },
                "lead": { ... }
            }
        }
    """
    result = {
        "template": Path(template_path).name,
        "placeholders": {}
    }

    with zipfile.ZipFile(template_path, 'r') as zf:
        # 프레젠테이션 크기 가져오기
        try:
            pres_xml = zf.read('ppt/presentation.xml')
            pres_root = ET.fromstring(pres_xml)
            sldSz = pres_root.find('.//p:sldSz', NS)
            if sldSz is not None:
                result['slide_width'] = int(sldSz.get('cx', 12192000))
                result['slide_height'] = int(sldSz.get('cy', 6858000))
        except:
            result['slide_width'] = 12192000
            result['slide_height'] = 6858000

        # 첫 번째 슬라이드에서 placeholder 추출
        slide_xml = zf.read('ppt/slides/slide1.xml')
        shapes = extract_shapes_from_slide(slide_xml)

        for shape in shapes:
            result['placeholders'][shape.placeholder_type] = {
                'name': shape.name,
                'x': shape.x,
                'y': shape.y,
                'width': shape.width,
                'height': shape.height,
                'x_pt': round(emu_to_pt(shape.x), 1),
                'y_pt': round(emu_to_pt(shape.y), 1),
                'width_pt': round(emu_to_pt(shape.width), 1),
                'height_pt': round(emu_to_pt(shape.height), 1),
                'original_text': shape.text,
                'style': asdict(shape.style)
            }

    return result


def print_template_info(template_path: str):
    """템플릿 정보를 보기 좋게 출력"""
    info = extract_template_style(template_path)

    print(f"\n{'='*60}")
    print(f"템플릿 분석: {info['template']}")
    print(f"{'='*60}")
    print(f"슬라이드 크기: {info['slide_width']} x {info['slide_height']} EMU")
    print(f"            ({round(emu_to_pt(info['slide_width']), 1)} x {round(emu_to_pt(info['slide_height']), 1)} pt)")

    print(f"\n{'─'*60}")
    print("Placeholder 정보:")
    print(f"{'─'*60}")

    for ptype, pinfo in info['placeholders'].items():
        print(f"\n[{ptype.upper()}]")
        print(f"  원본 텍스트: '{pinfo['original_text']}'")
        print(f"  위치: ({pinfo['x_pt']}pt, {pinfo['y_pt']}pt)")
        print(f"  크기: {pinfo['width_pt']}pt x {pinfo['height_pt']}pt")
        print(f"  스타일:")
        style = pinfo['style']
        print(f"    폰트: {style['font_name']} {style['font_size']}pt", end='')
        if style['bold']:
            print(' [굵게]', end='')
        if style['italic']:
            print(' [기울임]', end='')
        print()
        print(f"    색상: {style['color']}")
        print(f"    정렬: {style['alignment']}")

    return info


def save_template_style(template_path: str, output_path: str = None):
    """템플릿 스타일을 JSON으로 저장"""
    info = extract_template_style(template_path)

    if output_path is None:
        output_path = Path(template_path).stem + "_style.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"스타일 저장: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys

    template = sys.argv[1] if len(sys.argv) > 1 else "tem.pptx"

    info = print_template_info(template)
    save_template_style(template, "template_style.json")
