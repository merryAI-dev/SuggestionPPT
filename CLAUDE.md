# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PPT auto-generation pipeline that converts natural language input into PowerPoint presentations using Claude API. The workflow is:
`Natural language input → Claude API → slides_data.json → output.pptx`

Additionally, the project includes PPTX quality checking tools that use ML models and Claude API for spell-checking and term consistency validation.

## Commands

### Main Pipeline
```bash
# Run the full pipeline (main entry point)
python pipeline.py '자연어 요청' [output.pptx]
# Example: python pipeline.py 'H-온드림 2026년 제안서 만들어줘'

# Generate PPTX from existing JSON data
python ppt_generator.py slides_data.json output.pptx [template.pptx]

# Analyze template structure
python ppt_generator.py --analyze tem.pptx
```

### Learning System
```bash
# Extract content from PPTX/PDF files in inputdata/
python extractor.py

# Build learning data patterns from extracted content
python build_learning_data.py
# Output: learning_data/patterns.json

# Extract template style info to JSON
python template_extractor.py tem.pptx
# Output: template_style.json
```

### Quality Checking
```bash
# Run integrated PPTX checker (Knowledge Distillation mode - recommended)
python integrated_pptx_checker.py input.pptx [--output report.json]
# Default: Uses Few-shot examples instead of fine-tuned model (faster & more accurate)

# Run Ultra Think text extraction only (for testing/debugging)
python ultra_text_extractor.py input.pptx [output.json]

# Convert PPTX to images
python pptx_to_images.py input.pptx [output_dir]

# Extract text from a single image using Claude Vision
python vision_text_extractor.py image.png

# Build Few-shot examples from fine-tuning dataset (Knowledge Distillation)
python build_fewshot_examples.py
# Output: fewshot_examples.json (31 positive + 12 negative examples)

# Test fine-tuned spelling model (legacy, now replaced by Few-shot)
python test_spelling_model.py
```

### Dataset Building
```bash
# Build spelling correction dataset from existing presentations
python build_spelling_dataset.py
# Output: learning_data/spelling_dataset.json (3,111 samples used for Few-shot extraction)

# Extract lead text examples for training
python extract_leads.py
# Output: learning_data/extracted_leads.json

# Build local RAG indexes (QA + lead)
python build_rag_index.py --kind all
# Output: rag_indexes/qa_index.json, rag_indexes/lead_index.json

# Build unsupervised auto-mask vocab (industry-specific terms)
python build_auto_mask_vocab.py --target-dir inputdata --target-pattern "H-온드림" \
  --background-dir inputdata --output learning_data/auto_mask_vocab.environment.json
```

### RAG-enabled flows
```bash
# Use RAG examples in Stage 3 (default if index exists)
python integrated_pptx_checker.py input.pptx --rag-index rag_indexes/qa_index.json

# Lead RL with RAG generator
python lead_rl_supervisor.py --meta-dataset learning_data/mvp_meta_dataset.environment.jsonl \
  --generator rag --rag-index rag_indexes/lead_index.json

# Build masked MVP dataset using auto-mask vocab
python build_mvp_lead_datasets.py --input-dir inputdata --industry environment \
  --mask-industry --auto-mask-vocab learning_data/auto_mask_vocab.environment.json
```

## Claude Code Skills

이 프로젝트는 5개의 자동화 워크플로우 스킬을 제공합니다:

### 콘텐츠 생성
- **lead-writer**: 수동 리드문 일괄 작성 (기존)
  - 인터랙티브 워크플로우, 슬롯 기반 템플릿
  - 샘플 생성 및 스타일 튜닝
  - [.claude/skills/lead-writer/SKILL.md](.claude/skills/lead-writer/SKILL.md)

- **ppt-generator**: 자연어로 PPT 자동 생성 (신규)
  - 사용: "PPT 만들어줘: [설명]"
  - 래퍼: [pipeline.py](pipeline.py)

- **lead-inserter**: 기존 PPT에 리드문 생성 및 삽입 (신규)
  - 사용: "리드문 넣어줘: input.pptx"
  - 조합: [ultra_text_extractor.py](ultra_text_extractor.py) + [generator.py](generator.py) + [ppt_generator.py](ppt_generator.py)

### 품질 관리
- **ppt-checker**: 3단계 품질 검사 (신규)
  - 사용: "PPT 검사해줘: input.pptx"
  - 래퍼: [integrated_pptx_checker.py](integrated_pptx_checker.py)
  - 검사 항목: 맞춤법, 띄어쓰기, 용어통일, 문맥 검토

### 템플릿 관리
- **template-analyzer**: 템플릿 구조 및 스타일 추출 (신규)
  - 사용: "템플릿 분석: tem.pptx"
  - 래퍼: [template_extractor.py](template_extractor.py)

자세한 워크플로우는 각 스킬의 SKILL.md 파일 참조.

## Architecture

### 1. Content Generation Pipeline
**Entry point:** [pipeline.py](pipeline.py) orchestrates the full generation flow.

