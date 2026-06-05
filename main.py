"""Savage Dungeon — 主入口"""

import pygame
import sys
import os
import json
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.savage_dice import SavageDice
from core.player import create_default_player, PlayerState
from core.combat import CombatSystem
from core.map_system import MapSystem, TileType
from systems.renderer import Renderer
from systems.ui import UI
from systems.sound import SoundManager
from shared.font_utils import load_cjk_font


class GameState:
    PLAYING = "playing"
    DEAD = "dead"
    INVENTORY = "inventory"
    BENNY_REROLL = "benny_reroll"
    LOAD_PROMPT = "load_prompt"


# P2：用 dataclass 替代模块级 _reroll_ctx 字典
@dataclass
class BennyRerollContext:
    player: object = None
    tile: object = None
    combat: object = None
    ui: object = None
    sound: object = None
    detail: str = ""
    dc: int = 0

    def clear(self):
        self.player = None
        self.tile = None
        self.combat = None
        self.ui = None
        self.sound = None
        self.detail = ""
        self.dc = 0

    @property
    def active(self) -> bool:
        return self.player is not None and self.tile is not None


SCREEN_W, SCREEN_H = 960, 640
FPS = 60
SAVE_PATH = os.path.join(os.path.dirname(__file__), "save.json")


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Savage Dungeon — 扫雷地牢")

    clock = pygame.time.Clock()
    font = _load_font(14)

    # P2：reroll 上下文作为局部变量，不再使用模块级字典
    reroll_ctx = BennyRerollContext()

    # --- 存档读档入口 ---
    loaded_player, loaded_map = _load_game()
    if loaded_player and loaded_map:
        state = _show_load_prompt(screen, font)
        if state:
            player = loaded_player
            map_sys = loaded_map
            combat = CombatSystem()
            renderer = Renderer(screen)
            ui = UI(screen)
            ui.add_log("—— 读档成功，继续冒险 ——")
            state = GameState.PLAYING
        else:
            loaded_player, loaded_map = None, None

    if not loaded_player or not loaded_map:
        map_sys = MapSystem(seed=42)
        player = create_default_player()
        combat = CombatSystem()
        renderer = Renderer(screen)
        ui = UI(screen)
        player.position = (8, 8)
        map_sys.move_player(player.position[0], player.position[1])
        _ensure_safe_spawn(player, map_sys)
        state = GameState.PLAYING

    sound = SoundManager()

    running = True
    show_help = True

    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if state == GameState.DEAD:
                    if event.key == pygame.K_r:
                        player = create_default_player()
                        player.position = (8, 8)
                        # P6：不再调用 map_sys.__init__()，改为重新赋值
                        map_sys = MapSystem(seed=42)
                        map_sys.move_player(8, 8)
                        _ensure_safe_spawn(player, map_sys)
                        reroll_ctx.clear()
                        state = GameState.PLAYING
                        ui.logs.clear()
                        ui.add_log("—— 新的冒险开始 ——")
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    continue

                if state == GameState.BENNY_REROLL:
                    if event.key == pygame.K_y:
                        _do_benny_reroll(reroll_ctx)
                        dead, msg = combat.check_death(player)
                        if dead:
                            ui.add_log(msg)
                            sound.play_death()
                            state = GameState.DEAD
                        else:
                            state = GameState.PLAYING
                    elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                        ui.add_log("[Benny] 选择接受结果，不重掷。")
                        sound.play_damage()
                        reroll_ctx.clear()
                        state = GameState.PLAYING
                    continue

                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_h:
                    show_help = not show_help
                elif event.key == pygame.K_TAB:
                    if state == GameState.INVENTORY:
                        state = GameState.PLAYING
                        sound.play_menu_close()
                    else:
                        state = GameState.INVENTORY
                        sound.play_menu_open()
                elif event.key == pygame.K_SPACE:
                    _do_perception(player, map_sys, ui, combat)
                    sound.play_perception()
                elif event.key == pygame.K_b:
                    _do_use_benny(player, ui, combat)
                    sound.play_benny_use()
                elif event.key in (pygame.K_w, pygame.K_UP):
                    _move_player(player, map_sys, ui, combat, sound, 0, -1)
                elif event.key in (pygame.K_s, pygame.K_DOWN):
                    _move_player(player, map_sys, ui, combat, sound, 0, 1)
                elif event.key in (pygame.K_a, pygame.K_LEFT):
                    _move_player(player, map_sys, ui, combat, sound, -1, 0)
                elif event.key in (pygame.K_d, pygame.K_RIGHT):
                    _move_player(player, map_sys, ui, combat, sound, 1, 0)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 非 PLAYING 状态下禁止鼠标交互
                if state not in (GameState.PLAYING, GameState.INVENTORY):
                    continue

                mx, my = event.pos
                wx, wy = renderer.screen_to_world(
                    mx, my, player.position[0], player.position[1])

                if event.button == 1:
                    result = _do_explore(player, map_sys, ui, combat, sound,
                                         wx, wy, reroll_ctx)
                    if result == GameState.DEAD:
                        state = GameState.DEAD
                    elif result == GameState.BENNY_REROLL:
                        state = GameState.BENNY_REROLL
                elif event.button == 3:
                    map_sys.flag_tile(wx, wy)
                    tile = map_sys.get_tile(wx, wy)
                    if tile:
                        action = "标记" if tile.flagged else "取消标记"
                        ui.add_log(f"{action} ({wx}, {wy})")
                        sound.play_flag()
                elif event.button == 2:
                    _do_perception(player, map_sys, ui, combat)
                    sound.play_perception()

        renderer.draw_map(map_sys, player)
        ui.draw_hud(player)

        if show_help:
            ui.draw_help_overlay()

        if state == GameState.DEAD:
            _draw_death_screen(screen, font)

        if state == GameState.BENNY_REROLL:
            _draw_reroll_prompt(screen, font, reroll_ctx)

        if state == GameState.INVENTORY:
            _draw_inventory_screen(screen, font, player)

        pygame.display.flip()

    _save_game(player, map_sys)
    pygame.quit()
    sys.exit()


