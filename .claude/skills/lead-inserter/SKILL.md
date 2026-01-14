---
name: lead-inserter
description: 기존 PPT에 리드문 자동 생성 및 삽입 스킬. 슬라이드 구조를 추출하고 각 슬라이드에 맞는 리드문을 생성하여 삽입합니다. "리드문 넣어줘", "슬라이드 설명 추가", "리드 생성" 등의 요청에 응답합니다.
allowed-tools: Bash(python3:*), Read, Write, AskUserQuestion
---

# 리드문 자동 삽입 스킬

기존 PPTX 파일에서 슬라이드 구조를 추출하고, 리드문을 자동 생성하여 삽입하는 스킬입니다.

## 워크플로우

### Phase 1: 추출 (Extract)

#### Step 1-1: 입력 수집

사용자에게 다음 정보를 요청합니다:

```
리드문 자동 삽입을 시작합니다!

다음 정보를 알려주세요:

1. **소스 PPTX 파일**: (리드문을 추가할 파일)
   예: presentation.pptx

2. **템플릿 파일**: (기본: tem.pptx)
   - tem.pptx (기본)
   - 커스텀 템플릿 경로

3. **출력 파일명**: (기본: 원본명_with_leads.pptx)
```

#### Step 1-2: 환경 검증

```
파일 검증:
✓ presentation.pptx 발견
✓ tem.pptx 발견

ANTHROPIC_API_KEY 환경변수:
✓ 설정됨
```

#### Step 1-3: 구조 추출

```bash
python ultra_text_extractor.py presentation.pptx extracted_structure.json
```

실행 중:
- XML 파싱 중... (1-2초)
- Claude API 구조 분류 중... (5-10초)
- 총 15개 슬라이드 추출 완료

#### Step 1-4: 추출 결과 표시

```
=== 추출된 구조 ===

총 슬라이드: 15개

[Slide 1]
- Chapter:
- Title: H-온드림 2026년 제안서
- Subtitle: 임팩트 스타트업 발굴 육성
- Lead: (없음) ← 생성 필요

[Slide 2]
- Chapter: 01. 발견
- Title: Born-AI 세대 창업팀 발굴
- Subtitle:
- Lead: (없음) ← 생성 필요

[Slide 3]
- Chapter: 01. 발견
- Title: 대학생 중심 해커톤 운영
- Subtitle: 아이디어 발굴 및 팀 빌딩
- Lead: (없음) ← 생성 필요

...

리드문이 필요한 슬라이드: 12개
```

---

### Phase 2: 생성 (Generate)

#### Step 2-1: 리드문 생성 시작

리드문이 없는 각 슬라이드에 대해:

1. **컨텍스트 구성**:
```
슬라이드 2 컨텍스트:
- Chapter: 01. 발견
- Title: Born-AI 세대 창업팀 발굴
- Subtitle: (없음)
```

2. **Claude API 호출**:
```python
from generator import SlideGenerator
generator = SlideGenerator()
lead = generator.generate_lead_only(context="01. 발견\nBorn-AI 세대 창업팀 발굴")
```

3. **생성된 리드**:
```
생성: "AI 네이티브 세대의 창업 아이디어를 발굴합니다"
길이: 28자 ✓
```

#### Step 2-2: 품질 평가

각 생성된 리드에 대해 lead_scorer.py로 평가:

```python
from lead_scorer import LeadScorer
scorer = LeadScorer(length_min=25, length_max=35)
score, details = scorer.score(lead)
```

```
=== 품질 평가 ===

[Slide 2] Lead: "AI 네이티브 세대의 창업 아이디어를 발굴합니다"
- 길이: 28자 ✓ (+2.0)
- 어미: "합니다" ✓ (+1.0)
- 키워드: "발굴" ✓ (+1.0)
- 줄바꿈: 없음 ✓
- 점수: 4.0 / 5.0

[Slide 3] Lead: "대학생 중심의 해커톤을 통해 팀 빌딩을 지원합니다"
- 길이: 30자 ✓ (+2.0)
- 어미: "합니다" ✓ (+1.0)
- 키워드: "지원" ✓ (+1.0)
- 줄바꿈: 없음 ✓
- 점수: 4.0 / 5.0

...

평균 점수: 3.8 / 5.0
```

