#!/usr/bin/env python3
"""
PPTX를 PDF로 변환하는 간단한 유틸리티
macOS에서 Keynote/PowerPoint를 사용하여 변환
"""

import subprocess
from pathlib import Path
import tempfile
import shutil


def pptx_to_pdf_keynote(pptx_path: str, output_pdf: str = None) -> str:
    """
    macOS Keynote를 사용하여 PPTX를 PDF로 변환

    Args:
        pptx_path: PPTX 파일 경로
        output_pdf: 출력 PDF 경로 (None이면 자동 생성)

    Returns:
        생성된 PDF 파일 경로
    """
    pptx_path = Path(pptx_path).absolute()

    if not pptx_path.exists():
        raise FileNotFoundError(f"PPTX 파일을 찾을 수 없습니다: {pptx_path}")

    if output_pdf is None:
        output_pdf = pptx_path.parent / f"{pptx_path.stem}.pdf"
    else:
        output_pdf = Path(output_pdf).absolute()

    # AppleScript로 Keynote를 사용하여 변환
    applescript = f'''
    set pptxFile to POSIX file "{pptx_path}" as alias
    set pdfFile to POSIX file "{output_pdf}" as text

    tell application "Keynote"
        activate
        open pptxFile
        delay 2

        tell the front document
            export to file pdfFile as PDF
        end tell

        close the front document saving no
        quit
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and output_pdf.exists():
            print(f"✅ Keynote로 PDF 변환 완료: {output_pdf}")
            return str(output_pdf)
        else:
            raise RuntimeError(f"Keynote 변환 실패: {result.stderr}")

    except Exception as e:
        raise RuntimeError(f"Keynote 변환 오류: {e}")


def pptx_to_pdf_simple(pptx_path: str, output_pdf: str = None) -> str:
    """
    간단한 방법: 사용자에게 수동 변환 요청

    실제로는 python-pptx로 PDF를 생성할 수 없으므로,
    외부 도구나 사용자가 직접 변환해야 합니다.
    """
    pptx_path = Path(pptx_path).absolute()

    if output_pdf is None:
        output_pdf = pptx_path.parent / f"{pptx_path.stem}.pdf"
    else:
        output_pdf = Path(output_pdf).absolute()

    # PDF가 이미 있는지 확인
    if output_pdf.exists():
        print(f"✅ 기존 PDF 사용: {output_pdf}")
        return str(output_pdf)

    # 사용자에게 안내
    print(f"⚠️  PPTX를 PDF로 변환해주세요:")
    print(f"   1. PowerPoint/Keynote로 '{pptx_path.name}' 열기")
    print(f"   2. '다른 이름으로 내보내기' → PDF")
    print(f"   3. '{output_pdf}' 경로로 저장")
    print(f"\n   또는: Keynote를 사용하여 자동 변환하려면 pptx_to_pdf_keynote() 함수를 사용하세요")

    raise FileNotFoundError(f"PDF 파일이 필요합니다: {output_pdf}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python pptx_to_pdf.py input.pptx [output.pdf]")
        sys.exit(1)

    pptx_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else None

    try:
        # Keynote 변환 시도
        pdf_path = pptx_to_pdf_keynote(pptx_file, output_file)
        print(f"\n✅ 변환 완료: {pdf_path}")
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        print("\n대안: PowerPoint나 Keynote로 수동 변환 후 사용하세요")
        sys.exit(1)
