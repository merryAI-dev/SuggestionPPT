#!/usr/bin/env python3
"""
lead_scorer.py

리드문 품질 평가 모듈
- 길이 체크 (40-70자)
- 엔딩 체크 ("합니다." 등)
- 슬롯 사용 체크 (중복 금지, 누락 금지)
- 금지어 체크
- 쉼표 사용 페널티
"""

import re
from collections import Counter
from typing import Optional


# 허용된 플레이스홀더
ALLOWED_PLACEHOLDERS = {
    'ORG', 'TARGET', 'EFFECT', 'METHOD', 'YEAR', 'AMOUNT', 'COUNT', 'SCOPE'
}

# 숫자 관련 플레이스홀더
NUMBER_PLACEHOLDERS = {'YEAR', 'AMOUNT', 'COUNT'}

# 기본 절 마커 (복문 감지용)
DEFAULT_CLAUSE_MARKERS = ['그리고', '또한', '아울러', '더불어', '한편']

# 금지어 기본값
DEFAULT_FORBIDDEN_WORDS = ['펠로우']  # "펠로우" → "펠로"

# 플레이스홀더 패턴
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Z_]+)\}")


class LeadScorer:
    """리드문 점수 평가기"""

    def __init__(
        self,
        length_min: int = 100,
        length_max: int = 120,
        ending: str = "합니다.",
        length_penalty: float = 2.0,
        ending_penalty: float = 1.0,
        slot_repeat_penalty: float = 1.0,
        comma_penalty: float = 0.5,
        clause_penalty: float = 0.5,
        forbidden_penalty: float = 1.0,
        clause_markers: Optional[list] = None,
        forbidden_words: Optional[list] = None,
    ):
        self.length_min = length_min
        self.length_max = length_max
        self.ending = ending
        self.length_penalty = length_penalty
        self.ending_penalty = ending_penalty
        self.slot_repeat_penalty = slot_repeat_penalty
        self.comma_penalty = comma_penalty
        self.clause_penalty = clause_penalty
        self.forbidden_penalty = forbidden_penalty
        self.clause_markers = clause_markers or DEFAULT_CLAUSE_MARKERS
        self.forbidden_words = forbidden_words or DEFAULT_FORBIDDEN_WORDS

    def score(
        self,
        text: str,
        required_slots: Optional[list] = None,
        max_slot_repeat: int = 1,
    ) -> tuple[float, dict]:
        """
        리드문 점수 계산

        Args:
            text: 평가할 텍스트
            required_slots: 필수 슬롯 목록 (예: ['ORG', 'TARGET'])
            max_slot_repeat: 슬롯 최대 반복 횟수

        Returns:
            (점수, 상세 정보 dict)
        """
        score = 0.0
        details = {}
        length = len(text)
        required_slots = required_slots or []

        # 1. 길이 체크
        if self.length_min <= length <= self.length_max:
            score += 2.0
            details["length_ok"] = True
            details["length"] = length
        else:
            distance = min(
                abs(length - self.length_min),
                abs(length - self.length_max)
            )
            penalty = min(distance / 5.0, 3.0) + self.length_penalty
            score -= penalty
            details["length_ok"] = False
            details["length"] = length
            details["length_penalty"] = round(penalty, 2)

        # 2. 엔딩 체크 (다양한 경어체 엔딩 허용)
        valid_endings = ["합니다.", "입니다.", "습니다.", "됩니다.", "드립니다.", "옵니다."]
        if self.ending:
            if any(text.endswith(e) for e in valid_endings):
                score += 1.0
                details["ending_ok"] = True
            else:
                score -= self.ending_penalty
                details["ending_ok"] = False
                details["actual_ending"] = text[-10:] if len(text) >= 10 else text

        # 3. 슬롯 사용 체크
        placeholders = PLACEHOLDER_PATTERN.findall(text)

        # 3a. 필수 슬롯 누락 체크
        missing_slots = []
        for slot in required_slots:
            token = f"{{{slot}}}"
            if token in text:
                score += 1.0
            else:
                missing_slots.append(slot)
                score -= 1.0
        details["missing_slots"] = missing_slots

        # 3b. 알 수 없는 슬롯 체크
        unknown = [
            token for token in placeholders
            if token not in ALLOWED_PLACEHOLDERS and token not in required_slots
        ]
        if unknown:
            score -= 0.5 * len(unknown)
        details["unknown_placeholders"] = unknown

        # 3c. 슬롯 반복 체크
        if max_slot_repeat > 0:
            slot_counts = Counter(placeholders)
            repeats = {
                slot: count for slot, count in slot_counts.items()
                if count > max_slot_repeat
            }
            if repeats:
                extra = sum(count - max_slot_repeat for count in repeats.values())
                penalty = self.slot_repeat_penalty * extra
                score -= penalty
                details["slot_repeats"] = repeats
                details["slot_repeat_penalty"] = round(penalty, 2)

        # 4. 쉼표 체크
        if "," in text or "\uff0c" in text:
            score -= self.comma_penalty
            details["comma"] = True

        # 5. 복문 마커 체크
        clause_hits = [m for m in self.clause_markers if m in text]
        if clause_hits:
            score -= self.clause_penalty
            details["clause_markers"] = clause_hits

        # 6. 개행 체크
        if "\n" in text:
            score -= 0.5
            details["newline"] = True

        # 7. 복수 문장 체크
        if len(re.findall(r"[.!?]", text)) > 1:
            score -= 0.5
            details["multi_sentence"] = True

        # 8. 금지어 체크
        forbidden_hits = [w for w in self.forbidden_words if w in text]
        if forbidden_hits:
            score -= self.forbidden_penalty * len(forbidden_hits)
            details["forbidden_words"] = forbidden_hits

        # 9. 인접 중복 슬롯 체크
        if re.search(r"(\{[A-Z_]+\})\s*\1", text):
            score -= 0.5
            details["duplicate_placeholder"] = True

        # 10. 숫자 유출 체크 (슬롯 없이 숫자 사용)
        digit_leak = bool(re.search(r"\d", text)) and not any(
            f"{{{slot}}}" in text for slot in NUMBER_PLACEHOLDERS
        )
        if digit_leak:
            score -= 1.0
            details["digit_leak"] = True

        return round(score, 2), details

    def passes_hard_constraints(
        self,
        text: str,
        required_slots: Optional[list] = None,
        max_slot_repeat: int = 1,
    ) -> tuple[bool, list]:
        """
        하드 제약 조건 통과 여부 체크

        Returns:
            (통과 여부, 위반 사항 목록)
        """
        violations = []
        required_slots = required_slots or []
        length = len(text)

        # 길이
        if not (self.length_min <= length <= self.length_max):
            violations.append(f"length: {length} (required: {self.length_min}-{self.length_max})")

        # 엔딩 (다양한 경어체 허용)
        valid_endings = ["합니다.", "입니다.", "습니다.", "됩니다.", "드립니다.", "옵니다."]
        if self.ending and not any(text.endswith(e) for e in valid_endings):
            violations.append(f"ending: must end with formal Korean ending")

        # 필수 슬롯
        for slot in required_slots:
            if f"{{{slot}}}" not in text:
                violations.append(f"missing_slot: {slot}")

        # 슬롯 반복
        placeholders = PLACEHOLDER_PATTERN.findall(text)
        if max_slot_repeat > 0:
            slot_counts = Counter(placeholders)
            for slot, count in slot_counts.items():
                if count > max_slot_repeat:
                    violations.append(f"slot_repeat: {slot} ({count}x)")

        # 쉼표
        if "," in text or "\uff0c" in text:
            violations.append("comma: contains comma")

        # 개행
        if "\n" in text:
            violations.append("newline: contains newline")

        return len(violations) == 0, violations

    def get_constraint_satisfaction_rate(self, texts: list, required_slots: Optional[list] = None) -> dict:
        """
        여러 텍스트에 대한 제약 만족률 계산

        Returns:
            {
                "total": 100,
                "passed": 85,
                "rate": 0.85,
                "by_constraint": {
                    "length": 0.90,
                    "ending": 0.95,
                    ...
                }
            }
        """
        total = len(texts)
        passed = 0
        constraint_counts = {
            "length": 0,
            "ending": 0,
            "slots": 0,
            "comma": 0,
            "newline": 0,
        }

        for text in texts:
            ok, violations = self.passes_hard_constraints(text, required_slots)
            if ok:
                passed += 1

            # 개별 제약 체크
            length = len(text)
            if self.length_min <= length <= self.length_max:
                constraint_counts["length"] += 1
            valid_endings = ["합니다.", "입니다.", "습니다.", "됩니다.", "드립니다.", "옵니다."]
            if not self.ending or any(text.endswith(e) for e in valid_endings):
                constraint_counts["ending"] += 1
            if not any(v.startswith("missing_slot") for v in violations):
                constraint_counts["slots"] += 1
            if "," not in text and "\uff0c" not in text:
                constraint_counts["comma"] += 1
            if "\n" not in text:
                constraint_counts["newline"] += 1

        return {
            "total": total,
            "passed": passed,
            "rate": round(passed / total, 4) if total > 0 else 0,
            "by_constraint": {
                k: round(v / total, 4) if total > 0 else 0
                for k, v in constraint_counts.items()
            }
        }