#### Step 2-3: 전체 리드 목록 표시

```
=== 생성된 리드문 (12개) ===

[1] Slide 2: "AI 네이티브 세대의 창업 아이디어를 발굴합니다"
[2] Slide 3: "대학생 중심의 해커톤을 통해 팀 빌딩을 지원합니다"
[3] Slide 5: "선발된 팀에게 체계적인 액셀러레이팅을 제공합니다"
[4] Slide 6: "멘토링과 교육 프로그램을 통해 역량을 강화합니다"
...

승인하시겠습니까?
- Y: 그대로 삽입
- E: 개별 편집
- J: JSON 파일로 내보내기 (수동 편집)
```

#### Step 2-4: 사용자 승인

**옵션 1: 그대로 삽입 (Y)**
→ Phase 3으로 진행

**옵션 2: 개별 편집 (E)**
```
편집할 슬라이드 번호: 5

[현재] "선발된 팀에게 체계적인 액셀러레이팅을 제공합니다"
[수정] (새로운 리드문 입력):
> 선발 팀 대상 6개월 집중 육성 프로그램 운영

✓ 업데이트됨 (점수: 3.5 → 3.2, 길이: 28자)

다른 슬라이드도 편집하시겠습니까? (Y/N)
```

**옵션 3: JSON 내보내기 (J)**
```bash
생성된 리드문을 leads_draft.json에 저장했습니다.

텍스트 에디터로 편집한 후 다음 명령어로 삽입하세요:
python ppt_generator.py leads_draft.json output_with_leads.pptx tem.pptx
```

---

### Phase 3: 삽입 (Insert)

#### Step 3-1: slides_data.json 생성

```json
{
  "slides": [
    {
      "page": 1,
      "chapter": "",
      "title": "H-온드림 2026년 제안서",
      "subtitle": "임팩트 스타트업 발굴 육성",
      "lead": ""
    },
    {
      "page": 2,
      "chapter": "01. 발견",
      "title": "Born-AI 세대 창업팀 발굴",
      "subtitle": "",
      "lead": "AI 네이티브 세대의 창업 아이디어를 발굴합니다"
    },
    ...
  ],
  "font_settings": {
    "lead": {"name": "HDharmonyL", "size": 12, "color": "#000000"}
  }
}
```

#### Step 3-2: PPTX 생성

```bash
python ppt_generator.py slides_with_leads.json presentation_with_leads.pptx tem.pptx
```

실행 중:
- 템플릿 로드 중...
- 슬라이드 1/15 처리 중...
- 슬라이드 2/15 처리 중 (Lead 삽입)
- ...
- 저장 중...

#### Step 3-3: 결과 요약

```
=== 삽입 완료 ===

처리된 슬라이드: 15개
리드 삽입: 12개
평균 점수: 3.8 / 5.0

✓ 원본 보존: presentation.pptx
✓ 새 파일 생성: presentation_with_leads.pptx

[파일 경로]
/Users/.../presentation_with_leads.pptx
```

#### Step 3-4: 후속 작업 안내

```
리드문 삽입이 완료되었습니다!

다음 작업을 추천합니다:
1. "PPT 검사해줘: presentation_with_leads.pptx" - 품질 검사
2. PPTX 파일 열어서 최종 확인
```

---

## 리드문 제약 조건

| 항목 | 조건 | 비고 |
|------|------|------|
| 길이 | **25-35자** | 슬라이드 가독성 최적화 |
| 줄바꿈 | **금지** | 한 줄로 표현 |
| 어미 | "합니다", "입니다" | 격식체 |
| 금지어 | "펠로우" → "펠로" | 조직 용어 |
| 금지어 | "기업가 정신" → "임팩트 앙트프러너십" | 용어 통일 |

---

## 기술 스택

### 1. ultra_text_extractor.py

**역할**: PPTX에서 구조화된 텍스트 추출

**기술**:
- XML 파싱 (`ppt/slides/slideN.xml`)
- Claude API 구조 분류

