---
name: ppt-checker
description: PPT 품질 검사 스킬. 맞춤법, 띄어쓰기, 용어 통일성을 3단계로 검사합니다. "PPT 검사", "맞춤법 체크", "용어 확인" 등의 요청에 응답합니다.
allowed-tools: Bash(python3:*), Read, Write, AskUserQuestion
---

# PPT 품질 검사 스킬

PPTX 파일의 맞춤법, 띄어쓰기, 용어 통일성을 3단계 파이프라인으로 검사하는 스킬입니다.

## 워크플로우

### Phase 1: 입력 수집

사용자에게 다음 정보를 요청합니다:

```
PPT 품질 검사를 시작합니다!

다음 정보를 알려주세요:

1. **PPTX 파일 경로**: (검사할 파일)
   예: output.pptx, presentation.pptx

2. **출력 형식**: (기본: Excel)
   - Excel (.xlsx) - 권장
   - JSON (.json) - 프로그래밍용

3. **RAG 인덱스** (선택사항):
   - 없음 (기본)
   - rag_indexes/qa_index.json (컨텍스트 기반 검사)
```

### Phase 2: 파일 검증

```
파일 존재 여부 확인:
✓ /Users/.../output.pptx 발견

ANTHROPIC_API_KEY 환경변수 확인:
✓ 설정됨
```

### Phase 3: 검사 실행

```bash
python integrated_pptx_checker.py input.pptx --output report.xlsx
```

실행 중 표시:
- [Stage 1/3] Ultra Think 텍스트 추출 중...
- [Stage 2/3] ML + 규칙 기반 검사 중...
- [Stage 3/3] Claude 컨텍스트 검토 중...

### Phase 4: 결과 요약

검사 완료 후 요약을 표시합니다:

```
=== 검사 완료 ===

총 텍스트: 85개
총 이슈: 23개

[이슈 분류]
- 맞춤법: 8개
- 띄어쓰기: 5개
- 용어통일: 7개
- 문맥기반: 3개

[검출 소스]
- Few-shot 모델: 12개
- 규칙 기반: 8개
- Claude 검토: 3개

[False Positive 제거]
- Claude가 제거한 오탐: 5개
```

### Phase 5: 상위 이슈 표시

상위 10개 이슈를 우선순위별로 표시합니다:

```
=== 상위 10개 이슈 ===

[1] Slide 3 - Lead
원본: "기업가 정신을 바탕으로 성장을 지원합니다"
제안: "임팩트 앙트프러너십을 바탕으로 성장을 지원합니다"
이유: 용어통일 - "기업가 정신" → "임팩트 앙트프러너십"
신뢰도: 높음 (rule_based)

[2] Slide 5 - Title
원본: "펠로우 선발 과정"
제안: "펠로 선발 과정"
이유: 금지어 - "펠로우" → "펠로"
신뢰도: 높음 (rule_based)

[3] Slide 7 - Lead
원본: "혁신적인 솔루션을제공합니다"
제안: "혁신적인 솔루션을 제공합니다"
이유: 띄어쓰기
신뢰도: 중간 (finetuned_model)

...
```

### Phase 6: 파일 안내

```
✓ Excel 리포트 생성 완료: /Users/.../report.xlsx

[Excel 파일 구조]
- Sheet 1: 이슈 목록 (변경 부분 빨간색)
- Sheet 2: 전체 텍스트 ("문제 없음" 포함)

[활용 방법]
1. Excel 파일 열기
2. Sheet 1에서 이슈 검토
3. 원본 PPTX에서 수정 적용
```

---

## 3단계 검사 파이프라인

### Stage 1: Ultra Think (텍스트 추출)

**기술**: XML 파싱 + Claude API 구조 분류

**특징**:
- 빠른 속도 (10x faster than Vision API)
- 자동 semantic 분류 (Chapter/Title/Subtitle/Lead/Contents)
- 구조화된 데이터 반환

**처리 시간**: 7슬라이드 기준 ~15초

### Stage 2: ML + 규칙 기반 검사

**기술**: Few-shot 예시 + 규칙 엔진

**검사 항목**:
- 맞춤법 오류
- 띄어쓰기 오류
- 용어 통일성

**Knowledge Distillation**:
- fewshot_examples.json 활용 (31 positive + 12 negative)
- Fine-tuned 모델 대비 빠르고 정확

**규칙 엔진** (pptx_checker.py):
- 금지어 검사
- 특수 규칙 적용

### Stage 3: Claude 컨텍스트 검토

**기술**: Claude API 문맥 분석

**역할**:
- False Positive 제거
- 문맥 기반 제안
- 추가 이슈 발견 (additional_issues)

**예시**:
- "스타트업" → 문맥에 따라 "임팩트 스타트업" 제안
- "빠르게" vs "빨리" → 문장 흐름에 따라 판단

---

## 특별 규칙

이 스킬은 다음 조직 특화 규칙을 적용합니다:

| 원본 | 수정 | 이유 |
|------|------|------|
| 펠로우 | 펠로 | 금지어 (조직 내부 용어) |
| 기업가 정신 | 임팩트 앙트프러너십 | 용어 통일 |
| 스타트업 | (문맥 판단) 임팩트 스타트업 | 컨텍스트 기반 |

---

## 출력 형식

### Excel 리포트 (.xlsx)

**Sheet 1: 이슈 목록**

| Slide | Field | Original | Suggested | Type | Source | Confidence | Reason |
|-------|-------|----------|-----------|------|--------|------------|--------|
| 3 | Lead | 기업가 정신... | 임팩트 앙트... | 용어통일 | rule_based | 높음 | "기업가 정신" → "임팩트 앙트프러너십" |

