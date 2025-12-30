# PPT Maker

자연어로 파워포인트를 생성하고, AI로 맞춤법과 용어 통일성을 검사하는 자동화 도구입니다.

```
"H-온드림 2026년 제안서 만들어줘" → Claude API → slides_data.json → output.pptx
```

---

## 목차

1. [개요](#개요)
2. [설치](#설치)
3. [전체 파일 구조](#전체-파일-구조)
4. [PPT 생성 파이프라인](#ppt-생성-파이프라인)
   - [pipeline.py](#pipelinepy---메인-파이프라인)
   - [generator.py](#generatorpy---슬라이드-콘텐츠-생성)
   - [ppt_generator.py](#ppt_generatorpy---pptx-파일-생성)
5. [품질 검사 시스템](#품질-검사-시스템)
   - [integrated_pptx_checker.py](#integrated_pptx_checkerpy---통합-검사-메인)
   - [ultra_text_extractor.py](#ultra_text_extractorpy---텍스트-추출)
   - [pptx_checker.py](#pptx_checkerpy---규칙-기반-검사)
   - [vision_text_extractor.py](#vision_text_extractorpy---vision-api-추출)
6. [학습 시스템](#학습-시스템)
   - [extractor.py](#extractorpy---콘텐츠-추출)
   - [build_learning_data.py](#build_learning_datapy---패턴-학습)
   - [build_spelling_dataset.py](#build_spelling_datasetpy---맞춤법-데이터셋)
   - [build_fewshot_examples.py](#build_fewshot_examplespy---few-shot-예제)
7. [ML 모델 파인튜닝](#ml-모델-파인튜닝-선택)
   - [finetune_spelling_mps.py](#finetune_spelling_mpspy---맞춤법-모델-파인튜닝)
   - [finetune_qwen3_mps.py](#finetune_qwen3_mpspy---codeforces-데이터셋-파인튜닝)
   - [test_spelling_model.py](#test_spelling_modelpy---모델-테스트)
8. [템플릿 관리](#템플릿-관리)
9. [데이터 포맷](#데이터-포맷)
10. [용어 통일 규칙](#용어-통일-규칙)
11. [문제 해결](#문제-해결)

---

## 개요

### 문제 상황

- 수동으로 PPT 구조를 설계하고 텍스트를 입력하는 반복 작업
- 수백 페이지 문서의 맞춤법과 용어 통일성을 육안으로 검토
- "펠로우/펠로", "H온드림/H-온드림" 같은 표기 불일치 발생

### 해결 방안

1. **PPT 생성 자동화**: 자연어 입력 → Claude API → 구조화된 슬라이드 데이터 → PPTX 파일
2. **3단계 품질 검사**: XML 텍스트 추출 → 규칙 기반 검사 → Claude API 문맥 검토
3. **학습 시스템**: 기존 문서에서 패턴을 학습하여 생성 품질 향상

### 지원 문서 유형

- 제안서
- 결과보고서
- 기획안
- 백서
- 중장기계획
- 컨설팅보고서

---

## 설치

### 필수 요구사항

- Python 3.9 이상
- Anthropic API Key

### 기본 설치

```bash
# 가상환경 생성
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# API 키 설정
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 의존성 목록

**requirements.txt** (기본)
```
python-pptx>=0.6.21    # PPTX 파일 생성 및 조작
pdfplumber>=0.10.0     # PDF 텍스트 추출
anthropic>=0.18.0      # Claude API 클라이언트
```

**requirements_finetune.txt** (ML 모델 파인튜닝용, 선택)
```
torch>=2.1.0
transformers>=4.51.0
datasets>=2.14.0
trl>=0.12.0
peft>=0.13.0
accelerate>=0.25.0
bitsandbytes>=0.41.0
tensorboard
scipy
```

### 폰트 설정

기본 폰트는 HDharmony 패밀리입니다.
- HDharmonyB (Bold) - 챕터, 타이틀용
- HDharmonyM (Medium) - 서브타이틀용
- HDharmonyL (Light) - 리드문용

폰트가 시스템에 설치되어 있어야 PPTX에서 올바르게 렌더링됩니다.

---

## 전체 파일 구조

```
pptMaker/
│
├── [PPT 생성]
│   ├── pipeline.py              # 메인 진입점 (자연어 → PPTX)
│   ├── generator.py             # Claude API로 슬라이드 데이터 생성
│   └── ppt_generator.py         # JSON → PPTX 변환
│
├── [품질 검사]
│   ├── integrated_pptx_checker.py  # 통합 검사 파이프라인 (메인)
│   ├── ultra_text_extractor.py     # XML + Claude API 텍스트 추출
│   ├── vision_text_extractor.py    # Vision API 텍스트 추출 (대안)
│   ├── pptx_checker.py             # 규칙 기반 용어/맞춤법 검사
│   ├── pptx_to_images.py           # PPTX → 이미지 변환
│   └── pptx_to_pdf.py              # PPTX → PDF 변환
│
├── [학습 시스템]
│   ├── extractor.py                # PPTX/PDF 콘텐츠 추출
│   ├── build_learning_data.py      # 학습 패턴 분석 및 생성
│   ├── build_spelling_dataset.py   # 맞춤법 데이터셋 구축
│   ├── build_fewshot_examples.py   # Few-shot 예제 생성
│   └── extract_leads.py            # 리드문 예제 추출
│
├── [템플릿]
│   ├── template_extractor.py       # 템플릿 스타일 추출
│   ├── tem.pptx                    # 기본 템플릿
│   └── template_style.json         # 추출된 스타일 정보
│
├── [ML 파인튜닝] (선택)
│   ├── finetune_spelling_mps.py    # 맞춤법 모델 파인튜닝
│   ├── finetune_qwen3_mps.py       # Qwen3 파인튜닝
│   └── test_spelling_model.py      # 모델 테스트
│
├── [데이터]
│   ├── fewshot_examples.json       # Few-shot 예제 (31개 positive, 12개 negative)
│   ├── learning_data/              # 학습 데이터 폴더
│   │   ├── patterns.json           # 문서 패턴
│   │   └── spelling_dataset.json   # 맞춤법 데이터셋
│   └── inputdata/                  # 학습용 입력 데이터 (PPTX/PDF)
│
├── [설정]
│   ├── requirements.txt            # 기본 의존성
│   ├── requirements_finetune.txt   # 파인튜닝 의존성
│   └── CLAUDE.md                   # Claude Code용 프로젝트 가이드
│
└── [ML 모델] (선택)
    └── qwen3-spelling-checker/     # 파인튜닝된 모델 체크포인트
```

---

## PPT 생성 파이프라인

### pipeline.py - 메인 파이프라인

전체 PPT 생성 흐름을 오케스트레이션하는 메인 진입점입니다.

**사용법**
```bash
# 기본 실행
python pipeline.py "H-온드림 2026년 제안서 만들어줘"

# 출력 파일 지정
python pipeline.py "신한 스퀘어브릿지 결과보고서" result.pptx

# 도움말
python pipeline.py
```

**실행 흐름**
```
[1/3] generator.py로 슬라이드 콘텐츠 생성
     ↓
[2/3] slides_data_generated.json 저장
     ↓
[3/3] ppt_generator.py로 PPTX 생성
     ↓
output.pptx 완성
```

**코드 예시**
```python
from pipeline import run

# 함수로 직접 호출
output_path = run(
    user_input="H-온드림 2026년 제안서 만들어줘",
    output_path="output.pptx",
    template_path="tem.pptx"
)
```

**출력 예시**
```
============================================================
PPT 자동 생성 파이프라인
============================================================

입력: H-온드림 2026년 제안서 만들어줘

[1/3] 슬라이드 콘텐츠 생성 중...
[2/3] JSON 저장 중... (slides_data_generated.json)
[3/3] PPTX 생성 중... (output.pptx)

============================================================
완료! 생성된 파일: output.pptx
슬라이드 수: 12개
============================================================
```

---

### generator.py - 슬라이드 콘텐츠 생성

Claude API를 호출하여 자연어 입력을 구조화된 슬라이드 데이터로 변환합니다.

**사용법**
```bash
python generator.py "H-온드림 2026년 제안서 만들어줘"
```

**핵심 클래스: SlideGenerator**

```python
from generator import SlideGenerator

# 인스턴스 생성
generator = SlideGenerator()  # ANTHROPIC_API_KEY 환경변수 사용

# 또는 API 키 직접 전달
generator = SlideGenerator(api_key="sk-ant-...")

# 슬라이드 데이터 생성
slides_data = generator.generate("H-온드림 2026년 제안서")
```

**생성 원리**

1. `_load_learning_data()`: `learning_data/patterns.json`에서 기존 문서 패턴 로드
2. `_get_reference_examples()`: 문서 유형별 예시 추출 (각 유형별 2개씩, 최대 6개)
3. `_build_system_prompt()`: 패턴과 예시를 포함한 시스템 프롬프트 구성
4. `_build_user_prompt()`: 사용자 입력을 프롬프트로 변환
5. Claude API 호출 (`claude-sonnet-4-20250514` 모델 사용)
6. `_parse_response()`: JSON 응답 파싱 및 검증

**글자 수 제약 (Claude 프롬프트에 포함됨)**

| 필드 | 글자 수 | 설명 |
|------|---------|------|
| chapter | 최대 5자 (번호 제외) | 예: "발견", "채용", "집중" |
| title | 10-20자 | 슬라이드 제목 |
| subtitle | 15-30자 (생략 가능) | 부제목 |
| lead | 25-35자, 한 줄 | 핵심 메시지 (줄바꿈 금지) |

**편의 함수**
```python
from generator import generate_slides

# 한 줄로 슬라이드 생성
result = generate_slides("아산 두어스 기획안 10페이지로")
```

---

### ppt_generator.py - PPTX 파일 생성

JSON 슬라이드 데이터를 실제 PPTX 파일로 변환합니다.

**사용법**
```bash
# PPTX 생성
python ppt_generator.py slides_data.json output.pptx tem.pptx

# 인자 순서: JSON파일 출력파일 템플릿파일
python ppt_generator.py slides_data.json output.pptx

# 템플릿 구조 분석
python ppt_generator.py --analyze tem.pptx
```

**핵심 함수**

1. **load_json_data(json_path)**: JSON 파일에서 슬라이드 데이터 로드

2. **duplicate_slide(prs, index)**: 템플릿 슬라이드 복제
   - 첫 번째 슬라이드를 기준으로 필요한 만큼 복제
   - XML 요소를 deep copy하여 모든 스타일 유지

3. **find_and_replace_text(slide, placeholder, new_text, font_config)**: 플레이스홀더 텍스트 교체
   - 템플릿에서 "Chapter", "Title", "Subtitle", "Lead" 텍스트를 찾아 교체
   - 대소문자 무시하여 매칭

4. **apply_font_style(run, font_config)**: 폰트 스타일 적용
   - 폰트 이름, 크기, 굵기, 색상 설정
   - 한글(동아시아) 폰트 설정 (`a:ea` XML 요소 사용)

5. **generate_pptx(template_path, json_path, output_path)**: 메인 생성 함수

**템플릿 분석 모드**
```bash
python ppt_generator.py --analyze tem.pptx
```

출력 예시:
```
템플릿 분석: tem.pptx
총 슬라이드: 1개

=== Slide 1 ===
  Shape: Title Placeholder
    Text: 'Title'
  Shape: Subtitle Placeholder
    Text: 'Subtitle'
  Shape: Text Placeholder
    Text: 'Chapter'
  Shape: Content Placeholder
    Text: 'Lead'
```

**코드 예시**
```python
from ppt_generator import generate_pptx

# PPTX 생성
generate_pptx(
    template_path="tem.pptx",
    json_path="slides_data.json",
    output_path="output.pptx"
)
```

---

## 품질 검사 시스템

### integrated_pptx_checker.py - 통합 검사 (메인)

3단계 파이프라인으로 PPTX 품질을 검사합니다.

**사용법**
```bash
# 기본 실행 (Knowledge Distillation 모드)
python integrated_pptx_checker.py presentation.pptx

# JSON 리포트 출력
python integrated_pptx_checker.py presentation.pptx --output report.json

# Excel 리포트 출력 (변경 부분 빨간색 표시)
python integrated_pptx_checker.py presentation.pptx --output report.xlsx

# 파인튜닝 모델 경로 지정 (선택)
python integrated_pptx_checker.py presentation.pptx --model ./custom_model/
```

**3단계 검사 파이프라인**

```
Stage 1: Ultra Think 텍스트 추출
    │   - XML 파싱 (1-2초)
    │   - Claude API 구조 분류 (5-10초)
    │   - Chapter/Title/Subtitle/Lead/Contents 자동 분류
    ▼
Stage 2: 하이브리드 검사
    │   - 규칙 기반 검사 (pptx_checker.py)
    │   - 파인튜닝 모델 검사 (선택, 기본값: 스킵)
    │   - 결과 합집합으로 병합
    ▼
Stage 3: Claude API 최종 검토
    │   - 문맥 기반 검사 (스타트업 → 임팩트 스타트업?)
    │   - False Positive 제거
    │   - 스타일/의미 개선 제안
    ▼
최종 리포트 (JSON + Excel)
```

**Knowledge Distillation 모드**

기본값으로 활성화됩니다. 파인튜닝 모델 대신 Few-shot 예제(`fewshot_examples.json`)를 사용합니다.
- 더 빠른 실행 속도
- 별도 모델 설치 불필요
- 31개 positive + 12개 negative 예제 활용

**핵심 함수**

1. **extract_texts_from_pptx(pptx_path)**: Ultra Think 모드로 텍스트 추출
   - `ultra_text_extractor.py` 호출
   - 실패 시 기본 XML 추출로 폴백

2. **check_with_rules(pptx_path)**: 규칙 기반 검사
   - `pptx_checker.py`의 PPTXChecker 클래스 사용
   - 용어 통일, 맞춤법, 띄어쓰기 검사

3. **review_with_claude(pptx_path, texts, merged_issues)**: Claude API 최종 검토
   - 타입별(Chapter/Title/Subtitle/Lead/Contents) 그룹 검사
   - 배치 처리 (200개씩)
   - Few-shot 예제 포함

4. **generate_final_report(...)**: 최종 리포트 생성
   - False Positive 제거
   - 원문/수정안 동일 항목 제거
   - JSON 및 Excel 저장

**리포트 출력 예시**
```
============================================
최종 검사 리포트
============================================

요약:
   - 검사된 텍스트: 127개
   - 발견된 문제: 15건

   타입별:
      - 용어통일: 5건
      - 띄어쓰기: 4건
      - 맞춤법: 3건
      - 문맥기반: 3건

   출처별:
      - rule_based: 6건
      - claude_context: 7건
      - claude_additional: 2건

주요 이슈 (최대 10개):

   1. [슬라이드 3] 용어통일
      원문: "펠로우 프로그램"
      제안: "펠로 프로그램"
      이유: H-온드림 공식 용어는 '펠로'입니다
      (출처: claude_context, 신뢰도: high)

   2. [슬라이드 7] 띄어쓰기
      원문: "할수있는"
      제안: "할 수 있는"
      이유: 의존명사 띄어쓰기
      (출처: rule_based, 신뢰도: high)
```

**코드 예시**
```python
from integrated_pptx_checker import run_integrated_check

report = run_integrated_check(
    pptx_path="presentation.pptx",
    output_path="report.xlsx",
    skip_finetuned=True  # Knowledge Distillation 모드 (기본값)
)

print(f"발견된 이슈: {report['summary']['total_issues']}건")
```

---

### ultra_text_extractor.py - 텍스트 추출

XML 파싱 + Claude API 구조 분류를 결합한 고속 텍스트 추출기입니다.

**사용법**
```bash
# 기본 실행
python ultra_text_extractor.py presentation.pptx

# 결과를 JSON으로 저장
python ultra_text_extractor.py presentation.pptx result.json
```

**동작 원리**

1. **Stage 1: XML 텍스트 추출** (1-2초)
   - PPTX를 ZIP으로 열어 `ppt/slides/slideN.xml` 파싱
   - `<a:t>` 태그에서 모든 텍스트 추출
   - 슬라이드별로 텍스트 리스트 생성

2. **Stage 2: Claude API 구조 분류** (5-10초)
   - 각 슬라이드의 텍스트를 순서와 길이 기반으로 분류
   - Chapter: 첫 번째 짧은 텍스트 (5-15자)
   - Title: 다음 중간 길이 텍스트 (10-40자)
   - Subtitle: 제목 다음 중간~긴 텍스트 (15-60자)
   - Lead: 본문 시작 긴 텍스트 (25자 이상)
   - Contents: 나머지 모든 텍스트

**성능 비교**
| 방식 | 7슬라이드 | 300슬라이드 |
|------|-----------|-------------|
| Vision API | 3분+ | 사용 불가 |
| Ultra Think | 15초 | 1-2분 |

**핵심 함수**

1. **extract_xml_texts(pptx_path)**: XML에서 텍스트 추출
2. **_classify_structure_with_claude(xml_results, api_key)**: Claude API로 구조 분류
3. **ultra_extract_texts(pptx_path, api_key)**: 메인 함수

**출력 구조**
```json
{
  "file": "presentation.pptx",
  "total_slides": 7,
  "slides": [
    {
      "page": 1,
      "chapter": "01. 발견",
      "title": "임팩트 스타트업 발굴",
      "subtitle": "사회문제 해결 스타트업 선발",
      "lead": "사회적 가치와 비즈니스 모델을 갖춘 스타트업을 발굴합니다",
      "contents": ["추가 내용1", "추가 내용2"],
      "raw_texts": ["01. 발견", "임팩트 스타트업 발굴", ...],
      "text_count": 5
    }
  ]
}
```

---

### pptx_checker.py - 규칙 기반 검사

사전 정의된 규칙으로 용어 통일성과 맞춤법을 검사합니다.

**사용법**
```bash
# 기본 실행
python pptx_checker.py presentation.pptx

# Claude API 고급 검사 포함
python pptx_checker.py presentation.pptx --claude

# 결과 파일 경로 지정
python pptx_checker.py presentation.pptx --output report.json
```

**핵심 클래스: PPTXChecker**

```python
from pptx_checker import PPTXChecker

checker = PPTXChecker("presentation.pptx")

# 개별 검사
checker.extract_text()           # 텍스트 추출
checker.check_term_consistency() # 용어 통일성
checker.check_typos()            # 맞춤법 오류
checker.check_number_format()    # 숫자 표기 일관성

# 전체 검사 + 리포트
report = checker.run_all_checks()
```

**검사 항목**

1. **용어 통일성 (TERM_VARIANTS 사전)**
   - 스타트업: "스타트 업", "Start-up", "startup" → "스타트업"
   - 펠로: "펠로우", "Fellow" → "펠로"
   - H-온드림: "H온드림", "H 온드림" → "H-온드림"
   - 총 50+ 개 용어 그룹

2. **맞춤법 오류 (COMMON_TYPOS 사전)**
   - "되있" → "돼있"
   - "할께" → "할게"
   - "갯수" → "개수"
   - 총 20+ 개 패턴

3. **띄어쓰기 오류 (SPACING_ERRORS 패턴)**
   - "할수있" → "할 수 있"
   - "해야할" → "해야 할"

4. **숫자 표기 일관성**
   - "억원" vs "억 원" 혼용 감지
   - 연도 표기 "21년" vs "2021년" 혼용 감지

**Claude API 고급 검사**

`--claude` 옵션 사용 시 추가 검사:
- 문맥 기반 용어 변경 (스타트업 → 임팩트 스타트업)
- 어색한 문장 감지
- 스타일 개선 제안

```python
from pptx_checker import check_with_claude

result = check_with_claude("presentation.pptx", checker.texts)
```

---

### vision_text_extractor.py - Vision API 추출

Claude Vision API를 사용하여 이미지에서 텍스트를 추출합니다. Ultra Think보다 느리지만 특수한 경우에 사용합니다.

**사용법**
```bash
# 단일 이미지에서 텍스트 추출
python vision_text_extractor.py slide_image.png

# PPTX 전체 추출 (내부적으로 이미지 변환)
# 주의: pptx_to_images.py로 먼저 이미지 변환 필요
```

**관련 도구: pptx_to_images.py**
```bash
# PPTX를 이미지로 변환
python pptx_to_images.py presentation.pptx ./output_images/
```

---

## 학습 시스템

### extractor.py - 콘텐츠 추출

PPTX/PDF 파일에서 텍스트와 구조를 추출합니다.

**사용법**
```bash
# inputdata/ 폴더의 모든 파일 추출
python extractor.py
```

**핵심 함수**

1. **extract_pptx_xml(file_path)**: XML 기반 PPTX 텍스트 추출
   - ZIP으로 열어 `ppt/slides/slideN.xml` 직접 파싱
   - shape 단위 → paragraph 단위 → 텍스트 요소 순으로 시도

2. **extract_pptx(file_path)**: PPTX 추출 (XML 우선, python-pptx 폴백)

3. **extract_pdf(file_path)**: PDF 텍스트 추출 (pdfplumber 사용)

4. **analyze_slide_structure(slide_data)**: 슬라이드에서 chapter/title/lead 추정
   - 챕터 패턴 감지: "01. 섹션", "Ⅰ. 소개" 등
   - 길이와 순서 기반으로 title, lead 추정

5. **is_noise_text(text)**: 노이즈 필터링
   - 페이지 번호, 저작권 문구, 플레이스홀더 제외

6. **detect_document_type(filename)**: 파일명에서 문서 유형 추출

**출력 구조**
```python
{
    "source": "파일명.pptx",
    "slide_count": 20,
    "slides": [
        {"page": 1, "texts": ["텍스트1", "텍스트2"]}
    ]
}
```

---

### build_learning_data.py - 패턴 학습

추출된 콘텐츠를 분석하여 학습 데이터 패턴을 생성합니다.

**사용법**
```bash
python build_learning_data.py
# 출력: learning_data/patterns.json
```

**분석 항목**

1. **챕터 형식 패턴**: "01. 한글명", "1. 한글명", "Ⅰ. 한글명" 중 가장 많이 사용된 형식

2. **텍스트 길이 분석**: title 평균 길이, lead 평균 길이

3. **문서 유형별 전형적 섹션**: 제안서의 경우 "사업개요", "추진계획" 등

4. **고품질 예시 추출**: 각 문서 유형별 5개 예시

**출력 구조: learning_data/patterns.json**
```json
{
  "metadata": {
    "source_count": 5,
    "sources": ["파일1.pptx", "파일2.pptx"]
  },
  "style_patterns": {
    "chapter_format": "##. 한글명",
    "title_avg_length": 15,
    "lead_avg_length": 50
  },
  "document_types": {
    "제안서": {
      "avg_slides": 20,
      "typical_sections": ["사업개요", "추진계획", "예산"],
      "examples": [
        {"chapter": "01. 발견", "title": "...", "lead": "..."}
      ]
    }
  }
}
```

---

### build_spelling_dataset.py - 맞춤법 데이터셋

기존 프레젠테이션에서 맞춤법 교정 데이터셋을 구축합니다.

**사용법**
```bash
python build_spelling_dataset.py
# 출력: learning_data/spelling_dataset.json
```

**데이터셋 규모**: 약 3,111개 샘플

---

### build_fewshot_examples.py - Few-shot 예제

맞춤법 데이터셋에서 Few-shot 예제를 추출합니다.

**사용법**
```bash
python build_fewshot_examples.py
# 출력: fewshot_examples.json
```

**출력 구조**
```json
{
  "positive_examples": [
    {"wrong": "펠로우", "correct": "펠로", "reason": "H-온드림 공식 용어"}
  ],
  "negative_examples": [
    {"text": "Executive Summary", "reason": "영어 표현은 변경하지 않음"}
  ]
}
```

**예제 수**: 31개 positive + 12개 negative

---

## ML 모델 파인튜닝 (선택)

맞춤법 검사 모델을 직접 파인튜닝하여 사용할 수 있습니다. Apple Silicon(M1/M2/M3/M4) MPS 백엔드를 지원합니다.

기본적으로 Knowledge Distillation 모드(Few-shot 예제 사용)가 활성화되어 있어 파인튜닝 없이도 품질 검사가 가능합니다.

### 파인튜닝 의존성 설치

```bash
pip install -r requirements_finetune.txt
```

**requirements_finetune.txt 내용**
```
torch>=2.1.0
transformers>=4.51.0
datasets>=2.14.0
trl>=0.12.0
peft>=0.13.0
accelerate>=0.25.0
bitsandbytes>=0.41.0
tensorboard
scipy
```

---

### finetune_spelling_mps.py - 맞춤법 모델 파인튜닝

Qwen3-0.6B 모델을 한국어 맞춤법 교정용으로 파인튜닝합니다.

**사전 준비**
```bash
# 1. 먼저 맞춤법 데이터셋 생성
python build_spelling_dataset.py
# 출력: learning_data/spelling_dataset.json (약 3,111개 샘플)
```

**사용법**
```bash
python finetune_spelling_mps.py
```

**설정 파라미터**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| MODEL_NAME | Qwen/Qwen3-0.6B | 베이스 모델 |
| BATCH_SIZE | 1 | 배치 크기 (MPS에서는 1 권장) |
| GRADIENT_ACCUMULATION_STEPS | 8 | 그래디언트 누적 |
| LEARNING_RATE | 2e-4 | 학습률 |
| NUM_EPOCHS | 3 | 에폭 수 |
| MAX_SEQ_LENGTH | 512 | 최대 시퀀스 길이 |
| LORA_R | 8 | LoRA rank |
| LORA_ALPHA | 16 | LoRA alpha |

**LoRA 타겟 모듈**
- q_proj, k_proj, v_proj, o_proj (어텐션)
- gate_proj, up_proj, down_proj (FFN)

**출력 구조**
```
qwen3-spelling-checker/
├── checkpoint-XXX/     # 체크포인트
├── final/              # 최종 모델
│   ├── adapter_config.json
│   ├── adapter_model.safetensors
│   └── tokenizer 파일들
└── logs/               # 텐서보드 로그
```

**실행 예시**
```
============================================================
Apple Silicon MPS 환경 확인
============================================================
MPS 사용 가능!
   PyTorch 버전: 2.1.0

[1/5] 데이터셋 로딩 중...
   로드된 샘플 수: 3111개

[2/5] 토크나이저 로딩 중...
   토크나이저 로드 완료

[3/5] 모델 로딩 중... (디바이스: mps)
   모델 파라미터: 600,000,000

[4/5] LoRA 설정 중...
   trainable params: 1,572,864 || all params: 601,572,864 || trainable%: 0.2615

[5/5] 트레이너 설정 중...

============================================================
한국어 맞춤법 검사 모델 파인튜닝 시작!
============================================================
   디바이스: mps
   샘플 수: 3111
   에폭: 3
   배치 크기: 1 x 8
============================================================
```

---

### finetune_qwen3_mps.py - CodeForces 데이터셋 파인튜닝

코드 추론 능력 향상을 위해 CodeForces 데이터셋으로 파인튜닝합니다.

**사용법**
```bash
python finetune_qwen3_mps.py
```

**설정 파라미터**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| DATASET_NAME | open-r1/codeforces-cots | 데이터셋 |
| DATASET_SUBSET | solutions_py | Python 버전 |
| MAX_SAMPLES | 1000 | 샘플 제한 (전체: None) |
| MAX_SEQ_LENGTH | 1024 | 최대 시퀀스 길이 |

**출력 디렉토리**: `./qwen3-0.6b-codeforces-mps/`

---

### test_spelling_model.py - 모델 테스트

파인튜닝된 모델로 PPTX 맞춤법을 검사합니다.

**사용법**
```bash
python test_spelling_model.py
```

**기본 설정**
- 입력: `온드림 1차 합본_1208.pptx` (코드에서 수정 필요)
- 모델: `./qwen3-spelling-checker/final`
- 디바이스: MPS (자동 감지)

**동작 원리**

1. PPTX에서 텍스트 추출 (XML 파싱)
2. 10-100자 텍스트만 필터링
3. 50개 샘플링 (너무 많은 경우)
4. 파인튜닝 모델로 맞춤법 검사
5. 수정 제안 출력

**출력 예시**
```
======================================================================
PPTX 맞춤법 검사 (파인튜닝 모델)
======================================================================
파일: 온드림 1차 합본_1208.pptx
모델: ./qwen3-spelling-checker/final

[1/3] PPTX 텍스트 추출 중...
   추출된 텍스트: 150개
   검사 대상: 80개 (10-100자)
   샘플링: 50개로 제한

[2/3] 모델 로딩 중...
   디바이스: mps
   모델 로드 완료

[3/3] 맞춤법 검사 중...
======================================================================

[1/50] 슬라이드 3 - 수정 제안
  원문: 스타트 업이 성공할수있도록 지원합니다
  수정: 스타트업이 성공할 수 있도록 지원합니다
  유형: 띄어쓰기

[2/50] 슬라이드 5 - 문제 없음
...

======================================================================
검사 결과 요약
======================================================================
총 검사: 50개
수정 제안: 8개
```

**코드 예시 - 모델 직접 사용**
```python
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer
import torch

# 모델 로드
model_path = "./qwen3-spelling-checker/final"
model = AutoPeftModelForCausalLM.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

device = "mps" if torch.backends.mps.is_available() else "cpu"
model.to(device)
model.eval()

# 맞춤법 검사
text = "스타트 업이 성공할수있도록 지원합니다."
prompt = f"다음 문장의 맞춤법과 용어 통일성을 검사해주세요:\n\n{text}"

messages = [{"role": "user", "content": prompt}]
text_input = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text_input, return_tensors="pt").to(device)

with torch.no_grad():
    outputs = model.generate(**inputs, max_new_tokens=150, temperature=0.1)

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(response)
```

---

### 파인튜닝 vs Knowledge Distillation

| 항목 | 파인튜닝 모델 | Knowledge Distillation |
|------|---------------|------------------------|
| 설치 | 추가 의존성 필요 | 기본 의존성만 |
| 속도 | 빠름 (로컬 추론) | Claude API 호출 필요 |
| 정확도 | 학습 데이터에 의존 | Claude 수준 |
| 유지보수 | 모델 업데이트 필요 | Few-shot 예제만 수정 |
| 권장 상황 | 대량 문서 처리 | 일반적인 사용 |

**권장**: 대부분의 경우 Knowledge Distillation 모드(기본값)로 충분합니다.

---

### MPS 관련 문제 해결

**메모리 부족**
```bash
# 환경 변수 설정
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0
```

또는 코드에서:
```python
import os
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"
```

**MAX_SEQ_LENGTH 조정**
```python
# 메모리 부족 시 줄이기
MAX_SEQ_LENGTH = 256  # 기본값 512에서 축소
```

**배치 크기**
```python
# MPS에서는 1 권장
BATCH_SIZE = 1
GRADIENT_ACCUMULATION_STEPS = 16  # 누적으로 보완
```

---

## 템플릿 관리

### template_extractor.py

템플릿 PPTX에서 스타일 정보를 JSON으로 추출합니다.

**사용법**
```bash
python template_extractor.py tem.pptx
# 출력: template_style.json
```

### 템플릿 구조

템플릿 파일(`tem.pptx`)은 첫 번째 슬라이드를 기준으로 합니다.

**플레이스홀더 텍스트**
- "Chapter" → chapter 필드로 교체
- "Title" → title 필드로 교체
- "Subtitle" → subtitle 필드로 교체
- "Lead" → lead 필드로 교체

**슬라이드 복제**
- 첫 번째 슬라이드 XML 구조를 deep copy
- 모든 스타일과 레이아웃 유지

---

## 데이터 포맷

### 슬라이드 데이터 JSON

```json
{
  "slides": [
    {
      "page": 1,
      "chapter": "01. 발견",
      "title": "임팩트 스타트업 발굴",
      "subtitle": "사회문제 ���결 스타트업 선발",
      "lead": "사회적 가치와 비즈니스 모델을 갖춘 스타트업을 발굴합니다"
    },
    {
      "page": 2,
      "chapter": "02. 채용",
      "title": "펠로 선발 및 매칭",
      "subtitle": "",
      "lead": "스타트업과 인재를 최적으로 연결합니다"
    }
  ],
  "font_settings": {
    "chapter": {"name": "HDharmonyB", "size": 16, "bold": false, "color": "#000000"},
    "title": {"name": "HDharmonyB", "size": 24, "bold": true, "color": "#333333"},
    "subtitle": {"name": "HDharmonyM", "size": 18, "bold": false, "color": "#666666"},
    "lead": {"name": "HDharmonyL", "size": 14, "color": "#999999"}
  }
}
```

### 검사 리포트 JSON

```json
{
  "file": "presentation.pptx",
  "summary": {
    "total_texts": 127,
    "total_issues": 15,
    "by_type": {"용어통일": 5, "띄어쓰기": 4},
    "by_source": {"rule_based": 6, "claude_context": 7}
  },
  "issues": [
    {
      "source": "claude_context",
      "slide": 3,
      "original": "펠로우 프로그램",
      "suggested": "펠로 프로그램",
      "type": "용어통일",
      "confidence": "high",
      "reason": "H-온드림 공식 용어는 '펠로'입니다"
    }
  ]
}
```

---

## 용어 통일 규칙

품질 검사 시 자동 적용되는 규칙입니다.

### 필수 변경 규칙

| 잘못된 표현 | 올바른 표현 | 비고 |
|-------------|-------------|------|
| 펠로우 | 펠로 | 모든 경우 |
| 기업가 정신, 기업가정신 | 임팩트 앙트프러너십 | 용어 통일 |
| H온드림, H 온드림, H-OnDream | H-온드림 | 브랜드명 |
| 엑셀러레이터 | 액셀러레이터 | 맞춤법 |
| 소셜 벤처 | 소셜벤처 | 붙여쓰기 |
| 펜테크 | 핀테크 | 맞춤법 |

### 띄어쓰기 규칙

| 잘못된 표현 | 올바른 표현 |
|-------------|-------------|
| 할수있, 될수있 | 할 수 있, 될 수 있 |
| 해야할 | 해야 할 |
| 하기위해 | 하기 위해 |
| 억원 | 억 원 |
| 두번째, 첫번째 | 두 번째, 첫 번째 |

### 문맥 기반 규칙

| 상황 | 변경 |
|------|------|
| 임팩트/소셜 맥락에서 "스타트업" | "임팩트 스타트업"으로 변경 고려 |
| 일반 생태계 언급 | 변경하지 않음 |

### 변경하지 않는 표현

- Executive, Summary, Insight 등 영어 표현
- Station F, Co-creation 등 고유명사
- AI, MYSClass 등 약어

---

## 문제 해결

### API 키 오류

```
ANTHROPIC_API_KEY 환경변수를 설정하거나 api_key를 전달해주세요.
```

해결:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 텍스트 추출 실패

```
Ultra Think 추출 실패, 기본 XML 추출로 전환
```

원인: Claude API 호출 실패 또는 PPTX 파일 손상

해결:
- API 키 확인
- PPTX 파일 손상 여부 확인
- 자동으로 XML 추출로 폴백됨

### 폰트 렌더링 문제

증상: PPTX에서 폰트가 깨져 보임

해결:
- HDharmony 폰트 패밀리 시스템 설치
- 또는 `font_settings`에서 시스템에 있는 폰트로 변경

### 모델 로드 실패

```
모델 로드 실패
```

해결: Knowledge Distillation 모드(기본값)를 사용하면 파인튜닝 모델 없이 동작합니다.

### JSON 파싱 오류

```
JSON 파싱 오류
```

해결:
- Claude API 응답 형식 확인
- 자동으로 폴백 결과 반환됨

---

## 라이선스

MIT License

---

**Made with Claude API**