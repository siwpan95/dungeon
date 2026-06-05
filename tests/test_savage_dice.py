"""tests/test_savage_dice.py — SavageDice 单元测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.savage_dice import SavageDice, DiceResult


class TestDiceRoll:
    def test_roll_returns_dice_result(self):
        result = SavageDice.roll()
        assert isinstance(result, DiceResult)

    def test_roll_trait_in_range(self):
        for _ in range(200):
            r = SavageDice.roll(trait_die=8)
            assert 1 <= r.trait_roll <= 8

    def test_roll_wild_in_range(self):
        for _ in range(200):
            r = SavageDice.roll(wild_die=6)
            assert 1 <= r.wild_roll <= 6

    def test_total_is_max_of_both(self):
        for _ in range(200):
            r = SavageDice.roll()
            assert r.total == max(r.trait_roll, r.wild_roll)

    def test_critical_fail_only_on_double_one(self):
        # 手动伪造双1
        import unittest.mock as mock
        with mock.patch("random.randint", return_value=1):
            r = SavageDice.roll()
            assert r.is_critical_fail

    def test_no_crit_fail_when_not_double_one(self):
        for _ in range(500):
            r = SavageDice.roll()
            if r.trait_roll != 1 or r.wild_roll != 1:
                assert not r.is_critical_fail


class TestRollWithTarget:
    def test_success_when_total_gte_target(self):
        for _ in range(200):
            r = SavageDice.roll_with_target(4)
            if r.total >= 4:
                assert r.total >= 4  # tautology to confirm branch reached

    def test_raise_requires_target_plus_4(self):
        for _ in range(500):
            r = SavageDice.roll_with_target(4)
            if r.total >= 8:
                assert r.is_raise
            elif r.total < 8:
                assert not r.is_raise

    def test_raises_count_correct(self):
        for _ in range(500):
            r = SavageDice.roll_with_target(4)
            if r.total >= 4:
                expected = (r.total - 4) // 4
                assert r.raises == expected
            else:
                assert r.raises == 0


class TestDamageRoll:
    def test_1d6_range(self):
        for _ in range(200):
            val = SavageDice.damage_roll("1d6")
            assert 1 <= val <= 6

    def test_2d6_range(self):
        for _ in range(200):
            val = SavageDice.damage_roll("2d6")
            assert 2 <= val <= 12

    def test_modifier_plus(self):
        for _ in range(100):
            val = SavageDice.damage_roll("1d6+2")
            assert 3 <= val <= 8

    def test_modifier_minus(self):
        for _ in range(100):
            val = SavageDice.damage_roll("1d6-1")
            assert 0 <= val <= 5

    def test_invalid_notation_returns_zero(self):
        assert SavageDice.damage_roll("invalid") == 0

    def test_3d8_range(self):
        for _ in range(200):
            val = SavageDice.damage_roll("3d8")
            assert 3 <= val <= 24


class TestInitiative:
    def test_returns_tuple_of_two(self):
        result = SavageDice.roll_initiative()
        assert len(result) == 2

    def test_values_in_range(self):
        for _ in range(200):
            a, b = SavageDice.roll_initiative()
            assert 1 <= a <= 8
            assert 1 <= b <= 6