# 편의 함수
def score_lead(text: str, constraints: Optional[dict] = None) -> tuple[float, dict]:
    """
    간단한 점수 계산 함수

    Args:
        text: 평가할 텍스트
        constraints: {
            "length_min": 40,
            "length_max": 70,
            "ending": "합니다.",
            "slots": ["ORG", "TARGET"],
            "forbidden_words": ["펠로우"]
        }

    Returns:
        (점수, 상세 정보)
    """
    constraints = constraints or {}
    scorer = LeadScorer(
        length_min=constraints.get("length_min", 100),
        length_max=constraints.get("length_max", 120),
        ending=constraints.get("ending", "합니다."),
        forbidden_words=constraints.get("forbidden_words"),
    )
    return scorer.score(
        text,
        required_slots=constraints.get("slots", []),
    )


if __name__ == "__main__":
    # 테스트
    scorer = LeadScorer()

    test_cases = [
        # 좋은 예시
        "MYSC의 청년그린창업 스프링캠프를 통해 환경 스타트업의 성장을 지원합니다.",
        # 너무 짧음
        "지원합니다.",
        # 엔딩 틀림
        "MYSC는 환경 스타트업을 지원해요",
        # 쉼표 포함
        "MYSC는 환경, 그린테크 스타트업을 지원합니다.",
        # 슬롯 사용
        "{ORG}는 {TARGET}을 위한 프로그램을 운영합니다.",
        # 슬롯 중복
        "{ORG}와 {ORG}가 함께 프로그램을 운영합니다.",
    ]

    print("=" * 60)
    print("Lead Scorer Test")
    print("=" * 60)

    for text in test_cases:
        score, details = scorer.score(text)
        print(f"\nText: {text}")
        print(f"Length: {len(text)}")
        print(f"Score: {score}")
        print(f"Details: {details}")
        print("-" * 40)
