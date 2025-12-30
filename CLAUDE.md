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
```

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