def _ensure_safe_spawn(player, map_sys):
    """确保玩家出生在安全的地板格上（无威胁）"""
    px, py = player.position
    tile = map_sys.get_tile(px, py)

    if tile and tile.type == TileType.FLOOR and tile.threat == 0:
        return  # 已经安全

    for radius in range(1, 6):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) != radius and abs(dy) != radius:
                    continue
                sx, sy = px + dx, py + dy
                st = map_sys.get_tile(sx, sy)
                if st and st.type == TileType.FLOOR and st.threat == 0:
                    player.position = (sx, sy)
                    map_sys.move_player(sx, sy)
                    return

    if tile:
        tile.reveal()


def _load_font(size: int):
    """跨平台加载 CJK 字体（内部含文件路径 / SysFont / 默认三级回退）"""
    return load_cjk_font(size)


def _move_player(player, map_sys, ui, combat, sound, dx, dy):
    nx = player.position[0] + dx
    ny = player.position[1] + dy
    tile = map_sys.get_tile(nx, ny)
    if tile is None or tile.type == TileType.WALL:
        ui.add_log("前方是墙壁，无法通过。")
        sound.play_wall_bump()
        return None
    if not tile.revealed:
        ui.add_log("前方区域尚未揭开，请用鼠标左键探索。")
        sound.play_blocked()
        return None

    player.position = (nx, ny)
    map_sys.move_player(nx, ny)
    sound.play_step()
    return None