**출력**:
```json
{
  "total_slides": 15,
  "slides": [
    {
      "page": 1,
      "chapter": "...",
      "title": "...",
      "subtitle": "...",
      "lead": "...",
      "contents": ["..."]
    }
  ]
}
```

### 2. generator.py (새 메서드)

**역할**: 단일 슬라이드 리드문 생성

**메서드**: `generate_lead_only(context, max_length=35)`

**프롬프트**:
```
다음 슬라이드의 핵심 메시지를 리드문으로 작성해주세요.

슬라이드 내용:
{context}

리드문 요구사항:
- 35글자 이내
- 한 줄로 작성 (줄바꿈 금지)
- "~합니다" 또는 "~입니다" 어미 사용
- 슬라이드의 핵심 메시지를 담은 간결한 문장
```

**재시도 로직**:
- 길이 초과 시 max_length-5로 재시도
- 최대 3회 재시도

### 3. lead_scorer.py

**역할**: 리드문 품질 평가

**채점 기준**:
- 길이 OK (25-35자): +2.0
- 어미 OK ("합니다", "입니다"): +1.0
- 키워드 존재: +1.0 (각각)
- 줄바꿈 있음: -0.5
- 금지어 사용: -1.0
- 쉼표 사용: -0.5

**출력**:
```python
{
  "score": 4.0,
  "details": {
    "length_ok": True,
    "ending_ok": True,
    "keywords": ["발굴", "지원"],
    "has_newline": False,
    "forbidden_words": []
  }
}
```

### 4. ppt_generator.py

**역할**: 템플릿 기반 PPTX 생성

**메커니즘**:
- `find_and_replace_text(slide, "Lead", new_lead, font_config)`
- Placeholder 텍스트 매칭 (대소문자 무시)
- 폰트 설정 적용 (HDharmonyL, 12pt)

---

## 활성화 키워드

사용자가 다음과 같은 요청을 하면 이 스킬이 활성화됩니다:

- "리드문 넣어줘"
- "슬라이드 설명 추가"
- "리드 생성"
- "Lead text 삽입"
- "리드문 자동 생성"

---

## 에러 처리

### ANTHROPIC_API_KEY 미설정

```
⚠️ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.

다음 명령어로 설정해주세요:

export ANTHROPIC_API_KEY="sk-ant-..."
```

### 템플릿에 Lead placeholder 없음

```
⚠️ 템플릿에 "Lead" placeholder를 찾을 수 없습니다.

해결 방법:
1. "템플릿 분석: tem.pptx" 실행하여 구조 확인
2. 템플릿에 "Lead" 텍스트 추가
3. 다시 시도
```

### 생성된 리드가 35자 초과 (3회 재시도 실패)

```
⚠️ 슬라이드 5: 리드 생성 실패 (길이 초과)

수동 입력:
[현재 컨텍스트]
- Title: "멘토링 및 교육 프로그램 운영 계획"
- Subtitle: "전문가 멘토링, 워크샵, 온라인 강의 등 다양한 학습 기회 제공"

[리드문 입력] (25-35자):
> 전문 멘토와 교육으로 역량을 강화합니다

✓ 입력됨 (28자)
```

### 파일 손상

```
⚠️ PPTX 파일을 읽을 수 없습니다: presentation.pptx

원인:
- 파일 손상
- 암호화된 파일
- 지원하지 않는 형식

해결:
- PowerPoint에서 파일 열어 "다른 이름으로 저장"
- 다시 시도
```

---

## 고급 사용법

### RAG 모드 (향후 지원)

RAG 인덱스를 활용한 컨텍스트 기반 생성:

```python
from lead_rag_pipeline import LeadRAGPipeline
rag_pipeline = LeadRAGPipeline("rag_indexes/lead_index.json")
lead = rag_pipeline.generate_with_retrieval(context, top_k=5)
```

**효과**:
- 유사 슬라이드 검색
- 도메인 특화 표현 활용
- 일관된 스타일 유지

### 배치 처리

여러 PPTX 파일에 리드문 일괄 삽입:

```bash
for file in *.pptx; do
  # 리드문 삽입 스킬 실행
  echo "리드문 넣어줘: $file"
done
```

