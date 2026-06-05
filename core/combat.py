"""战斗与遭遇结算系统

实现 Savage Worlds 规则的战斗机制：
- 翻开威胁格子 → 触发战斗/陷阱检定
- 敏捷检定（Agility）避开陷阱
- 先攻（Initiative）决定行动顺序
- 伤害结算 + 重伤表
- 穿甲与部位伤害
- 眩晕(Shaken)与休克状态处理
"""

import random
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field

from core.savage_dice import SavageDice, DiceResult
from core.player import PlayerState, Attribute
from core.map_system import TileType


class EncounterResult(Enum):
    SUCCESS = "success"
    HIT = "hit"
    CRITICAL_HIT = "crit_hit"
    GRAZE = "graze"
    FUMBLE = "fumble"


@dataclass
class CombatLog:
    message: str
    result: EncounterResult
    damage: int = 0
    roll_detail: str = ""


class CombatSystem:
    THREAT_DC_MAP = {0: 0, 1: 4, 2: 6, 3: 8, 4: 10, 5: 12}

    HIT_LOCATION_WEIGHTS = {"head": 10, "torso": 40, "arms": 25, "legs": 25}

    @staticmethod
    def pretest_exploration(player: PlayerState, tile) -> Tuple[bool, str, int]:
        """预检掷骰（不造成伤害），返回 (成功, 检定详情, DC)"""
        if tile.threat == 0:
            return True, "安全", 0

        dc = tile.threat * 2

        if tile.type == TileType.TRAP:
            agi_die = player.get_attribute_die(Attribute.AGILITY)
            result = SavageDice.roll_with_target(dc, trait_die=agi_die)
            return result.total >= dc, str(result), dc

        if tile.type == TileType.MONSTER:
            init_result = SavageDice.roll_initiative()
            player_init = max(init_result[0], init_result[1])
            monster_init = random.randint(1, 8)
            if player_init < monster_init:
                return False, f"怪物先攻 [P:{player_init} vs M:{monster_init}]", dc
            fight_die = player.get_skill_die("fighting") or player.get_attribute_die(Attribute.AGILITY)
            result = SavageDice.roll_with_target(dc, trait_die=fight_die)
            return result.total >= dc, str(result), dc

        # 普通威胁
        result = SavageDice.roll_with_target(dc)
        return result.total >= dc, str(result), dc

    @staticmethod
    def resolve_exploration(player: PlayerState, tile,
                           action: str = "explore") -> CombatLog:
        if tile.threat == 0:
            return CombatLog("安全区域，未发现威胁。", EncounterResult.SUCCESS)

        dc = tile.threat * 2

        if action == "perception":
            skill_die = player.get_skill_die("notice") or player.get_attribute_die(Attribute.SMARTS)
            result = SavageDice.roll_with_target(dc, trait_die=skill_die)
            if result.total >= dc:
                return CombatLog(
                    f"侦查成功！发现威胁（{tile.type.value}），可以安全绕过。",
                    EncounterResult.SUCCESS, roll_detail=str(result))
            return CombatLog("侦查失败，未发现隐藏威胁…",
                            EncounterResult.HIT, roll_detail=str(result))

        if tile.type == TileType.TRAP:
            agi_die = player.get_attribute_die(Attribute.AGILITY)
            result = SavageDice.roll_with_target(dc, trait_die=agi_die)
            if result.total >= dc:
                return CombatLog(f"陷阱检定 DC={dc} {result} → 成功避开陷阱！",
                                EncounterResult.SUCCESS, roll_detail=str(result))
            damage = SavageDice.damage_roll("2d6")
            is_dead, dmg_msg = player.take_damage(damage, "torso")
            return CombatLog(
                f"陷阱检定 DC={dc} {result} → 触发陷阱！{dmg_msg}",
                EncounterResult.HIT, damage=damage, roll_detail=str(result))

        if tile.type == TileType.MONSTER:
            return CombatSystem._resolve_combat(player, tile, dc)

        # 普通威胁格子
        result = SavageDice.roll_with_target(dc)
        if result.total >= dc:
            return CombatLog(f"检定成功 DC={dc}：{result}",
                            EncounterResult.SUCCESS, roll_detail=str(result))
        damage = SavageDice.damage_roll("1d6")
        is_dead, dmg_msg = player.take_damage(damage, "torso")
        return CombatLog(f"检定失败 DC={dc}：{result} → {dmg_msg}",
                        EncounterResult.HIT, damage=damage, roll_detail=str(result))

    @staticmethod
    def _resolve_combat(player: PlayerState, tile, dc: int) -> CombatLog:
        init_result = SavageDice.roll_initiative()
        player_init = max(init_result[0], init_result[1])
        monster_init = random.randint(1, 8)

        logs = [f"遭遇 {tile.metadata.get('monster_id', '怪物')}！"]

        if player_init >= monster_init:
            fight_die = player.get_skill_die("fighting") or player.get_attribute_die(Attribute.AGILITY)
            attack_result = SavageDice.roll_with_target(dc, trait_die=fight_die)
            if attack_result.total >= dc:
                logs.append(f"攻击检定 {attack_result} → 命中！怪物被击败。")
                player.bennies.restore(1)
                return CombatLog(" ".join(logs), EncounterResult.SUCCESS,
                                roll_detail=str(attack_result))
            damage = SavageDice.damage_roll(tile.metadata.get("damage", "1d6"))
            hit_loc = CombatSystem._roll_hit_location()
            is_dead, dmg_msg = player.take_damage(damage, hit_loc)
            logs.append(f"攻击失败 {attack_result}，受到 {damage} 点伤害（{hit_loc}）。{dmg_msg}")
            return CombatLog(" ".join(logs), EncounterResult.HIT,
                            damage=damage, roll_detail=str(attack_result))
        else:
            damage = SavageDice.damage_roll(tile.metadata.get("damage", "1d6"))
            hit_loc = CombatSystem._roll_hit_location()
            is_dead, dmg_msg = player.take_damage(damage, hit_loc)
            logs.append(f"怪物先攻！受到 {damage} 点伤害（{hit_loc}）。{dmg_msg}")
            return CombatLog(" ".join(logs), EncounterResult.HIT, damage=damage)

    @staticmethod
    def _roll_hit_location() -> str:
        weights = CombatSystem.HIT_LOCATION_WEIGHTS
        locations = list(weights.keys())
        wvals = list(weights.values())
        return random.choices(locations, weights=wvals)[0]

    @staticmethod
    def try_soak(player: PlayerState) -> Tuple[bool, str]:
        if player.bennies.current < 1:
            return False, "没有足够的 Bennies 进行 Soak 检定！"
        vigor_die = player.get_attribute_die(Attribute.VIGOR)
        result = SavageDice.roll_with_target(4, trait_die=vigor_die)
        if result.total >= 4:
            player.wounds = max(0, player.wounds - 1)
            player.bennies.use()
            return True, f"Soak 成功！移除 1 个创伤。{result}"
        player.bennies.use()
        return False, f"Soak 失败… {result}"

    @staticmethod
    def use_consumable(player: PlayerState, item: Dict) -> str:
        effect = item.get("effect", "")
        if effect == "heal_1_wound":
            if player.wounds > 0:
                player.wounds -= 1
                player.is_incapacitated = player.wounds >= player.max_wounds
                return f"使用 {item['name']}，恢复 1 个创伤。"
            return "当前没有创伤需要治疗。"
        return f"使用了 {item['name']}。"

    @staticmethod
    def check_death(player: PlayerState) -> Tuple[bool, str]:
        if not player.is_alive:
            return True, "💀 你的旅程在此终结…（Roguelike 永久死亡）"
        if player.is_incapacitated:
            return False, "丧失行动能力！需要治疗物品或休息。"
        return False, ""

    @staticmethod
    def end_turn(player: PlayerState) -> str:
        player.bennies.reset_turn()
        if player.is_shaken:
            spirit_die = player.get_attribute_die(Attribute.SPIRIT)
            result = SavageDice.roll_with_target(4, trait_die=spirit_die)
            if result.total >= 4:
                player.is_shaken = False
                return f"精神检定成功，从惊吓中恢复。{result}"
            return f"仍在惊吓状态…{result}"
        return ""
