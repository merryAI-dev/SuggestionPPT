#!/usr/bin/env python3
"""
lead_retriever.py

리드문 few-shot 유사도 검색기 (순수 Python, API 미사용)

learning_data/skill_examples/ 코퍼스에서 대상 슬라이드와 가장 유사한
리드문 예시를 뽑아 few-shot 재료로 제공합니다.

검색 신호:
- part          : INTRO / OVERVIEW / PART_1..4 / PLAN / UNKNOWN
- slots         : 리드문에 사용할 슬롯 집합 (EFFECT, METHOD, ORG, TARGET, ...)
- keywords      : 슬라이드 컨텍스트에서 뽑은 키워드
- score(코퍼스)  : 예시의 품질 점수 (높을수록 좋음)

사용 (CLI):
    python3 lead_retriever.py --part PART_3 --slots EFFECT,METHOD,TARGET \
        --keywords 지원,전문가,경영 --k 5 --json

사용 (import):
    from lead_retriever import retrieve
    examples = retrieve(part="PART_3", slots=["EFFECT","METHOD"], keywords=["지원"], k=5)
"""

import argparse
import glob
import json
import re
from pathlib import Path

SKILL_EXAMPLES_DIR = Path(__file__).parent / "learning_data" / "skill_examples"
SLOT_PATTERN = re.compile(r"\{([A-Z_]+)\}")

# 유사도 가중치 (합 1.0 근처)
W_SLOT = 0.35      # 슬롯 시그니처 겹침
W_KEYWORD = 0.30   # 키워드 겹침
W_TEXT = 0.15      # 키워드가 output 본문에 등장하는 비율
W_QUALITY = 0.20   # 코퍼스 품질 점수 (풀 내 정규화)


def _norm_part(part: str) -> str:
    """'PART 3' / 'part_3' → 'PART_3' 로 정규화."""
    return (part or "UNKNOWN").strip().upper().replace(" ", "_")


def _slots_of(output: str) -> set:
    """output 본문에서 {SLOT} 토큰을 추출."""
    return set(SLOT_PATTERN.findall(output or ""))


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _text_hit_ratio(keywords, output: str) -> float:
    """query 키워드 중 output 본문에 실제로 등장하는 비율."""
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw and kw in output)
    return hits / len(keywords)


def _dedup_key(output: str) -> str:
    """공백·따옴표 제거한 정규화 키 (완전 중복 제거용)."""
    return re.sub(r"\s+", "", output or "").strip("\"'")


def _shingles(text: str, n: int = 3) -> set:
    """문자 n-gram 집합 (근사 중복 판정용)."""
    t = re.sub(r"\s+", "", text or "")
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _too_similar(output: str, selected_shingles: list, threshold: float) -> bool:
    """이미 뽑은 예시들과 근사 중복인지 (few-shot 다양성 확보)."""
    sh = _shingles(output)
    return any(_jaccard(sh, prev) >= threshold for prev in selected_shingles)


