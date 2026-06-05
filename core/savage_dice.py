"""Savage Worlds 骰子系统"""

import random
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class DiceResult:
    trait_roll: int
    wild_roll: int
    total: int
    is_raise: bool = False
    is_critical_fail: bool = False
    raises: int = 0

    def __str__(self):
        wild_str = f" [Wild d6={self.wild_roll}]"
        raise_str = f" ✨Raise x{self.raises}!" if self.raises > 0 else ""
        crit_str = " 💀CRIT FAIL!" if self.is_critical_fail else ""
        return f"d8={self.trait_roll}{wild_str} → {self.total}{raise_str}{crit_str}"


class SavageDice:
    TRAIT_DIE = 8
    WILD_DIE = 6

    @staticmethod
    def roll(trait_die: int = TRAIT_DIE,
             wild_die: int = WILD_DIE) -> DiceResult:
        trait_roll = random.randint(1, trait_die)
        wild_roll = random.randint(1, wild_die)
        total = max(trait_roll, wild_roll)
        is_critical_fail = (trait_roll == 1 and wild_roll == 1)
        return DiceResult(
            trait_roll=trait_roll,
            wild_roll=wild_roll,
            total=total,
            is_critical_fail=is_critical_fail
        )

    @staticmethod
    def roll_with_target(target_number: int,
                        trait_die: int = TRAIT_DIE,
                        wild_die: int = WILD_DIE) -> DiceResult:
        result = SavageDice.roll(trait_die, wild_die)
        result.is_raise = result.total >= target_number + 4
        if result.total >= target_number:
            result.raises = (result.total - target_number) // 4
        return result

    @staticmethod
    def damage_roll(dice_notation: str) -> int:
        import re
        match = re.match(r'(\d+)d(\d+)(?:([+-])(\d+))?', dice_notation)
        if not match:
            return 0
        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = 0
        if match.group(3):
            sign = 1 if match.group(3) == '+' else -1
            modifier = sign * int(match.group(4))
        total = sum(random.randint(1, die_size) for _ in range(num_dice))
        return total + modifier

    @staticmethod
    def spend_bennie() -> int:
        return random.randint(1, SavageDice.TRAIT_DIE)

    @staticmethod
    def roll_initiative() -> Tuple[int, int]:
        return random.randint(1, 8), random.randint(1, 6)
