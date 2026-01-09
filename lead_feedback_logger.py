#!/usr/bin/env python3
"""
lead_feedback_logger.py

리드문 스킬 사용자 피드백 로깅 시스템
- 사용자 선택 기록 (chosen/rejected)
- 피드백 수집 (좋아요/보통/아쉬워요)
- 나중에 DPO 학습용 데이터로 활용
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class FeedbackLogger:
    """피드백 로거"""

    def __init__(self, log_path: Optional[str] = None):
        if log_path is None:
            base_dir = Path(__file__).parent
            log_path = base_dir / "learning_data" / "skill_feedback.jsonl"
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_session(
        self,
        session_id: str,
        industry: str,
        part: str,
        slots: list,
        slot_values: dict,
        tone: str,
        candidates: list,
        chosen: str,
        chosen_index: int,
        custom_edit: Optional[str] = None,
        rating: Optional[str] = None,
        feedback_text: Optional[str] = None,
        reference_data: Optional[str] = None,
    ):
        """
        세션 피드백 로깅

        Args:
            session_id: 세션 고유 ID
            industry: 산업/분야 (자유 입력)
            part: 문서 파트 (INTRO, OVERVIEW, PART 3, PLAN 등)
            slots: 선택한 슬롯 목록
            slot_values: 슬롯 값 딕셔너리
            tone: 문투 (공식적, 친근한, 간결한)
            candidates: 생성된 후보 리스트
            chosen: 선택된 텍스트
            chosen_index: 선택된 인덱스 (0, 1, 2)
            custom_edit: 사용자가 직접 수정한 경우 수정된 텍스트
            rating: 만족도 (좋아요, 보통, 아쉬워요)
            feedback_text: 추가 피드백 텍스트
            reference_data: 사용자가 제공한 참고 데이터 정보
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "input": {
                "industry": industry,
                "part": part,
                "slots": slots,
                "slot_values": slot_values,
                "tone": tone,
                "reference_data": reference_data,
            },
            "generation": {
                "candidates": candidates,
                "chosen": chosen,
                "chosen_index": chosen_index,
                "rejected": [c for i, c in enumerate(candidates) if i != chosen_index],
                "custom_edit": custom_edit,
            },
            "feedback": {
                "rating": rating,
                "text": feedback_text,
            }
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return entry

    def to_dpo_pairs(self, min_rating: str = "보통") -> list:
        """
        피드백 로그를 DPO 학습용 페어로 변환

        Args:
            min_rating: 최소 만족도 (좋아요, 보통)

        Returns:
            DPO pairs 리스트 [{"prompt": ..., "chosen": ..., "rejected": ...}, ...]
        """
        rating_order = {"좋아요": 3, "보통": 2, "아쉬워요": 1, None: 0}
        min_score = rating_order.get(min_rating, 0)

        pairs = []

        if not self.log_path.exists():
            return pairs

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)

                # 만족도 체크
                rating = entry.get("feedback", {}).get("rating")
                if rating_order.get(rating, 0) < min_score:
                    continue

                # 프롬프트 구성
                inp = entry.get("input", {})
                prompt = self._build_prompt(inp)

                # chosen (커스텀 수정이 있으면 그것 사용)
                gen = entry.get("generation", {})
                chosen = gen.get("custom_edit") or gen.get("chosen")

                # rejected (선택되지 않은 것들)
                for rejected in gen.get("rejected", []):
                    pairs.append({
                        "prompt": prompt,
                        "chosen": chosen,
                        "rejected": rejected,
                        "meta": {
                            "session_id": entry.get("session_id"),
                            "rating": rating,
                            "industry": inp.get("industry"),
                        }
                    })

        return pairs

    def _build_prompt(self, inp: dict) -> str:
        """입력 정보로 프롬프트 구성"""
        parts = [
            "Task: Generate a single-sentence meta lead.",
            f"PART: {inp.get('part', 'UNKNOWN')}",
            f"SLOTS: {', '.join(inp.get('slots', [])) or 'NONE'}",
            f"INDUSTRY: {inp.get('industry', 'general')}",
            f"TONE: {inp.get('tone', '공식적')}",
            "LENGTH: 40-70",
            "ENDING: 합니다.",
        ]
        return "\n".join(parts)

    def get_stats(self) -> dict:
        """피드백 통계"""
        if not self.log_path.exists():
            return {"total": 0}

        total = 0
        rating_counts = {"좋아요": 0, "보통": 0, "아쉬워요": 0, None: 0}
        part_counts = {}
        industry_counts = {}
        custom_edit_count = 0

        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                total += 1

                # 만족도
                rating = entry.get("feedback", {}).get("rating")
                rating_counts[rating] = rating_counts.get(rating, 0) + 1

                # 파트
                part = entry.get("input", {}).get("part", "UNKNOWN")
                part_counts[part] = part_counts.get(part, 0) + 1

                # 산업
                industry = entry.get("input", {}).get("industry", "unknown")
                industry_counts[industry] = industry_counts.get(industry, 0) + 1

                # 커스텀 수정
                if entry.get("generation", {}).get("custom_edit"):
                    custom_edit_count += 1

        return {
            "total": total,
            "by_rating": rating_counts,
            "by_part": part_counts,
            "by_industry": industry_counts,
            "custom_edit_count": custom_edit_count,
            "custom_edit_rate": round(custom_edit_count / total, 4) if total > 0 else 0,
        }


