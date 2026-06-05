"""pygame_ce 渲染器

负责将地图 Tile 和游戏状态渲染到屏幕：
- 地格绘制（颜色区分类型）
- 玩家角色渲染
- 视距（FOV）遮罩
- 中文字体支持
"""

import pygame
from typing import Dict, List, Optional, Tuple
from core.map_system import Tile, TileType, MapSystem
from core.player import PlayerState

CELL_SIZE = 32


class Renderer:
    TILE_COLORS = {
        TileType.WALL:        (60, 60, 70),
        TileType.FLOOR:        (45, 45, 50),
        TileType.DOOR:         (120, 80, 40),
        TileType.TRAP:         (140, 30, 30),
        TileType.MONSTER:      (160, 30, 30),
        TileType.LOOT:         (140, 120, 30),
        TileType.STAIRS_DOWN:  (40, 40, 120),
        TileType.STAIRS_UP:    (40, 120, 40),
        TileType.VOID:         (10, 10, 12),
    }

    THREAT_COLORS = {
        0: (100, 100, 100),
        1: (80, 140, 80),
        2: (140, 140, 60),
        3: (200, 140, 40),
        4: (200, 80, 40),
        5: (220, 40, 40),
    }

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.cell_size = CELL_SIZE
        self.font: Optional[pygame.font.Font] = None
        self.small_font: Optional[pygame.font.Font] = None
        self._init_font()

    def _init_font(self):
        """跨平台加载 CJK 字体"""
        from shared.font_utils import load_cjk_fonts
        self.font, self.small_font = load_cjk_fonts(14, 10)

    def world_to_screen(self, wx: int, wy: int,
                       player_x: int, player_y: int) -> Tuple[int, int]:
        cx = self.width // 2 // self.cell_size
        cy = self.height // 2 // self.cell_size
        sx = (cx + wx - player_x) * self.cell_size
        sy = (cy + wy - player_y) * self.cell_size
        return sx, sy

    def screen_to_world(self, sx: int, sy: int,
                       player_x: int, player_y: int) -> Tuple[int, int]:
        cx = self.width // 2 // self.cell_size
        cy = self.height // 2 // self.cell_size
        wx = (sx // self.cell_size) - cx + player_x
        wy = (sy // self.cell_size) - cy + player_y
        return wx, wy

    def draw_map(self, map_sys: MapSystem, player: PlayerState):
        self.screen.fill((10, 10, 12))
        visible_tiles = map_sys.get_visible_tiles(player.position[0], player.position[1])

        for tile in visible_tiles:
            sx, sy = self.world_to_screen(
                tile.x, tile.y, player.position[0], player.position[1])

            if sx + self.cell_size < 0 or sy + self.cell_size < 0 or \
               sx > self.width or sy > self.height:
                continue

            if not tile.revealed:
                color = self.TILE_COLORS[TileType.VOID]
                pygame.draw.rect(self.screen, color,
                                (sx, sy, self.cell_size, self.cell_size))
                pygame.draw.rect(self.screen, (25, 25, 30),
                                (sx, sy, self.cell_size, self.cell_size), 1)
                continue

            color = self.TILE_COLORS.get(tile.type, (45, 45, 50))
            pygame.draw.rect(self.screen, color,
                            (sx, sy, self.cell_size, self.cell_size))

            border_color = (70, 70, 80) if tile.type == TileType.FLOOR else (90, 90, 100)
            pygame.draw.rect(self.screen, border_color,
                            (sx, sy, self.cell_size, self.cell_size), 1)

            if tile.flagged:
                flag_sx = sx + self.cell_size // 2
                pygame.draw.polygon(self.screen, (220, 50, 50), [
                    (flag_sx, sy + 4),
                    (flag_sx + 8, sy + 8),
                    (flag_sx, sy + 12),
                ])
                pygame.draw.line(self.screen, (180, 180, 180),
                                (flag_sx, sy + 14), (flag_sx, sy + 28), 2)

            if tile.revealed and tile.threat > 0 and tile.type == TileType.FLOOR:
                t_color = self.THREAT_COLORS.get(tile.threat, (220, 40, 40))
                t_surf = self.font.render(str(tile.threat), True, t_color)
                t_rect = t_surf.get_rect(
                    center=(sx + self.cell_size // 2, sy + self.cell_size // 2))
                self.screen.blit(t_surf, t_rect)

            self._draw_tile_icon(tile, sx, sy)

        self._draw_player(player)
        self._draw_fog_of_war(player)

    def _draw_tile_icon(self, tile: Tile, sx: int, sy: int):
        cx = sx + self.cell_size // 2
        cy = sy + self.cell_size // 2

        if tile.type == TileType.MONSTER:
            pygame.draw.circle(self.screen, (180, 40, 40), (cx, cy), 5)
        elif tile.type == TileType.TRAP:
            pygame.draw.line(self.screen, (180, 120, 40),
                           (sx + 4, sy + 4),
                           (sx + self.cell_size - 4, sy + self.cell_size - 4), 2)
            pygame.draw.line(self.screen, (180, 120, 40),
                           (sx + self.cell_size - 4, sy + 4),
                           (sx + 4, sy + self.cell_size - 4), 2)
        elif tile.type == TileType.LOOT:
            pygame.draw.rect(self.screen, (180, 160, 40),
                           (cx - 4, cy - 4, 8, 8))
        elif tile.type == TileType.DOOR:
            pygame.draw.rect(self.screen, (140, 100, 50),
                           (sx + 4, sy + 4, self.cell_size - 8, self.cell_size - 8), 2)
        elif tile.type == TileType.STAIRS_DOWN:
            for i in range(3):
                y_off = sy + 8 + i * 7
                pygame.draw.line(self.screen, (80, 80, 180),
                               (sx + 6, y_off), (sx + self.cell_size - 6, y_off), 2)

    def _draw_player(self, player: PlayerState):
        sx, sy = self.world_to_screen(
            player.position[0], player.position[1],
            player.position[0], player.position[1])
        cx = sx + self.cell_size // 2
        cy = sy + self.cell_size // 2

        pygame.draw.circle(self.screen, (60, 180, 240), (cx, cy), 10)
        pygame.draw.circle(self.screen, (150, 220, 255), (cx, cy), 6)

        dirs = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        dx, dy = dirs[player.facing]
        ex = cx + dx * 12
        ey = cy + dy * 12
        pygame.draw.line(self.screen, (255, 255, 100), (cx, cy), (ex, ey), 2)

    def _draw_fog_of_war(self, player: PlayerState):
        fov_radius = 4 * self.cell_size
        cx = self.width // 2
        cy = self.height // 2

        fog = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        fog.fill((0, 0, 0, 160))

        fov_rect = pygame.Rect(
            cx - fov_radius, cy - fov_radius,
            fov_radius * 2, fov_radius * 2
        )
        pygame.draw.rect(fog, (0, 0, 0, 0), fov_rect)

        self.screen.blit(fog, (0, 0))

    def draw_debug_grid(self, player_x: int, player_y: int):
        for dx in range(-8, 9):
            for dy in range(-6, 7):
                wx, wy = player_x + dx, player_y + dy
                sx, sy = self.world_to_screen(wx, wy, player_x, player_y)
                coord_surf = self.small_font.render(
                    f"{wx},{wy}", True, (80, 80, 80))
                self.screen.blit(coord_surf, (sx + 1, sy + 1))