**Flow:**
1. **[generator.py](generator.py)** (`SlideGenerator` class):
   - Takes natural language input (Korean text describing presentation content)
   - Loads reference patterns from `learning_data/patterns.json`
   - Calls Claude API (`claude-sonnet-4-20250514`) with structured prompts
   - Returns structured `slides_data.json` format with content fitting character constraints

2. **[ppt_generator.py](ppt_generator.py)**:
   - Loads JSON data and template PPTX
   - Duplicates first template slide for each content slide
   - Finds and replaces placeholder text by matching content ("Chapter", "Title", "Subtitle", "Lead")
   - Applies font settings (supports HDharmony family fonts)
   - Saves final PPTX

**Key constraint:** Content must preserve user's original phrasing while fitting within strict character limits (see Content Constraints section).

### 2. Learning System
Provides reference examples to improve Claude API content generation quality.

**Components:**
- **[extractor.py](extractor.py)**:
  - XML-based extraction from PPTX files (parses `ppt/slides/slideN.xml`)
  - PDF text extraction using pdfplumber
  - Detects document types (제안서, 결과보고서, 기획안, etc.)
  - Filters noise text (page numbers, copyright, placeholders)

- **[build_learning_data.py](build_learning_data.py)**:
  - Analyzes extracted content for patterns
  - Identifies common chapter formats, typical sections, text lengths
  - Builds `learning_data/patterns.json` with document-type-specific examples
  - Used by generator.py to provide reference examples in Claude prompts

### 3. Quality Checking System
Three-stage pipeline for spell-checking and term consistency validation.

**Entry point:** [integrated_pptx_checker.py](integrated_pptx_checker.py)

**Stages:**
1. **Ultra Think Text Extraction (Default Mode)**:
   - **Fast & Accurate**: XML parsing + Claude API structure classification
   - **XML extraction**: Structural extraction from `ppt/slides/slideN.xml` (~1-2 seconds)
   - **Claude API classification**: Automatic categorization into Chapter/Title/Subtitle/Lead/Contents (~5-10 seconds)
   - **Performance**: 10x faster than Vision API (15 seconds vs 3+ minutes for 7 slides)
   - **Structured output**: Returns organized data with semantic fields
   - **Fallback**: Gracefully falls back to XML-only if Claude API fails

2. **ML + Rules**: Combines fine-tuned model + rule-based checker (union of results)

3. **Claude Review**: Context-aware final review, identifies false positives, applies special rules

**Special rules enforced:**
- "펠로우" → "펠로"
- "기업가 정신" → "임팩트 앙트프러너십"
- "스타트업" → contextually determine if "임팩트 스타트업" is needed

**Output:** JSON report with issues categorized by type, source, and confidence level.

**Ultra Think Architecture (Default Mode):**

Files:
- [ultra_text_extractor.py](ultra_text_extractor.py): XML extraction + Claude API structure classification (default)
- [vision_text_extractor.py](vision_text_extractor.py): Alternative Vision API-based extraction (slower, for special cases)
- [pptx_to_images.py](pptx_to_images.py): PPTX → PNG conversion (for Vision API mode)

Workflow:
```
PPTX file → XML Parser (1-2s) → Claude API Classifier (5-10s) → Structured Output
                                        ↓
                          Chapter / Title / Subtitle / Lead / Contents
```

Benefits:
- **Speed**: 10x faster than Vision API (handles 300-page documents in 1-2 minutes)
- **Structure**: Automatic semantic classification of text elements
- **Accuracy**: Claude API intelligently categorizes based on position, order, and length
- **Reliability**: XML parsing is robust and deterministic

### 4. Template System
Templates define the visual structure while content is dynamically inserted.

**Mechanism:**
- Template file: `tem.pptx` (first slide used as template)
- Placeholder matching: Text content matching (case-insensitive)
  - "Chapter" → chapter field
  - "Title" → title field
  - "Subtitle" → subtitle field
  - "Lead" → lead field
- Slide duplication: `duplicate_slide()` deep-copies template slide XML structure
- Font application: Supports East Asian fonts via `a:ea` XML element

**Template analysis:** Use `python ppt_generator.py --analyze tem.pptx` to inspect template structure.

**Template extraction:** Use [template_extractor.py](template_extractor.py) to extract font styles, positions, and colors to JSON.

## 프로젝트 구조