**Sheet 2: 전체 텍스트**

| Slide | Field | Text | Issues |
|-------|-------|------|--------|
| 1 | Title | H-온드림 제안서 | 문제 없음 |
| 2 | Lead | MYSC와 함께... | 문제 없음 |
| 3 | Lead | 기업가 정신... | [이슈 발견] |

**서식**:
- 변경 부분: 빨간색 텍스트
- 이슈 없음: 녹색 배경

### JSON 리포트 (.json)

```json
{
  "total_texts": 85,
  "total_issues": 23,
  "issues": [
    {
      "slide": 3,
      "field": "Lead",
      "original": "기업가 정신을 바탕으로...",
      "suggested": "임팩트 앙트프러너십을 바탕으로...",
      "type": "용어통일",
      "source": "rule_based",
      "confidence": "높음",
      "reason": "\"기업가 정신\" → \"임팩트 앙트프러너십\""
    }
  ],
  "false_positives_removed": 5,
  "additional_issues": [...]
}
```

---

## 활성화 키워드

사용자가 다음과 같은 요청을 하면 이 스킬이 활성화됩니다:

- "PPT 검사"
- "맞춤법 체크"
- "품질 검사"
- "오타 확인"
- "용어 통일"
- "리뷰해줘"

---

## 에러 처리

### ANTHROPIC_API_KEY 미설정

```
⚠️ ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.

다음 명령어로 설정해주세요:

export ANTHROPIC_API_KEY="sk-ant-..."
```

### 파일 없음

```
⚠️ PPTX 파일을 찾을 수 없습니다: input.pptx

파일 경로를 확인해주세요.
```

### Stage 실패

```
⚠️ Stage 1 (텍스트 추출) 실패

원인: XML 파싱 오류
해결: PPTX 파일 손상 여부 확인

Stage 2로 진행할까요? (Y/N)
```

---

## 고급 사용법

### RAG 모드

컨텍스트 기반 검사를 위해 RAG 인덱스 사용:

```bash
python integrated_pptx_checker.py input.pptx \
  --output report.xlsx \
  --rag-index rag_indexes/qa_index.json
```

**효과**:
- 과거 제안서의 용어 패턴 참조
- 도메인 특화 맞춤법 검사
- 문맥 정확도 향상

### 배치 처리

여러 파일 동시 검사:

```bash
for file in *.pptx; do
  python integrated_pptx_checker.py "$file" --output "${file%.pptx}_report.xlsx"
done
```

### 자동 수정 (향후 기능)

```bash
# 현재는 수동 수정 필요
# 향후: --auto-fix 옵션으로 자동 적용 예정
python integrated_pptx_checker.py input.pptx --auto-fix --output corrected.pptx
```

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| [integrated_pptx_checker.py](../../integrated_pptx_checker.py) | 메인 검사 파이프라인 |
| [ultra_text_extractor.py](../../ultra_text_extractor.py) | Stage 1: 텍스트 추출 |
| [pptx_checker.py](../../pptx_checker.py) | Stage 2: 규칙 엔진 |
| [fewshot_examples.json](../../fewshot_examples.json) | Knowledge Distillation 예시 |
| rag_indexes/qa_index.json | RAG 컨텍스트 인덱스 |

---

## 성능 비교

| 모드 | 속도 (7 slides) | 정확도 |
|------|-----------------|--------|
| **Ultra Think (기본)** | ~15초 | ★★★★★ |
| Vision API (대체) | ~3분 | ★★★★☆ |
| Few-shot (Knowledge Distillation) | ~10초 | ★★★★★ |
| Fine-tuned 모델 (레거시) | ~20초 | ★★★★☆ |

**권장**: Ultra Think + Few-shot (기본 설정)

---

## 예시

### 예시 1: 제안서 검사

**입력:**
```
"PPT 검사해줘: H온드림_제안서_2026.pptx"
```

**출력:**
```
=== 검사 완료 ===

총 텍스트: 120개
총 이슈: 15개

[주요 이슈]
1. "펠로우" → "펠로" (5회)
2. "기업가 정신" → "임팩트 앙트프러너십" (3회)
3. 띄어쓰기 오류 (7회)

✓ Excel 리포트: H온드림_제안서_2026_report.xlsx
```

### 예시 2: 결과보고서 검사

**입력:**
```
"PPT 검사해줘: 결과보고서_2025.pptx"
출력 형식: JSON
```

**출력:**
```
=== 검사 완료 ===

총 텍스트: 95개
총 이슈: 8개

[이슈 분류]
- 맞춤법: 3개
- 띄어쓰기: 2개
- 용어통일: 2개
- 문맥기반: 1개

✓ JSON 리포트: 결과보고서_2025_report.json
```

---

## False Positive 예시

Claude Stage 3가 제거한 오탐 사례:

| 원본 | 제안 (Stage 2) | Claude 판단 | 이유 |
|------|----------------|-------------|------|
| 빠르게 성장 | 빨리 성장 | ✗ 유지 | "빠르게"가 문맥상 적절 |
| 소셜벤처 | 소셜 벤처 | ✗ 유지 | 조직 내 표준 표기 |
| AI 기반 | A.I. 기반 | ✗ 유지 | "AI"가 일반적 |

---

## 추가 이슈 (additional_issues)

Claude가 발견한 스타일/문맥 제안:

```
[추가 제안]
- Slide 5: "할 수 있습니다" → "하겠습니다" (더 강한 의지 표현)
- Slide 8: 문장이 너무 길어 가독성 저하 (40자 → 25-35자 권장)
- Slide 12: 중복 표현 ("지원을 지원") 확인 필요
```

**용도**: 품질 향상을 위한 참고 사항 (선택적 적용)
