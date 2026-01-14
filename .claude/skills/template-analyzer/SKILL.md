---
name: template-analyzer
description: PPT 템플릿 분석 스킬. 템플릿 파일의 구조, 폰트, 색상, 위치 정보를 추출합니다. "템플릿 분석", "템플릿 구조", "스타일 정보" 등의 요청에 응답합니다.
allowed-tools: Bash(python3:*), Read, Write, AskUserQuestion
---

# 템플릿 분석 스킬

PPTX 템플릿 파일의 구조, 폰트, 색상, 위치 정보를 추출하는 스킬입니다.

## 워크플로우

### Phase 1: 입력 수집

사용자에게 다음 정보를 요청합니다:

```
템플릿 분석을 시작합니다!

다음 정보를 알려주세요:

1. **템플릿 파일 경로**: (기본: tem.pptx)
   예: tem.pptx, custom_template.pptx

2. **출력 JSON 파일**: (기본: template_style.json)
```

### Phase 2: 파일 검증

```
파일 검증:
✓ tem.pptx 발견 (35 KB)

슬라이드 수: 1개
레이아웃: 커스텀
```

### Phase 3: 분석 실행

```bash
python template_extractor.py tem.pptx
```

실행 중:
- XML 파싱 중...
- Placeholder 탐지 중...
- 폰트 정보 추출 중...
- 위치 정보 계산 중...

### Phase 4: 결과 표시

#### 4-1: 슬라이드 크기

```
=== 슬라이드 크기 ===

EMU 단위: 9144000 × 6858000
포인트(pt): 720 × 540
인치(inch): 10 × 7.5
비율: 4:3 (표준)

* EMU: English Metric Units (1pt = 12700 EMU)
```

#### 4-2: Placeholder 정보

```
=== Placeholder 정보 ===

[1] Chapter
- 원본 텍스트: "Chapter"
- 위치 (x, y): (50pt, 80pt)
- 크기 (w, h): (200pt, 40pt)
- 폰트: HDharmonyB, 16pt, Bold
- 색상: #000000 (검정)
- 정렬: Left

[2] Title
- 원본 텍스트: "Title"
- 위치 (x, y): (50pt, 140pt)
- 크기 (w, h): (620pt, 60pt)
- 폰트: HDharmonyB, 16pt, Bold
- 색상: #000000 (검정)
- 정렬: Left

[3] Subtitle
- 원본 텍스트: "Subtitle"
- 위치 (x, y): (50pt, 220pt)
- 크기 (w, h): (620pt, 40pt)
- 폰트: HDharmonyM, 16pt, Regular
- 색상: #000000 (검정)
- 정렬: Left

[4] Lead
- 원본 텍스트: "Lead"
- 위치 (x, y): (50pt, 450pt)
- 크기 (w, h): (620pt, 50pt)
- 폰트: HDharmonyL, 12pt, Regular
- 색상: #000000 (검정)
- 정렬: Left
```

#### 4-3: 폰트 정보

```
=== 폰트 정보 ===

사용된 폰트 패밀리:
1. HDharmonyB (Bold) - Chapter, Title
2. HDharmonyM (Medium) - Subtitle
3. HDharmonyL (Light) - Lead

East Asian 폰트 설정:
✓ 모든 placeholder에 a:ea 설정됨
✓ 한글 텍스트 렌더링 최적화
```

#### 4-4: 색상 팔레트

```
=== 색상 팔레트 ===

텍스트 색상:
- #000000 (검정) - 모든 placeholder

배경 색상:
- #FFFFFF (흰색)

강조 색상:
- (감지되지 않음)
```

### Phase 5: JSON 저장

```
✓ template_style.json 저장 완료

파일 경로: /Users/.../template_style.json

[JSON 구조]
{
  "slide_size": {...},
  "placeholders": [...],
  "fonts": [...],
  "colors": [...]
}
```

### Phase 6: 활용 방법 안내

```
=== 활용 방법 ===

1. **커스텀 템플릿 제작**:
   - Placeholder 위치를 참고하여 새 템플릿 디자인
   - 폰트 설정 유지 (HDharmony 패밀리)

2. **Font 설정 커스터마이징**:
   - slides_data.json의 font_settings 섹션 수정
   - 추출된 폰트 정보 활용

3. **위치 계산**:
   - EMU 단위 → pt 변환 (÷ 12700)
   - 새 shape 배치 시 참고

4. **프로그래밍 활용**:
   - JSON 파일을 파싱하여 자동화 스크립트 작성
   - 템플릿 검증 로직에 활용
```

---

## 출력 JSON 구조

### template_style.json

