#!/usr/bin/env python3
"""
PPTX를 이미지로 변환하는 유틸리티
각 슬라이드를 PNG 이미지로 저장
"""

import os
import tempfile
from pathlib import Path
from typing import List
import subprocess


def pptx_to_images(pptx_path: str, output_dir: str = None, dpi: int = 150) -> List[str]:
    """
    PPTX 파일을 이미지로 변환

    Args:
        pptx_path: PPTX 파일 경로
        output_dir: 출력 디렉토리 (None이면 임시 디렉토리)
        dpi: 이미지 해상도 (기본 150)

    Returns:
        생성된 이미지 파일 경로 리스트
    """
    pptx_path = Path(pptx_path)

    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX 파일을 찾을 수 없습니다: {pptx_path}")

    # 출력 디렉토리 설정
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="pptx_images_")
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📄 PPTX를 이미지로 변환 중: {pptx_path.name}")
    print(f"📁 출력 디렉토리: {output_dir}")

    # macOS에서 sips + qlmanage를 사용한 변환 시도
    try:
        image_files = _convert_with_macos_tools(pptx_path, output_dir, dpi)
        if image_files:
            return image_files
    except Exception as e:
        print(f"   ⚠️ macOS 도구 변환 실패: {e}")

    # LibreOffice를 사용한 변환 시도
    try:
        image_files = _convert_with_libreoffice(pptx_path, output_dir)
        if image_files:
            return image_files
    except Exception as e:
        print(f"   ⚠️ LibreOffice 변환 실패: {e}")

    # pdf2image를 사용한 변환 (PPTX → PDF → 이미지)
    try:
        image_files = _convert_via_pdf(pptx_path, output_dir, dpi)
        if image_files:
            return image_files
    except Exception as e:
        print(f"   ⚠️ PDF 경유 변환 실패: {e}")

    raise RuntimeError("모든 변환 방법이 실패했습니다. LibreOffice 또는 pdf2image를 설치해주세요.")


def _convert_with_macos_tools(pptx_path: Path, output_dir: Path, dpi: int) -> List[str]:
    """macOS 내장 도구를 사용한 변환 (cupsfilter 또는 qlmanage → pdf2image)"""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image 패키지가 필요합니다: pip install pdf2image")

    output_dir = Path(output_dir)
    pdf_path = output_dir / f"{pptx_path.stem}.pdf"

    # 먼저 cupsfilter로 PDF 변환 시도
    try:
        result = subprocess.run(
            ["cupsfilter", str(pptx_path)],
            capture_output=True,
            timeout=60
        )

        if result.returncode == 0 and result.stdout:
            with open(pdf_path, 'wb') as f:
                f.write(result.stdout)
            print(f"   ✅ cupsfilter로 PDF 생성: {pdf_path.name}")
        else:
            raise RuntimeError("cupsfilter 실패")

    except Exception as e:
        print(f"   ⚠️  cupsfilter 실패 ({e}), qlmanage 시도 중...")

        # qlmanage로 PDF 생성 시도
        result = subprocess.run(
            ["qlmanage", "-t", "-s", "2048", "-o", str(output_dir), str(pptx_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        # qlmanage는 .png.pdf 형식으로 생성할 수 있음
        possible_pdf = output_dir / f"{pptx_path.stem}.png.pdf"
        if possible_pdf.exists():
            possible_pdf.rename(pdf_path)

        if not pdf_path.exists():
            raise RuntimeError("macOS 도구로 PDF 생성 실패")

    # PDF를 이미지로 변환
    images = convert_from_path(str(pdf_path), dpi=dpi)

    image_files = []
    for i, image in enumerate(images, 1):
        image_path = output_dir / f"slide_{i:03d}.png"
        image.save(str(image_path), "PNG")
        image_files.append(str(image_path))

    print(f"   ✅ {len(image_files)}개 슬라이드 이미지 생성 (macOS → PDF → PNG)")
    return image_files


def _convert_with_libreoffice(pptx_path: Path, output_dir: Path) -> List[str]:
    """LibreOffice를 사용한 변환 (PPTX → PDF → PNG)"""
    # PPTX를 PDF로 변환
    result = subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx_path)],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice PDF 변환 실패: {result.stderr}")

    pdf_path = output_dir / f"{pptx_path.stem}.pdf"

    if not pdf_path.exists():
        raise RuntimeError("PDF 파일이 생성되지 않았습니다")

    # PDF를 이미지로 변환
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(str(pdf_path), dpi=150)

        image_files = []
        for i, image in enumerate(images, 1):
            image_path = output_dir / f"slide_{i:03d}.png"
            image.save(str(image_path), "PNG")
            image_files.append(str(image_path))

        print(f"   ✅ {len(image_files)}개 슬라이드 이미지 생성")
        return image_files

    except ImportError:
        raise RuntimeError("pdf2image 패키지가 필요합니다: pip install pdf2image")


def _convert_via_pdf(pptx_path: Path, output_dir: Path, dpi: int) -> List[str]:
    """python-pptx로 PDF 생성 후 이미지 변환"""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image 패키지가 필요합니다: pip install pdf2image")

    # macOS에서 기본 제공하는 textutil이나 다른 도구 사용 불가능
    # LibreOffice 필요
    raise RuntimeError("이 방법은 LibreOffice가 필요합니다")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python pptx_to_images.py input.pptx [output_dir]")
        sys.exit(1)

    pptx_file = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        images = pptx_to_images(pptx_file, output_directory)
        print(f"\n✅ 변환 완료: {len(images)}개 이미지")
        for img in images:
            print(f"   - {img}")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        sys.exit(1)