def _do_explore(player, map_sys, ui, combat, sound, wx, wy,
                reroll_ctx: BennyRerollContext, auto=False):
    tile = map_sys.get_tile(wx, wy)
    if not tile:
        ui.add_log("无效位置。")
        return None
    if tile.revealed:
        ui.add_log("该格子已探索过。")
        return None
    if tile.flagged and not auto:
        ui.add_log("已插旗，先取消标记才能探索。")
        return None

    tile.reveal()
    ui.add_log(f"揭开 ({wx}, {wy}) — 类型：{tile.type.value}，威胁：{tile.threat}")

    if tile.threat == 0:
        ui.add_log("[success] 安全区域，未发现威胁。")
        sound.play_explore(threat=0)
        return None

    sound.play_explore(threat=tile.threat)

    # 预检掷骰（不造成伤害）
    success, detail, dc = combat.pretest_exploration(player, tile)
    ui.add_log(f"  检定 DC={dc}：{detail}")

    if success:
        _handle_explore_success(player, tile, ui, combat, sound)
        return None

    # 失败：有 Bennies 则提示重掷
    if player.bennies.current > 0:
        reroll_ctx.player = player
        reroll_ctx.tile = tile
        reroll_ctx.combat = combat
        reroll_ctx.ui = ui
        reroll_ctx.sound = sound
        reroll_ctx.detail = detail
        reroll_ctx.dc = dc
        ui.add_log(f"[Benny] 检定失败！按 Y 消耗 1 个 Benny 重掷，按 N 接受结果。")
        return GameState.BENNY_REROLL

    # 无 Bennies：直接结算伤害
    _apply_explore_failure(player, tile, ui, combat, sound)
    dead, msg = combat.check_death(player)
    if dead:
        ui.add_log(msg)
        sound.play_death()
        return GameState.DEAD
    return None


def _handle_explore_success(player, tile, ui, combat, sound):
    """处理探索成功的奖励（不重复掷骰子）"""
    if tile.type == TileType.MONSTER:
        ui.add_log("[success] 命中！怪物被击败。")
        sound.play_monster_defeat()
        player.bennies.restore(1)
        sound.play_benny_restore()
        ui.add_log("[Benny] 击败怪物，恢复 1 个 Benny。")
    elif tile.type == TileType.TRAP:
        ui.add_log("[success] 成功避开陷阱！")
        sound.play_trap_dodge()
    else:
        ui.add_log("[success] 检定成功！")


def _apply_explore_failure(player, tile, ui, combat, sound=None):
    """对失败结果结算伤害"""
    log = combat.resolve_exploration(player, tile, action="explore")
    ui.add_log(f"[{log.result.value}] {log.message}")
    if log.roll_detail:
        ui.add_log(f"  详情：{log.roll_detail}")
    if sound:
        sound.play_damage()


def _do_benny_reroll(reroll_ctx: BennyRerollContext):
    """消耗 1 个 Benny 重新预检 + 结算"""
    if not reroll_ctx.active:
        return

    player = reroll_ctx.player
    tile = reroll_ctx.tile
    combat = reroll_ctx.combat
    ui = reroll_ctx.ui
    sound = reroll_ctx.sound

    player.bennies.use()
    sound.play_benny_use()
    ui.add_log(f"[Benny] 重掷！剩余 Benny：{player.bennies.current}")

    success, detail, dc = combat.pretest_exploration(player, tile)
    ui.add_log(f"  重掷 DC={dc}：{detail}")

    if success:
        _handle_explore_success(player, tile, ui, combat, sound)
    else:
        _apply_explore_failure(player, tile, ui, combat, sound)

    reroll_ctx.clear()