```json
{
  "slide_size": {
    "width_emu": 9144000,
    "height_emu": 6858000,
    "width_pt": 720,
    "height_pt": 540,
    "width_inch": 10,
    "height_inch": 7.5,
    "aspect_ratio": "4:3"
  },
  "placeholders": [
    {
      "name": "Chapter",
      "original_text": "Chapter",
      "position": {
        "x_emu": 635000,
        "y_emu": 1016000,
        "x_pt": 50,
        "y_pt": 80
      },
      "size": {
        "width_emu": 2540000,
        "height_emu": 508000,
        "width_pt": 200,
        "height_pt": 40
      },
      "font": {
        "name": "HDharmonyB",
        "size": 16,
        "bold": true,
        "italic": false,
        "color": "#000000"
      },
      "alignment": "left"
    },
    ...
  ],
  "fonts": [
    {
      "family": "HDharmonyB",
      "weight": "Bold",
      "used_in": ["Chapter", "Title"]
    },
    {
      "family": "HDharmonyM",
      "weight": "Medium",
      "used_in": ["Subtitle"]
    },
    {
      "family": "HDharmonyL",
      "weight": "Light",
      "used_in": ["Lead"]
    }
  ],
  "colors": {
    "text": ["#000000"],
    "background": "#FFFFFF",
    "accent": []
  }
}
```

---

## Placeholder 탐지 로직

template_extractor.py는 다음 방법으로 placeholder를 탐지합니다:

### 1. 텍스트 내용 매칭

```python
# 대소문자 무시 매칭
if "chapter" in shape.text.lower():
    placeholder_type = "Chapter"
elif "title" in shape.text.lower():
    placeholder_type = "Title"
elif "subtitle" in shape.text.lower():
    placeholder_type = "Subtitle"
elif "lead" in shape.text.lower():
    placeholder_type = "Lead"
```

### 2. 위치 기반 추론

```python
# Y 좌표로 순서 추정
if y_pt < 100:
    likely_type = "Chapter"
elif y_pt < 200:
    likely_type = "Title"
elif y_pt < 300:
    likely_type = "Subtitle"
else:
    likely_type = "Lead"
```

### 3. 폰트 크기 힌트

```python
# 폰트 크기로 중요도 추정
if font_size >= 16:
    priority = "high"  # Chapter, Title
elif font_size >= 12:
    priority = "medium"  # Subtitle, Lead
```

---

## EMU ↔ Point 변환

### 변환 공식

```
1 point (pt) = 12700 EMU
1 inch = 914400 EMU = 72 pt
```

### 예시

```python
# EMU → pt
x_pt = x_emu / 12700
# 635000 EMU → 50 pt

# pt → EMU
x_emu = x_pt * 12700
# 50 pt → 635000 EMU
```

---

## 활성화 키워드

사용자가 다음과 같은 요청을 하면 이 스킬이 활성화됩니다:

- "템플릿 분석"
- "템플릿 구조 확인"
- "스타일 정보"
- "템플릿 추출"
- "플레이스홀더 위치"

---

## 에러 처리

### 파일 없음

```
⚠️ 템플릿 파일을 찾을 수 없습니다: tem.pptx

파일 경로를 확인해주세요.
```

### Placeholder 미발견

```
⚠️ "Lead" placeholder를 찾을 수 없습니다.

발견된 placeholder:
- Chapter ✓
- Title ✓
- Subtitle ✓
- Lead ✗

확인 사항:
1. 템플릿에 "Lead" 텍스트가 있는지 확인
2. 텍스트 대소문자 확인 (lead, LEAD도 매칭됨)
3. 텍스트 형태 확인 (TextBox, Shape 등)
```

### XML 파싱 오류

```
⚠️ 템플릿 파일을 파싱할 수 없습니다.

원인:
- 손상된 PPTX 파일
- 암호화된 파일
- 지원하지 않는 형식

해결:
- PowerPoint에서 파일 열어 "다른 이름으로 저장"
- 다시 시도
```

---

## 고급 사용법

### 커스텀 Placeholder 추가

template_style.json을 참고하여 새 placeholder 추가:

```python
# 기존 Lead 위치 아래에 "Content" placeholder 추가
content_y = lead_y + lead_height + 20  # 20pt 간격
content_position = {
    "x_emu": 635000,
    "y_emu": content_y * 12700,
    "x_pt": 50,
    "y_pt": content_y
}
```

### 템플릿 검증

분석 결과를 기반으로 템플릿 유효성 검사:

```python
import json

with open("template_style.json") as f:
    style = json.load(f)

required_placeholders = ["Chapter", "Title", "Subtitle", "Lead"]
found = [p["name"] for p in style["placeholders"]]

missing = set(required_placeholders) - set(found)
if missing:
    print(f"⚠️ 누락된 placeholder: {missing}")
else:
    print("✓ 모든 placeholder 발견됨")
```

### 폰트 일관성 체크

```python
fonts_used = {p["font"]["name"] for p in style["placeholders"]}
expected_fonts = {"HDharmonyB", "HDharmonyM", "HDharmonyL"}

if fonts_used == expected_fonts:
    print("✓ 폰트 설정 일관됨")
else:
    print(f"⚠️ 예상치 못한 폰트: {fonts_used - expected_fonts}")
```

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| [template_extractor.py](../../template_extractor.py) | 템플릿 분석 스크립트 |
| template_style.json | 추출된 스타일 정보 (출력) |
| tem.pptx | 기본 템플릿 파일 |