def _load_pool(part: str) -> list:
    """대상 part 에 해당하는 후보 예시 풀을 로드."""
    part_norm = _norm_part(part)
    pool = []

    # 1) by_part_slots/{PART}__*.json (슬롯 조합별)
    for fp in glob.glob(str(SKILL_EXAMPLES_DIR / "by_part_slots" / f"{part_norm}__*.json")):
        bucket = Path(fp).stem
        try:
            items = json.loads(Path(fp).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for it in items:
            pool.append({**it, "bucket": bucket, "source": "by_part_slots"})

    # 2) by_part/{PART}.json (슬롯 없이 파트별)
    fp = SKILL_EXAMPLES_DIR / "by_part" / f"{part_norm}.json"
    if fp.exists():
        try:
            for it in json.loads(fp.read_text(encoding="utf-8")):
                pool.append({**it, "bucket": part_norm, "source": "by_part"})
        except (OSError, json.JSONDecodeError):
            pass

    return pool


def retrieve(part="UNKNOWN", slots=None, keywords=None, k=5,
             min_score=None, fallback_unknown=True, diversity_threshold=0.6):
    """
    대상 슬라이드와 유사한 리드문 예시 top-k 를 반환.

    Args:
        part: 파트 (INTRO/OVERVIEW/PART_1..4/PLAN/UNKNOWN)
        slots: 사용할 슬롯 리스트 (예: ["ORG","TARGET"])
        keywords: 컨텍스트 키워드 리스트
        k: 반환 개수
        min_score: 코퍼스 품질 점수 하한 (None이면 필터 없음)
        fallback_unknown: 결과가 부족하면 UNKNOWN 파트로 보강

    Returns:
        [{output, score, keywords, bucket, source, similarity}, ...]
    """
    slots = set(slots or [])
    keywords = [k_.strip() for k_ in (keywords or []) if k_ and k_.strip()]

    pool = _load_pool(part)
    if fallback_unknown and len(pool) < k * 3 and _norm_part(part) != "UNKNOWN":
        pool += _load_pool("UNKNOWN")

    if not pool:
        return []

    if min_score is not None:
        pool = [it for it in pool if it.get("score", 0) >= min_score]
        if not pool:
            return []

    # 품질 점수 풀 내 min-max 정규화
    scores = [it.get("score", 0) for it in pool]
    s_min, s_max = min(scores), max(scores)
    s_span = (s_max - s_min) or 1.0

    ranked = []
    for it in pool:
        output = it.get("output", "")
        entry_slots = _slots_of(output)
        entry_kw = set(it.get("keywords", []))

        slot_sim = _jaccard(slots, entry_slots) if slots else 0.0
        kw_sim = _jaccard(set(keywords), entry_kw) if keywords else 0.0
        text_sim = _text_hit_ratio(keywords, output)
        quality = (it.get("score", 0) - s_min) / s_span

        similarity = (
            W_SLOT * slot_sim
            + W_KEYWORD * kw_sim
            + W_TEXT * text_sim
            + W_QUALITY * quality
        )
        ranked.append({**it, "similarity": round(similarity, 4)})

    # 유사도 내림차순, 동점이면 품질 우선
    ranked.sort(key=lambda x: (x["similarity"], x.get("score", 0)), reverse=True)

    # 완전 중복 + 근사 중복 제거하며 top-k 채우기 (few-shot 다양성 확보)
    seen = set()
    selected_shingles = []
    results = []
    for it in ranked:
        output = it.get("output", "")
        key = _dedup_key(output)
        if key in seen:
            continue
        if _too_similar(output, selected_shingles, diversity_threshold):
            continue
        seen.add(key)
        selected_shingles.append(_shingles(output))
        results.append(it)
        if len(results) >= k:
            break

    return results


def available_buckets(part=None):
    """사용 가능한 part / part_slots 버킷 목록 (스킬이 파트 판별 시 참고)."""
    parts = sorted(
        p.stem for p in (SKILL_EXAMPLES_DIR / "by_part").glob("*.json")
    )
    slot_buckets = sorted(
        p.stem for p in (SKILL_EXAMPLES_DIR / "by_part_slots").glob("*.json")
    )
    if part:
        part_norm = _norm_part(part)
        slot_buckets = [b for b in slot_buckets if b.startswith(part_norm + "__")]
    return {"parts": parts, "slot_buckets": slot_buckets}


def _format_human(results, query) -> str:
    lines = [
        f"[검색 쿼리] part={query['part']} slots={query['slots']} keywords={query['keywords']}",
        f"[결과] {len(results)}개",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. (sim={r['similarity']}, score={r.get('score')}, bucket={r.get('bucket')})")
        lines.append(f"   {r.get('output')}")
        kw = r.get("keywords") or []
        if kw:
            lines.append(f"   keywords: {', '.join(kw)}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="리드문 few-shot 유사도 검색기")
    parser.add_argument("--part", default="UNKNOWN", help="파트 (INTRO/OVERVIEW/PART_1..4/PLAN/UNKNOWN)")
    parser.add_argument("--slots", default="", help="슬롯, 쉼표 구분 (예: EFFECT,METHOD,TARGET)")
    parser.add_argument("--keywords", default="", help="키워드, 쉼표 구분")
    parser.add_argument("--k", type=int, default=5, help="반환 개수")
    parser.add_argument("--min-score", type=float, default=None, help="품질 점수 하한")
    parser.add_argument("--diversity", type=float, default=0.6,
                        help="근사 중복 임계값 (낮을수록 더 다양하게, 0~1)")
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    parser.add_argument("--list-buckets", action="store_true", help="사용 가능한 버킷 목록만 출력")
    args = parser.parse_args()

    if args.list_buckets:
        print(json.dumps(available_buckets(args.part if args.part != "UNKNOWN" else None),
                         ensure_ascii=False, indent=2))
        return

    slots = [s.strip() for s in args.slots.split(",") if s.strip()]
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    results = retrieve(
        part=args.part, slots=slots, keywords=keywords,
        k=args.k, min_score=args.min_score, diversity_threshold=args.diversity,
    )

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(_format_human(results, {"part": args.part, "slots": slots, "keywords": keywords}))


if __name__ == "__main__":
    main()
