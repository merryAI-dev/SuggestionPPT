#!/usr/bin/env python3
"""
build_skill_examples.py

데이터를 PART + SLOTS 기준으로 분류하여 Skill용 예시 데이터 생성

소스:
1. rl_run2_90k.jsonl (PART별, 슬롯 없음)
2. rl_pairs.environment_aug10.jsonl (PART+SLOTS 조합)

출력:
learning_data/skill_examples/
├── by_part/           # PART별 (슬롯 없음)
└── by_part_slots/     # PART+SLOTS 조합
"""

import json
import os
from collections import defaultdict
from pathlib import Path


def parse_prompt_fields(text: str) -> dict:
    """프롬프트에서 PART, SLOTS, KEYWORDS 추출"""
    fields = {}
    for line in text.split('\n'):
        if line.startswith('PART:'):
            part = line.replace('PART:', '').strip()
            if '(' in part:
                part = part.split('(')[0].strip()
            fields['part'] = part
        elif line.startswith('SLOTS:'):
            slots_str = line.replace('SLOTS:', '').strip()
            if slots_str == 'NONE':
                fields['slots'] = []
            else:
                fields['slots'] = sorted([s.strip() for s in slots_str.split(',')])
        elif line.startswith('KEYWORDS:'):
            kw_str = line.replace('KEYWORDS:', '').strip()
            if kw_str == 'NONE':
                fields['keywords'] = []
            else:
                fields['keywords'] = [k.strip() for k in kw_str.split(',')]
    return fields


def load_rl_run2_data(filepath: str) -> list:
    """rl_run2_90k.jsonl 로드 (input/output/meta 형식)"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            d = json.loads(line)
            fields = parse_prompt_fields(d.get('input', ''))
            data.append({
                'part': fields.get('part', 'UNKNOWN'),
                'slots': fields.get('slots', []),
                'keywords': fields.get('keywords', []),
                'output': d.get('output', ''),
                'score': d.get('meta', {}).get('score', 0),
                'source': 'rl_run2_90k'
            })
    return data


def load_rl_pairs_data(filepath: str) -> list:
    """rl_pairs.*.jsonl 로드 (prompt/chosen/rejected/meta 형식)"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            d = json.loads(line)
            fields = parse_prompt_fields(d.get('prompt', ''))
            # chosen만 사용 (고품질)
            data.append({
                'part': fields.get('part', 'UNKNOWN'),
                'slots': fields.get('slots', []),
                'keywords': fields.get('keywords', []),
                'output': d.get('chosen', ''),
                'score': d.get('meta', {}).get('chosen_score', 0),
                'source': 'rl_pairs_aug10'
            })
    return data


def group_by_part(data: list) -> dict:
    """PART별로 그룹핑"""
    groups = defaultdict(list)
    for item in data:
        groups[item['part']].append(item)
    return groups


def group_by_part_slots(data: list) -> dict:
    """PART + SLOTS 조합으로 그룹핑"""
    groups = defaultdict(list)
    for item in data:
        if item['slots']:  # 슬롯이 있는 경우만
            key = f"{item['part']}__{'-'.join(item['slots'])}"
            groups[key].append(item)
    return groups


def select_top_n(items: list, n: int) -> list:
    """점수 기준 상위 N개 선택"""
    sorted_items = sorted(items, key=lambda x: -x['score'])
    return sorted_items[:n]


def save_examples(groups: dict, output_dir: str, top_n_map: dict):
    """그룹별로 JSON 파일 저장"""
    os.makedirs(output_dir, exist_ok=True)

    stats = {}
    for key, items in groups.items():
        # 파일명 정리 (공백, 특수문자 처리)
        safe_key = key.replace(' ', '_').replace('/', '_')

        # top_n 결정 (기본값 100)
        top_n = top_n_map.get(key, 100)
        selected = select_top_n(items, top_n)

        # 저장할 데이터 정리
        output_data = []
        for item in selected:
            output_data.append({
                'output': item['output'],
                'score': item['score'],
                'keywords': item['keywords']
            })

        filepath = os.path.join(output_dir, f"{safe_key}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        stats[key] = {
            'total': len(items),
            'selected': len(selected),
            'avg_score': sum(i['score'] for i in selected) / len(selected) if selected else 0
        }

    return stats


def main():
    base_dir = Path(__file__).parent
    learning_dir = base_dir / 'learning_data'
    output_base = learning_dir / 'skill_examples'

    # 1. 데이터 로드
    print("Loading data...")

    # 1차 소스: rl_run2_90k.jsonl
    rl_run2_path = learning_dir / 'rl_run2_90k.jsonl'
    if rl_run2_path.exists():
        rl_run2_data = load_rl_run2_data(str(rl_run2_path))
        print(f"  rl_run2_90k.jsonl: {len(rl_run2_data)} samples")
    else:
        rl_run2_data = []
        print(f"  rl_run2_90k.jsonl: not found")

    # 2차 소스: rl_pairs.environment_aug10.jsonl
    rl_pairs_path = learning_dir / 'rl_pairs.environment_aug10.jsonl'
    if rl_pairs_path.exists():
        rl_pairs_data = load_rl_pairs_data(str(rl_pairs_path))
        print(f"  rl_pairs.environment_aug10.jsonl: {len(rl_pairs_data)} samples")
    else:
        rl_pairs_data = []
        print(f"  rl_pairs.environment_aug10.jsonl: not found")

    # 2. PART별 그룹핑 (1차 소스)
    print("\nGrouping by PART...")
    part_groups = group_by_part(rl_run2_data)

    # PART별 top_n 설정
    part_top_n = {
        'UNKNOWN': 500,
        'OVERVIEW': 500,
        'PART 3': 300,
        'PLAN': 200,
        'INTRO': 100,
        'PART 1': 100,
        'PART 2': 100,
        'PART 4': 100,
    }

    by_part_dir = output_base / 'by_part'
    part_stats = save_examples(part_groups, str(by_part_dir), part_top_n)

    print("  PART groups saved:")
    for key, stat in sorted(part_stats.items()):
        print(f"    {key}: {stat['selected']}/{stat['total']} (avg: {stat['avg_score']:.2f})")

    # 3. PART+SLOTS 그룹핑 (2차 소스)
    print("\nGrouping by PART+SLOTS...")
    part_slots_groups = group_by_part_slots(rl_pairs_data)

    # 모든 조합에 대해 최대 50개씩
    slots_top_n = {key: 50 for key in part_slots_groups.keys()}

    by_part_slots_dir = output_base / 'by_part_slots'
    slots_stats = save_examples(part_slots_groups, str(by_part_slots_dir), slots_top_n)

    print("  PART+SLOTS groups saved:")
    for key, stat in sorted(slots_stats.items()):
        print(f"    {key}: {stat['selected']}/{stat['total']} (avg: {stat['avg_score']:.2f})")

    # 4. 통계 요약
    print("\n" + "="*50)
    print("Summary:")
    print(f"  by_part/: {len(part_stats)} files")
    print(f"  by_part_slots/: {len(slots_stats)} files")
    print(f"  Total examples: {sum(s['selected'] for s in part_stats.values()) + sum(s['selected'] for s in slots_stats.values())}")
    print("="*50)


if __name__ == '__main__':
    main()