def _draw_reroll_prompt(screen, font, reroll_ctx: BennyRerollContext):
    """绘制 Benny 重掷提示（模态覆盖层）"""
    overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    benny_count = reroll_ctx.player.bennies.current if reroll_ctx.active else 0
    lines = [
        "检定失败！是否使用 Benny 重掷？",
        "",
        f"  当前 Benny：{benny_count}",
        f"  检定 DC={reroll_ctx.dc}，上次结果：{reroll_ctx.detail}",
        "",
        "按 Y — 消耗 1 个 Benny 重掷",
        "按 N / ESC — 接受失败结果",
    ]
    for i, line in enumerate(lines):
        color = (220, 200, 60) if i == 0 else (200, 200, 200)
        surf = font.render(line, True, color)
        rect = surf.get_rect(center=(screen.get_width() // 2, 160 + i * 32))
        screen.blit(surf, rect)


def _do_perception(player, map_sys, ui, combat):
    """P3：感知检定不造成伤害，仅侦查周围8格"""
    wx, wy = player.position
    found = 0
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx == 0 and dy == 0:
                continue
            tx, ty = wx + dx, wy + dy
            tile = map_sys.get_tile(tx, ty)
            if tile and not tile.revealed:
                # 仅预检，不结算伤害
                success, detail, dc = combat.pretest_exploration(player, tile)
                if success and dc > 0:
                    ui.add_log(f"[感知] ({tx},{ty}) 侦查到威胁！类型：{tile.type.value} DC={dc}")
                    found += 1
                elif dc == 0:
                    ui.add_log(f"[感知] ({tx},{ty}) 安全区域")
                    found += 1
    if found == 0:
        ui.add_log("[感知] 周围未发现未揭示格。")


def _do_use_benny(player, ui, combat):
    """B 键：手动使用 Benny（Soak 治疗创伤）"""
    if player.bennies.current <= 0:
        ui.add_log("没有可用的 Bennies！")
        return
    if player.wounds > 0:
        ok, msg = combat.try_soak(player)
        ui.add_log(f"[Benny Soak] {msg}")
    else:
        ui.add_log("[Benny] 当前没有创伤，无需 Soak。检定失败时系统会自动提示重掷。")


def _draw_death_screen(screen, font):
    overlay = pygame.Surface((screen.get_width(), screen.get_height()), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    lines = ["你的旅程在此终结", "", "按 R 重新开始", "按 ESC 退出"]
    for i, line in enumerate(lines):
        color = (220, 60, 60) if i == 0 else (200, 200, 200)
        surf = font.render(line, True, color)
        rect = surf.get_rect(center=(screen.get_width() // 2, 200 + i * 36))
        screen.blit(surf, rect)


def _draw_inventory_screen(screen, font, player):
    panel = pygame.Surface((400, 300), pygame.SRCALPHA)
    panel.fill((15, 15, 25, 230))
    screen.blit(panel, (screen.get_width() // 2 - 200, 100))

    title = font.render("—— 背包 ——", True, (220, 200, 100))
    screen.blit(title, (screen.get_width() // 2 - title.get_width() // 2, 110))

    for i, item in enumerate(player.inventory):
        txt = f"{i+1}. {item['name']} [{item['type']}]"
        surf = font.render(txt, True, (180, 180, 200))
        screen.blit(surf, (screen.get_width() // 2 - 160, 150 + i * 24))


def _save_game(player, map_sys):
    """P1：存档同时保存 revealed/flagged 格子状态"""
    try:
        data = {
            "player": player.to_dict(),
            "map_seed": map_sys.seed,
            "tile_states": map_sys.get_tile_states(),
        }
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as _e:
        import sys
        print(f"[Save] 存档失败：{_e}", file=sys.stderr)


def _load_game():
    """P1：读档时恢复 revealed/flagged 格子状态"""
    if not os.path.exists(SAVE_PATH):
        return None, None
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        player = PlayerState.from_dict(data["player"])
        map_sys = MapSystem(seed=data["map_seed"])
        map_sys.move_player(player.position[0], player.position[1])
        # 恢复揭示/标记状态
        tile_states = data.get("tile_states", [])
        if tile_states:
            map_sys.restore_tile_states(tile_states)
        return player, map_sys
    except Exception as _e:
        import sys
        print(f"[Load] 读档失败：{_e}", file=sys.stderr)
        return None, None


def _show_load_prompt(screen, font) -> bool:
    """显示存档加载提示。返回 True=加载，False=新游戏"""
    SCREEN_W, SCREEN_H = screen.get_width(), screen.get_height()
    clock = pygame.time.Clock()

    while True:
        clock.tick(FPS)
        screen.fill((10, 10, 18))

        lines = [
            "发现存档，是否继续上次冒险？",
            "",
            "按 Y — 继续冒险",
            "按 N — 开始新游戏",
            "按 ESC — 退出",
        ]
        for i, line in enumerate(lines):
            color = (220, 200, 100) if i == 0 else (160, 160, 180)
            surf = font.render(line, True, color)
            rect = surf.get_rect(center=(SCREEN_W // 2, 180 + i * 40))
            screen.blit(surf, rect)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    return True
                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    return False


if __name__ == "__main__":
    main()