### 커스텀 폰트

리드문 폰트 커스터마이징:

```json
{
  "font_settings": {
    "lead": {
      "name": "NanumSquare",
      "size": 14,
      "bold": false,
      "color": "#333333"
    }
  }
}
```

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| [ultra_text_extractor.py](../../ultra_text_extractor.py) | PPTX 구조 추출 |
| [generator.py](../../generator.py) | 리드문 생성 (generate_lead_only) |
| [lead_scorer.py](../../lead_scorer.py) | 품질 평가 |
| [ppt_generator.py](../../ppt_generator.py) | PPTX 생성 |
| [learning_data/extracted_leads.json](../../learning_data/extracted_leads.json) | 참조 코퍼스 |
| rag_indexes/lead_index.json | RAG 인덱스 (선택) |

---

## 성능

| 항목 | 시간 |
|------|------|
| 구조 추출 (15 slides) | ~15초 |
| 리드문 생성 (12 leads) | ~30초 |
| PPTX 삽입 | ~5초 |
| **총 소요 시간** | **~50초** |

---

## 예시

### 예시 1: 제안서 리드문 추가

**입력:**
```
"리드문 넣어줘: H온드림_제안서_초안.pptx"
```

**프로세스:**
```
1. 구조 추출: 15개 슬라이드, 12개 리드 필요
2. 생성: 평균 점수 3.9
3. 삽입: H온드림_제안서_초안_with_leads.pptx
```

**결과:**
```
[Slide 2] Lead: "AI 네이티브 세대의 창업 아이디어를 발굴합니다" (28자, 4.0점)
[Slide 3] Lead: "대학생 중심 해커톤으로 팀 빌딩을 지원합니다" (26자, 4.0점)
...
```

### 예시 2: 결과보고서 리드문 추가

**입력:**
```
"리드문 넣어줘: 2025_결과보고서.pptx"
출력: 2025_결과보고서_완성.pptx
```

**프로세스:**
```
1. 구조 추출: 20개 슬라이드, 18개 리드 필요
2. 생성: 평균 점수 3.7
3. 개별 편집: 슬라이드 10, 15 수정
4. 삽입: 2025_결과보고서_완성.pptx
```

---

## 품질 향상 팁

### 1. 컨텍스트 풍부화

슬라이드에 Subtitle이 있으면 생성 품질 향상:

```
[좋음]
- Title: "멘토링 프로그램"
- Subtitle: "전문가 1:1 멘토링 및 그룹 워크샵"
→ "전문가 멘토링과 워크샵으로 역량을 강화합니다" (정확)

[부족]
- Title: "멘토링 프로그램"
- Subtitle: (없음)
→ "멘토링 프로그램을 운영합니다" (일반적)
```

### 2. 참조 데이터 활용

과거 제안서의 리드문 스타일 참고:

```python
# learning_data/extracted_leads.json 활용
# Few-shot 예시로 제공하여 스타일 일관성 확보
```

### 3. 반복 개선

생성 → 검토 → 수정 → 재생성 사이클:

```
1차 생성: "혁신적인 프로그램을 운영합니다" (일반적)
피드백: "구체적인 방법 추가"
2차 생성: "전문가 멘토링과 워크샵으로 역량을 강화합니다" (구체적)
```

---

## lead-writer 스킬과의 차이

| 항목 | lead-writer (기존) | lead-inserter (신규) |
|------|-------------------|---------------------|
| **목적** | 수동 일괄 작성 | 자동 생성 및 삽입 |
| **입력** | 슬롯 기반 메타 정보 | 기존 PPTX 파일 |
| **워크플로우** | 인터랙티브 (4단계) | 자동화 (3단계) |
| **리드 길이** | 100-120자 (2-3문장) | 25-35자 (한 문장) |
| **사용 시점** | 기획 단계 (아이디에이션) | 완성 단계 (마무리) |
| **출력** | 텍스트 목록 (복사/붙여넣기) | PPTX 파일 |

**권장 사용법**:
- **기획 단계**: lead-writer로 풍부한 리드문 작성
- **완성 단계**: lead-inserter로 간결한 리드문 자동 삽입