```
pptMaker/
├── pipeline.py                    # 메인 진입점
├── generator.py                   # Claude API 콘텐츠 생성
├── ppt_generator.py               # 템플릿 기반 PPTX 생성
├── integrated_pptx_checker.py     # 3단계 품질 검사
├── template_extractor.py          # 템플릿 구조 분석
├── ultra_text_extractor.py        # 빠른 XML + Claude 추출
│
├── extractor.py                   # PPTX/PDF 텍스트 추출
├── build_learning_data.py         # 코퍼스 패턴 추출
├── extract_leads.py               # 리드문 추출
├── lead_scorer.py                 # 리드 품질 평가
├── lead_feedback_logger.py        # 사용자 피드백 로깅
├── pptx_checker.py                # 규칙 기반 맞춤법 검사
├── vision_text_extractor.py       # Vision API 대체 수단
├── pptx_to_images.py              # PPTX → PNG 변환
├── csv_to_json.py                 # 데이터 형식 변환
│
├── .claude/skills/                # Claude Code 스킬
│   ├── lead-writer/               # 수동 리드 작성 (인터랙티브)
│   ├── ppt-generator/             # 자동 PPT 생성
│   ├── ppt-checker/               # 품질 검사
│   ├── lead-inserter/             # 리드문 삽입
│   └── template-analyzer/         # 템플릿 분석
│
├── experiments/                   # 연구 및 실험 코드
│   ├── rl/                        # 강화학습 (GRPO)
│   │   ├── lead_rl_loop.py
│   │   ├── lead_rl_supervisor.py
│   │   ├── auto_rerun_controller.py
│   │   └── merge_run2_traces.py
│   ├── rag/                       # RAG 파이프라인 실험
│   │   ├── lead_rag_pipeline.py
│   │   ├── build_rag_index.py
│   │   └── analyze_similarity.py
│   ├── dataset_builders/          # 데이터셋 구축
│   │   ├── build_mvp_lead_datasets.py
│   │   ├── build_auto_mask_vocab.py
│   │   ├── build_lead_dataset.py
│   │   └── ...
│   ├── training/                  # 모델 파인튜닝
│   │   ├── finetune_lead_sft.py
│   │   ├── finetune_spelling_mps.py
│   │   └── test_lead_model.py
│   └── scripts/                   # 배치 처리
│       ├── run_overnight_rl.sh
│       └── monitor_overnight.sh
│
├── learning_data/                 # 학습 데이터 및 패턴
│   ├── patterns.json              # 콘텐츠 생성 패턴
│   ├── skill_examples/            # 스킬 학습 예시
│   ├── extracted_leads.json       # 리드문 코퍼스
│   └── fewshot_examples.json      # Knowledge Distillation 예시
│
├── rag/                           # RAG 모듈 (선택사항)
├── inputdata/                     # 참조 PPTX/PDF (gitignore)
└── tem.pptx                       # 기본 템플릿
```

## Data Formats

### Slide Data JSON
```json
{
  "slides": [
    {
      "page": 1,
      "chapter": "01. 섹션",
      "title": "제목",
      "subtitle": "부제목",
      "lead": "리드문"
    }
  ],
  "font_settings": {
    "chapter": {"name": "HDharmonyB", "size": 16, "bold": false, "color": "#000000"},
    "title": {"name": "HDharmonyB", "size": 16, "bold": false, "color": "#000000"},
    "subtitle": {"name": "HDharmonyM", "size": 16, "bold": false, "color": "#000000"},
    "lead": {"name": "HDharmonyL", "size": 12, "color": "#000000"}
  }
}
```

### Learning Data Patterns
Located at `learning_data/patterns.json`:
```json
{
  "metadata": {"source_count": N, "sources": [...]},
  "style_patterns": {
    "chapter_format": "##. 한글명",
    "title_avg_length": 15,
    "lead_avg_length": 50
  },
  "document_types": {
    "제안서": {
      "avg_slides": 20,
      "typical_sections": ["사업개요", "추진계획", ...],
      "examples": [{"chapter": "...", "title": "...", "lead": "..."}]
    }
  }
}
```

## Content Constraints

These are critical for Claude API prompts in [generator.py](generator.py):

- **chapter**: Maximum 5 characters (excluding numbers like "01. ")
  - Example: "발견", "채용", "집중"
- **title**: 10-20 characters
- **subtitle**: 15-30 characters (empty string if not needed)
- **lead**: 25-35 characters, **single line only (no `\n`)**

**Preservation principle:** User's original content, keywords, and phrasing must be preserved while fitting these constraints.

## Environment Setup

### Required Environment Variables
```bash
export ANTHROPIC_API_KEY="sk-ant-..."  # Required for generator.py and integrated_pptx_checker.py
```

### Dependencies
Install via `pip install -r requirements.txt`:
- `python-pptx>=0.6.21` - PPTX file manipulation
- `pdfplumber>=0.10.0` - PDF text extraction
- `anthropic>=0.18.0` - Claude API client

### Fonts
- Default: HDharmony family (HDharmonyB, HDharmonyM, HDharmonyL)
- Fonts must be installed on system for proper rendering
- Font settings are configurable in JSON slide data

## ML Models (Optional)

Fine-tuned models for spell-checking (used by integrated_pptx_checker.py):
- Model location: `./qwen3-spelling-checker/final/` or `./qwen3-spelling-checker/checkpoint-NNNN/`
- Training scripts: [finetune_spelling_mps.py](finetune_spelling_mps.py), [finetune_qwen3_mps.py](finetune_qwen3_mps.py)
- Dataset building: [build_spelling_dataset.py](build_spelling_dataset.py)
- Testing: [test_spelling_model.py](test_spelling_model.py)

Models use LoRA/PEFT for efficient fine-tuning on Apple Silicon (MPS backend).
