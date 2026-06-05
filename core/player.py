"""玩家角色模块

实现 Savage Worlds 规则的角色属性系统：
- 五大属性：敏捷(Agility)、灵巧(Smarts)、活力(Spirit)、力量(Strength)、体质(Vigor)
- 派生属性：步伐(Pace)、生命值(Wounds)、疲劳(Fatigue)
- Bennies（命运点）：用于重掷、免死、解除状态
- 状态效果：眩晕(Shaken)、丧失行动(Incapacitated)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json


class Attribute(Enum):
    AGILITY = "agility"
    SMARTS = "smarts"
    SPIRIT = "spirit"
    STRENGTH = "strength"
    VIGOR = "vigor"


class WoundState(Enum):
    NORMAL = "normal"
    SHAKEN = "shaken"
    WOUNDED = "wounded"
    INCAPACITATED = "incapacitated"
    DEAD = "dead"


@dataclass
class Skill:
    name: str
    attribute: Attribute
    rank: int = 0
    is_core: bool = False


@dataclass
class Bennies:
    max_bennies: int = 3
    current: int = 3
    used_this_turn: int = 0

    def use(self) -> bool:
        if self.current > 0:
            self.current -= 1
            self.used_this_turn += 1
            return True
        return False

    def restore(self, amount: int = 1):
        self.current = min(self.max_bennies, self.current + amount)

    def reset_turn(self):
        self.used_this_turn = 0


@dataclass
class PlayerState:
    attributes: Dict[Attribute, int] = field(default_factory=lambda: {
        Attribute.AGILITY: 6,
        Attribute.SMARTS: 4,
        Attribute.SPIRIT: 6,
        Attribute.STRENGTH: 6,
        Attribute.VIGOR: 8,
    })

    skills: Dict[str, Skill] = field(default_factory=dict)
    wounds: int = 0
    fatigue: int = 0
    is_shaken: bool = False
    bennies: Bennies = field(default_factory=Bennies)
    max_wounds: int = 3
    armor: Dict[str, int] = field(default_factory=lambda: {
        "head": 0, "torso": 0, "arms": 0, "legs": 0
    })
    inventory: List[Dict] = field(default_factory=list)
    active_effects: List[str] = field(default_factory=list)
    position: Tuple[int, int] = (0, 0)
    facing: int = 0
    is_alive: bool = True
    is_incapacitated: bool = False

    def get_attribute_die(self, attr: Attribute) -> int:
        return self.attributes.get(attr, 4)

    def get_skill_die(self, skill_name: str) -> Optional[int]:
        skill = self.skills.get(skill_name)
        if not skill:
            return None
        attr_die = self.get_attribute_die(skill.attribute)
        skill_die = [0, 4, 6, 8, 10, 12][skill.rank]
        return max(attr_die, skill_die)

    def take_damage(self, damage: int, hit_location: str = "torso") -> Tuple[bool, str]:
        armor_reduction = self.armor.get(hit_location, 0)
        actual_damage = max(1, damage - armor_reduction)
        new_wounds = (actual_damage + 3) // 4
        self.wounds = min(self.max_wounds + 1, self.wounds + new_wounds)

        if self.wounds > self.max_wounds:
            self.is_alive = False
            return True, f"致命伤害！受到 {actual_damage} 点伤害，新增 {new_wounds} 个创伤"
        elif self.wounds == self.max_wounds:
            self.is_incapacitated = True
            return False, f"丧失行动能力！受到 {actual_damage} 点伤害，新增 {new_wounds} 个创伤"
        else:
            self.is_shaken = True
            return False, f"惊吓状态！受到 {actual_damage} 点伤害，新增 {new_wounds} 个创伤"

    def use_benny(self, reason: str = "") -> bool:
        return self.bennies.use()

    def soak_roll(self) -> bool:
        if not self.use_benny("soak"):
            return False
        from core.savage_dice import SavageDice
        result = SavageDice.roll_with_target(4)
        if result.total >= 4:
            self.wounds = max(0, self.wounds - 1)
            return True
        return False

    def to_dict(self) -> Dict:
        return {
            "attributes": {k.value: v for k, v in self.attributes.items()},
            "skills": {k: {"name": v.name, "rank": v.rank, "attribute": v.attribute.value}
                       for k, v in self.skills.items()},
            "wounds": self.wounds,
            "fatigue": self.fatigue,
            "is_shaken": self.is_shaken,
            "bennies": self.bennies.current,
            "max_wounds": self.max_wounds,
            "armor": self.armor,
            "inventory": self.inventory,
            "position": list(self.position),
            "facing": self.facing,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PlayerState':
        state = cls()
        attr_map = {e.value: e for e in Attribute}
        state.attributes = {
            attr_map[k]: v for k, v in data.get("attributes", {}).items()
        }
        skill_map = {e.value: e for e in Attribute}
        state.skills = {}
        for k, v in data.get("skills", {}).items():
            attr = skill_map.get(v["attribute"], Attribute.AGILITY)
            state.skills[k] = Skill(name=v["name"], rank=v["rank"], attribute=attr)
        state.wounds = data.get("wounds", 0)
        state.fatigue = data.get("fatigue", 0)
        state.is_shaken = data.get("is_shaken", False)
        state.bennies = Bennies(current=data.get("bennies", 3))
        state.max_wounds = data.get("max_wounds", 3)
        state.armor = data.get("armor", {"head": 0, "torso": 0, "arms": 0, "legs": 0})
        state.inventory = data.get("inventory", [])
        pos = data.get("position", [0, 0])
        state.position = (pos[0], pos[1])
        state.facing = data.get("facing", 0)
        state.is_alive = state.wounds <= state.max_wounds
        state.is_incapacitated = state.wounds == state.max_wounds
        return state


def create_default_player() -> PlayerState:
    player = PlayerState()
    player.skills["athletics"] = Skill("运动", Attribute.AGILITY, 1)
    player.skills["notice"] = Skill("感知", Attribute.SMARTS, 1)
    player.skills["stealth"] = Skill("潜行", Attribute.AGILITY, 1)
    player.skills["fighting"] = Skill("格斗", Attribute.AGILITY, 1)
    player.skills["shooting"] = Skill("射击", Attribute.AGILITY, 0)

    player.inventory = [
        {"name": "短剑", "type": "weapon", "damage": "1d6", "weight": 2},
        {"name": "皮甲", "type": "armor", "protection": 1, "location": "torso"},
        {"name": "治疗药水", "type": "consumable", "effect": "heal_1_wound"},
    ]
    player.armor["torso"] = 1
    return player