def generate_session_id() -> str:
    """세션 ID 생성"""
    import uuid
    return str(uuid.uuid4())[:8]


# 편의 함수
_logger = None

def get_logger() -> FeedbackLogger:
    """싱글톤 로거 반환"""
    global _logger
    if _logger is None:
        _logger = FeedbackLogger()
    return _logger


def log_feedback(
    industry: str,
    part: str,
    slots: list,
    slot_values: dict,
    tone: str,
    candidates: list,
    chosen: str,
    chosen_index: int,
    custom_edit: Optional[str] = None,
    rating: Optional[str] = None,
    feedback_text: Optional[str] = None,
    reference_data: Optional[str] = None,
) -> dict:
    """피드백 로깅 (편의 함수)"""
    logger = get_logger()
    session_id = generate_session_id()
    return logger.log_session(
        session_id=session_id,
        industry=industry,
        part=part,
        slots=slots,
        slot_values=slot_values,
        tone=tone,
        candidates=candidates,
        chosen=chosen,
        chosen_index=chosen_index,
        custom_edit=custom_edit,
        rating=rating,
        feedback_text=feedback_text,
        reference_data=reference_data,
    )


if __name__ == "__main__":
    # 테스트
    logger = FeedbackLogger()

    # 샘플 로깅
    entry = logger.log_session(
        session_id="test001",
        industry="환경/그린테크",
        part="OVERVIEW",
        slots=["ORG", "TARGET"],
        slot_values={"ORG": "MYSC", "TARGET": "환경 스타트업"},
        tone="공식적",
        candidates=[
            "MYSC의 청년그린창업 스프링캠프를 통해 환경 스타트업의 성장을 지원합니다.",
            "2026년 환경 스타트업을 위한 맞춤형 액셀러레이팅 프로그램을 운영합니다.",
            "MYSC는 환경 분야 창업팀에게 체계적인 사업화 지원을 제공합니다.",
        ],
        chosen="MYSC의 청년그린창업 스프링캠프를 통해 환경 스타트업의 성장을 지원합니다.",
        chosen_index=0,
        rating="좋아요",
    )

    print("Logged entry:")
    print(json.dumps(entry, ensure_ascii=False, indent=2))

    # 통계
    print("\nStats:")
    print(json.dumps(logger.get_stats(), ensure_ascii=False, indent=2))

    # DPO 변환
    print("\nDPO pairs:")
    pairs = logger.to_dpo_pairs()
    for pair in pairs:
        print(json.dumps(pair, ensure_ascii=False, indent=2))
