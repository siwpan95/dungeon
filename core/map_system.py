"""地图区块系统

实现模块化地牢地图：
- Chunk（区块）：16x16 格子的地图块
- 威胁分布：每个格子有 threat 值（0=安全，1~5=难度）
- FOV（视距）：只渲染玩家周围 9x9 区域
- 区块加载/卸载：玩家远离 >20 格时销毁旧区块释放内存
- 地格类型：wall（墙）、floor（地板）、door（门）、trap（陷阱）、monster（怪物）、loot（战利品）
"""

import random
import json
import math
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum


class TileType(Enum):
    WALL = "wall"
    FLOOR = "floor"
    DOOR = "door"
    TRAP = "trap"
    MONSTER = "monster"
    LOOT = "loot"
    STAIRS_DOWN = "stairs_down"
    STAIRS_UP = "stairs_up"
    VOID = "void"  # 未探索/不可见


class Tile:
    """单个地格"""

    # 地格显示颜色映射
    COLOR_MAP = {
        TileType.WALL: (60, 60, 60),
        TileType.FLOOR: (30, 30, 30),
        TileType.DOOR: (120, 80, 40),
        TileType.TRAP: (80, 20, 20),
        TileType.MONSTER: (100, 20, 20),
        TileType.LOOT: (80, 80, 20),
        TileType.STAIRS_DOWN: (40, 40, 100),
        TileType.STAIRS_UP: (40, 100, 40),
        TileType.VOID: (10, 10, 10),
    }

    def __init__(self, x: int, y: int, tile_type: TileType,
                 threat: int = 0, metadata: Optional[Dict] = None):
        self.x = x
        self.y = y
        self.type = tile_type
        self.threat = threat          # 威胁等级 0~5
        self.revealed = False         # 是否已被探索揭示
        self.flagged = False          # 是否被插旗（标记）
        self.metadata = metadata or {} # 额外数据（怪物ID、战利品表等）
        self.entities: List[Dict] = []  # 该格上的实体（怪物、物品）

    def reveal(self) -> bool:
        """揭示此格，返回是否首次揭示"""
        if self.revealed:
            return False
        self.revealed = True
        return True

    def toggle_flag(self):
        self.flagged = not self.flagged

    def get_color(self, fog_of_war: bool = True) -> Tuple[int, int, int]:
        if not self.revealed and fog_of_war:
            return self.COLOR_MAP[TileType.VOID]
        return self.COLOR_MAP.get(self.type, (30, 30, 30))

    def to_dict(self) -> Dict:
        return {
            "x": self.x, "y": self.y,
            "type": self.type.value,
            "threat": self.threat,
            "revealed": self.revealed,
            "flagged": self.flagged,
            "metadata": self.metadata,
            "entities": self.entities,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Tile':
        tile = cls(
            x=data["x"], y=data["y"],
            tile_type=TileType(data["type"]),
            threat=data.get("threat", 0),
            metadata=data.get("metadata", {}),
        )
        tile.revealed = data.get("revealed", False)
        tile.flagged = data.get("flagged", False)
        tile.entities = data.get("entities", [])
        return tile


@dataclass
class MapChunk:
    """16x16 地图区块"""
    CHUNK_SIZE = 16

    chunk_id: str
    world_x: int          # 区块在完整地图上的左上角世界坐标 X
    world_y: int          # 区块在完整地图上的左上角世界坐标 Y
    tiles: Dict[Tuple[int, int], Tile] = field(default_factory=dict)
    visited: bool = False  # 玩家是否曾进入此区块

    def get_key(self, x: int, y: int) -> Tuple[int, int]:
        return (x, y)

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        return self.tiles.get(self.get_key(x, y))

    def set_tile(self, tile: Tile):
        self.tiles[self.get_key(tile.x, tile.y)] = tile

    def is_loaded(self) -> bool:
        return len(self.tiles) > 0

    def unload(self):
        """卸载区块（释放内存）"""
        self.tiles.clear()

    def generate(self, seed: Optional[int] = None):
        """生成区块内容（程序生成）"""
        rng = random.Random(seed if seed else random.randint(0, 999999))
        mid = self.CHUNK_SIZE // 2

        for lx in range(self.CHUNK_SIZE):
            for ly in range(self.CHUNK_SIZE):
                wx = self.world_x + lx
                wy = self.world_y + ly

                # 简单洞穴生成：边缘为墙，内部有概率通路
                dist_to_center = math.sqrt((lx - mid)**2 + (ly - mid)**2)
                if lx == 0 or ly == 0 or lx == self.CHUNK_SIZE - 1 or ly == self.CHUNK_SIZE - 1:
                    tile_type = TileType.WALL
                    threat = 0
                elif dist_to_center > mid * 0.8 and rng.random() < 0.3:
                    tile_type = TileType.WALL
                    threat = 0
                else:
                    # 地板上的威胁分布
                    r = rng.random()
                    if r < 0.55:
                        tile_type = TileType.FLOOR
                        threat = 0
                    elif r < 0.70:
                        tile_type = TileType.FLOOR
                        threat = rng.randint(2, 4)
                    elif r < 0.82:
                        tile_type = TileType.TRAP
                        threat = rng.randint(3, 5)
                    elif r < 0.93:
                        tile_type = TileType.MONSTER
                        threat = rng.randint(3, 6)
                        tile = Tile(wx, wy, tile_type, threat, {
                            "monster_id": rng.choice(["rat", "skeleton", "goblin"]),
                            "damage": "1d6",
                        })
                        self.set_tile(tile)
                        continue
                    else:
                        tile_type = TileType.LOOT
                        threat = 0

                    tile = Tile(wx, wy, tile_type, threat)
                    self.set_tile(tile)
                    continue

                tile = Tile(wx, wy, tile_type, threat)
                self.set_tile(tile)

    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "world_x": self.world_x,
            "world_y": self.world_y,
            "visited": self.visited,
            "tiles": [t.to_dict() for t in self.tiles.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'MapChunk':
        chunk = cls(
            chunk_id=data["chunk_id"],
            world_x=data["world_x"],
            world_y=data["world_y"],
        )
        chunk.visited = data.get("visited", False)
        for tdata in data.get("tiles", []):
            tile = Tile.from_dict(tdata)
            chunk.set_tile(tile)
        return chunk


class MapSystem:
    """地牢地图管理系统（区块加载/卸载 + FOV）"""

    FOV_RADIUS = 4        # 9x9 视距半径（中心 + 4格）
    UNLOAD_DIST = 20        # 超过此距离卸载区块
    CHUNK_SIZE = 16

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed if seed else random.randint(0, 999999)
        self.chunks: Dict[str, MapChunk] = {}
        self.player_chunk_key: Optional[str] = None
        self.revealed_tiles: Set[Tuple[int, int]] = set()

    def _chunk_key(self, cx: int, cy: int) -> str:
        return f"chunk_{cx}_{cy}"

    def _world_to_chunk(self, wx: int, wy: int) -> Tuple[int, int]:
        """世界坐标 → 区块坐标"""
        return (wx // self.CHUNK_SIZE, wy // self.CHUNK_SIZE)

    def _get_or_load_chunk(self, cx: int, cy: int) -> MapChunk:
        """获取区块，不存在则生成"""
        key = self._chunk_key(cx, cy)
        if key not in self.chunks:
            chunk = MapChunk(
                chunk_id=key,
                world_x=cx * self.CHUNK_SIZE,
                world_y=cy * self.CHUNK_SIZE,
            )
            chunk.generate(seed=self.seed + cx * 1000 + cy)
            self.chunks[key] = chunk
        return self.chunks[key]

    def move_player(self, px: int, py: int) -> List[str]:
        """玩家移动到 (px, py)，返回被卸载的区块 key 列表"""
        old_chunk_key = self.player_chunk_key
        ccx, ccy = self._world_to_chunk(px, py)
        new_key = self._chunk_key(ccx, ccy)

        # 加载当前区块及相邻区块
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                self._get_or_load_chunk(ccx + dx, ccy + dy)

        self.player_chunk_key = new_key

        # 卸载远离的区块（不再自动揭示 FOV，由渲染器/探索动作揭示）
        unloaded = self._unload_distant(px, py)
        return unloaded

    def _unload_distant(self, px: int, py: int) -> List[str]:
        """卸载距离玩家超过 UNLOAD_DIST 的区块"""
        unloaded = []
        to_remove = []
        for key, chunk in self.chunks.items():
            dist = abs(chunk.world_x - px) + abs(chunk.world_y - py)
            if dist > self.UNLOAD_DIST:
                chunk.unload()
                to_remove.append(key)
                unloaded.append(key)

        for key in to_remove:
            del self.chunks[key]

        return unloaded

    def get_tile(self, wx: int, wy: int) -> Optional[Tile]:
        """获取世界坐标对应的 Tile（自动懒加载 chunk）"""
        ccx, ccy = self._world_to_chunk(wx, wy)
        chunk = self._get_or_load_chunk(ccx, ccy)
        return chunk.get_tile(wx, wy)

    def reveal_tile(self, wx: int, wy: int) -> Optional[Tile]:
        """揭示指定格子，返回该 Tile（用于点击探索）"""
        tile = self.get_tile(wx, wy)
        if tile:
            tile.reveal()
            self.revealed_tiles.add((wx, wy))
        return tile

    def flag_tile(self, wx: int, wy: int) -> bool:
        """插旗/取消插旗，返回操作后状态"""
        tile = self.get_tile(wx, wy)
        if tile:
            tile.toggle_flag()
            return tile.flagged
        return False

    def get_visible_tiles(self, px: int, py: int) -> List[Tile]:
        """获取玩家当前可见的所有 Tile"""
        visible = []
        for dx in range(-self.FOV_RADIUS, self.FOV_RADIUS + 1):
            for dy in range(-self.FOV_RADIUS, self.FOV_RADIUS + 1):
                tx, ty = px + dx, py + dy
                if abs(dx) + abs(dy) <= self.FOV_RADIUS * 2:
                    tile = self.get_tile(tx, ty)
                    if tile:
                        visible.append(tile)
        return visible

    def get_tile_states(self) -> List[Dict]:
        """导出所有已修改的格子状态（revealed/flagged），用于存档"""
        states = []
        for chunk in self.chunks.values():
            for tile in chunk.tiles.values():
                if tile.revealed or tile.flagged:
                    states.append({
                        "x": tile.x, "y": tile.y,
                        "revealed": tile.revealed,
                        "flagged": tile.flagged,
                    })
        return states

    def restore_tile_states(self, states: List[Dict]):
        """从存档恢复格子的 revealed/flagged 状态"""
        for s in states:
            tile = self.get_tile(s["x"], s["y"])
            if tile:
                tile.revealed = s.get("revealed", False)
                tile.flagged = s.get("flagged", False)
                if tile.revealed:
                    self.revealed_tiles.add((tile.x, tile.y))

    def save_chunks(self, filepath: str):
        """保存已访问的区块到文件"""
        data = {
            "seed": self.seed,
            "chunks": [c.to_dict() for c in self.chunks.values() if c.visited],
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_chunks(self, filepath: str):
        """从文件加载区块"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.seed = data.get("seed", self.seed)
        for cdata in data.get("chunks", []):
            chunk = MapChunk.from_dict(cdata)
            self.chunks[chunk.chunk_id] = chunk