---

## 예시

### 예시 1: 기본 템플릿 분석

**입력:**
```
"템플릿 분석: tem.pptx"
```

**출력:**
```
=== 슬라이드 크기 ===
720 × 540 pt (4:3)

=== Placeholder 정보 ===
[1] Chapter: (50, 80) - HDharmonyB 16pt
[2] Title: (50, 140) - HDharmonyB 16pt
[3] Subtitle: (50, 220) - HDharmonyM 16pt
[4] Lead: (50, 450) - HDharmonyL 12pt

✓ template_style.json 저장 완료
```

### 예시 2: 커스텀 템플릿 분석

**입력:**
```
"템플릿 분석: custom_template.pptx"
출력: custom_style.json
```

**출력:**
```
=== 슬라이드 크기 ===
960 × 540 pt (16:9)

=== Placeholder 정보 ===
[1] Chapter: (100, 60) - NanumSquare 18pt
[2] Title: (100, 120) - NanumSquare 24pt
[3] Subtitle: (100, 200) - NanumSquare 14pt
[4] Lead: (100, 400) - NanumSquare 12pt

⚠️ 비표준 폰트 사용: NanumSquare
(권장: HDharmony 패밀리)

✓ custom_style.json 저장 완료
```

---

## 템플릿 디자인 가이드

### 권장 레이아웃

```
┌─────────────────────────────────┐
│  Chapter (50, 80)               │  ← 5자 이내
├─────────────────────────────────┤
│  Title (50, 140)                │  ← 10-20자
│  큰 폰트, Bold                   │
├─────────────────────────────────┤
│  Subtitle (50, 220)             │  ← 15-30자
│  중간 폰트, Medium               │
├─────────────────────────────────┤
│                                 │
│  [콘텐츠 영역]                   │
│                                 │
├─────────────────────────────────┤
│  Lead (50, 450)                 │  ← 25-35자
│  작은 폰트, Light                │
└─────────────────────────────────┘
```

### 폰트 크기 권장

| 요소 | 크기 | 무게 | 용도 |
|------|------|------|------|
| Chapter | 16pt | Bold | 섹션 키워드 |
| Title | 16-24pt | Bold | 슬라이드 제목 |
| Subtitle | 14-16pt | Medium | 부제목 |
| Lead | 12pt | Light | 리드문 |

### 색상 가이드

```
텍스트:
- Primary: #000000 (검정)
- Secondary: #555555 (회색)
- Accent: #0066CC (파랑)

배경:
- White: #FFFFFF
- Light gray: #F5F5F5
```

---

## 디버깅

### Placeholder 발견 안 됨

**원인 1**: 텍스트 매칭 실패

```
템플릿에 다음 텍스트가 정확히 있는지 확인:
- "Chapter" (대소문자 무관)
- "Title"
- "Subtitle"
- "Lead"
```

**원인 2**: Shape 타입 미지원

```
지원 타입:
✓ TextBox
✓ Shape with text
✗ Table
✗ SmartArt
```

### 폰트 정보 누락

```
⚠️ 폰트 정보를 추출할 수 없습니다.

확인 사항:
1. Shape에 텍스트가 있는지
2. 폰트가 시스템에 설치되어 있는지
3. XML에 <a:rPr> 요소가 있는지
```

### 위치 정보 부정확

```
⚠️ 위치 계산이 부정확할 수 있습니다.

원인:
- 그룹화된 Shape
- 회전된 Shape
- Transform이 적용된 Shape

해결:
- Shape를 그룹 해제
- 회전 제거
- 다시 분석
```

---

## 통합 워크플로우

템플릿 분석 → PPT 생성 → 검증:

```bash
# 1. 템플릿 분석
"템플릿 분석: tem.pptx"

# 2. 스타일 확인
cat template_style.json

# 3. PPT 생성 (분석 결과 기반)
"PPT 만들어줘: 제안서 내용..."

# 4. 검증
"PPT 검사해줘: output.pptx"
```

---

## FAQ

**Q: EMU가 뭔가요?**
A: English Metric Units. PowerPoint XML 내부에서 사용하는 길이 단위입니다. 1pt = 12700 EMU.

**Q: 여러 슬라이드가 있으면 어떻게 되나요?**
A: 기본적으로 첫 번째 슬라이드만 분석합니다. 다른 슬라이드는 --slide-index 옵션 사용.

**Q: 커스텀 Placeholder 이름을 사용할 수 있나요?**
A: 네, template_extractor.py에 매칭 규칙을 추가하면 됩니다.

**Q: 분석 결과를 자동화에 활용할 수 있나요?**
A: 네, template_style.json을 파싱하여 템플릿 검증, 자동 생성 등에 활용 가능합니다.
