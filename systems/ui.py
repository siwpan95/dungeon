"""UI 系统

负责绘制 HUD（状态栏）：
- 顶部：HP（Wounds）/ 护甲 / Bennies
- 右侧：日志面板
- 底部：技能快捷栏
- 中央：弹出消息
"""

import pygame
from typing import List, Optional
from core.player import PlayerState, Attribute


class UI:
    """游戏 UI 系统"""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.width, self.height = screen.get_size()
        self.font: Optional[pygame.font.Font] = None
        self.small_font: Optional[pygame.font.Font] = None
        self.logs: List[str] = []
        self.max_logs = 8
        self.popup_msg: Optional[str] = None
        self.popup_timer: int = 0
        self._init_font()

    def _init_font(self):
        """跨平台加载 CJK 字体"""
        from shared.font_utils import load_cjk_fonts
        self.font, self.small_font = load_cjk_fonts(16, 12)

    def add_log(self, message: str):
        """添加日志条目"""
        self.logs.append(message)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

    def show_popup(self, message: str, duration: int = 90):
        """显示中央弹出消息（帧数）"""
        self.popup_msg = message
        self.popup_timer = duration

    def draw_hud(self, player: PlayerState):
        """绘制 HUD"""
        self._draw_status_bar(player)
        self._draw_log_panel()
        self._draw_benny_display(player)
        self._draw_popup()

    def _draw_status_bar(self, player: PlayerState):
        """顶栏：Wounds / 护甲 / 状态"""
        bar_h = 36
        bar = pygame.Surface((self.width, bar_h), pygame.SRCALPHA)
        bar.fill((20, 20, 30, 220))

        # Wounds（创伤）
        wound_text = "创伤: "
        wound_surf = self.font.render(wound_text, True, (200, 200, 200))
        bar.blit(wound_surf, (10, 8))

        for i in range(player.max_wounds + 1):
            cx = 70 + i * 22
            color = (80, 200, 80) if i >= player.wounds else (220, 50, 50)
            pygame.draw.circle(bar, color, (cx, 18), 8)
            pygame.draw.circle(bar, (150, 150, 150), (cx, 18), 8, 1)

        # 疲劳
        fatigue_text = f"  疲劳: {'▣' * player.fatigue}{'▢' * (3 - player.fatigue)}"
        ft_surf = self.small_font.render(fatigue_text, True, (200, 180, 100))
        bar.blit(ft_surf, (70 + (player.max_wounds + 1) * 22, 10))

        # 护甲
        armor_text = f"  护甲 [身:{player.armor.get('torso',0)} 头:{player.armor.get('head',0)}]"
        ar_surf = self.small_font.render(armor_text, True, (100, 180, 200))
        bar.blit(ar_surf, (70 + (player.max_wounds + 1) * 22 + 120, 10))

        # 状态
        status_parts = []
        if player.is_shaken:
            status_parts.append("😵惊吓")
        if player.is_incapacitated:
            status_parts.append("🤕失能")
        if status_parts:
            st_surf = self.small_font.render(" | ".join(status_parts), True, (220, 180, 60))
            bar.blit(st_surf, (self.width - 200, 10))

        self.screen.blit(bar, (0, 0))

    def _draw_benny_display(self, player: PlayerState):
        """Bennies 显示（右上角）"""
        bx = self.width - 160
        by = 42
        label = self.font.render("Bennies:", True, (220, 200, 60))
        self.screen.blit(label, (bx, by))

        for i in range(player.bennies.max_bennies):
            color = (220, 200, 60) if i < player.bennies.current else (60, 55, 40)
            pygame.draw.circle(self.screen, color, (bx + 90 + i * 22, by + 8), 7)
            pygame.draw.circle(self.screen, (150, 140, 50), (bx + 90 + i * 22, by + 8), 7, 1)

    def _draw_log_panel(self):
        """右侧日志面板"""
        log_w = 280
        log_x = self.width - log_w
        log_y = 80
        log_h = 200

        panel = pygame.Surface((log_w, log_h), pygame.SRCALPHA)
        panel.fill((15, 15, 20, 180))

        for i, msg in enumerate(self.logs):
            color = (180, 180, 180)
            if "💀" in msg or "致命" in msg:
                color = (220, 60, 60)
            elif "成功" in msg or "恢复" in msg:
                color = (80, 200, 80)
            elif "伤害" in msg or "触发" in msg:
                color = (220, 160, 60)

            # 截断过长消息
            display_msg = msg[:36] + "…" if len(msg) > 38 else msg
            surf = self.small_font.render(display_msg, True, color)
            panel.blit(surf, (8, 6 + i * 20))

        self.screen.blit(panel, (log_x, log_y))

    def _draw_popup(self):
        """中央弹出消息"""
        if self.popup_msg and self.popup_timer > 0:
            self.popup_timer -= 1
            alpha = min(255, self.popup_timer * 4)
            surf = self.font.render(self.popup_msg, True, (255, 255, 200))
            surf.set_alpha(alpha)
            rect = surf.get_rect(center=(self.width // 2, self.height // 2 - 60))
            self.screen.blit(surf, rect)

    def draw_help_overlay(self):
        """绘制操作说明（首次提示）"""
        help_texts = [
            "左键：探索（揭开格子）",
            "右键：插旗（标记陷阱/怪物）",
            "中键/空格：感知检定",
            "WASD/方向键：移动",
            "B：Benny 重掷 / Soak",
            "H：切换帮助",
            "TAB：打开背包",
        ]
        panel = pygame.Surface((260, 180), pygame.SRCALPHA)
        panel.fill((10, 10, 20, 200))

        for i, txt in enumerate(help_texts):
            surf = self.small_font.render(txt, True, (180, 180, 200))
            panel.blit(surf, (10, 10 + i * 22))

        self.screen.blit(panel, (10, self.height - 190))
