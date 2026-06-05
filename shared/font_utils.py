# -*- coding: utf-8 -*-
"""
跨平台字体加载工具

优先通过字体文件路径加载 CJK 字体（最可靠），
其次尝试 SysFont，最后回退到 pygame 默认字体。

用法:
    from shared.font_utils import load_font, load_cjk_font

    font = load_cjk_font(16)      # 支持中文的字体
    font = load_cjk_font(16, bold=True)
    font = load_font(14)          # 仅英文，等宽优先

也可一次加载多个字号:
    f_lg, f_md, f_sm = load_cjk_fonts(24, 16, 12)
"""

import os
import sys
import platform
from typing import Optional, Tuple

import pygame


# ── 各平台 CJK 字体文件路径（按优先级排列） ──
_CJK_FONT_PATHS = {
    "Windows": [
        ("msyh.ttc", "Microsoft YaHei"),
        ("msyh.ttf", "Microsoft YaHei"),
        ("simhei.ttf", "SimHei"),
        ("simsun.ttc", "SimSun"),
    ],
    "Darwin": [  # macOS
        ("/System/Library/Fonts/PingFang.ttc", "PingFang SC"),
        ("/System/Library/Fonts/STHeiti Medium.ttc", "STHeiti"),
        ("/System/Library/Fonts/Hiragino Sans GB.ttc", "Hiragino Sans GB"),
    ],
    "Linux": [
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "Noto Sans CJK"),
        ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "WenQuanYi Micro Hei"),
        ("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf", "Droid Sans Fallback"),
    ],
}

# ── SysFont 名称回退链 ──
_CJK_SYSFONT_NAMES = [
    "microsoftyahei", "Microsoft YaHei",
    "simhei", "SimHei",
    "pingfang sc", "PingFang SC",
    "notosanscjk", "Noto Sans CJK",
    "wenquanyi micro hei", "WenQuanYi Micro Hei",
]

_MONO_SYSFONT_NAMES = [
    "consolas", "Consolas",
    "courier new", "Courier New",
    "dejavu sans mono", "DejaVu Sans Mono",
    "menlo", "Menlo",
    "monaco", "Monaco",
]


def _get_system_fonts_dir() -> str:
    """获取系统字体目录"""
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "Fonts")
    elif system == "Darwin":
        return "/System/Library/Fonts"
    elif system == "Linux":
        return "/usr/share/fonts"
    return ""


def _try_load_font_file(
    filename: str, size: int,
) -> Optional[pygame.font.Font]:
    """尝试从字体文件路径加载字体"""
    # 先在当前平台字体目录中查找
    fonts_dir = _get_system_fonts_dir()
    if fonts_dir:
        filepath = os.path.join(fonts_dir, filename)
        if os.path.isfile(filepath):
            try:
                return pygame.font.Font(filepath, size)
            except Exception:
                pass

    # 再尝试作为绝对/相对路径直接打开
    if os.path.isfile(filename):
        try:
            return pygame.font.Font(filename, size)
        except Exception:
            pass

    return None


def _try_sysfont(
    names: list[str], size: int, bold: bool = False, italic: bool = False
) -> Optional[pygame.font.Font]:
    """按优先级尝试 SysFont"""
    for name in names:
        try:
            font = pygame.font.SysFont(name, size, bold=bold, italic=italic)
            if font and _has_cjk(font):
                return font
        except Exception:
            continue
    return None


def _has_cjk(font: pygame.font.Font) -> bool:
    """验证字体是否支持中文（渲染"中"字，宽度应大于两个空格的一半）"""
    try:
        cjk_w = font.render("中文", True, (0, 0, 0)).get_width()
        spc_w = font.render("    ", True, (0, 0, 0)).get_width()
        return cjk_w > spc_w // 2
    except Exception:
        return False


def _load_by_platform_paths(size: int) -> Optional[pygame.font.Font]:
    """根据当前平台从已知字体文件路径加载"""
    system = platform.system()
    paths = _CJK_FONT_PATHS.get(system, [])
    for filename, _name in paths:
        font = _try_load_font_file(filename, size)
        if font and _has_cjk(font):
            return font
    # 也尝试其他平台的路径（兼容交叉编译等场景）
    for plat, plat_paths in _CJK_FONT_PATHS.items():
        if plat == system:
            continue
        for filename, _name in plat_paths:
            font = _try_load_font_file(filename, size)
            if font and _has_cjk(font):
                return font
    return None


def load_cjk_font(
    size: int, bold: bool = False, italic: bool = False
) -> pygame.font.Font:
    """加载支持中文的跨平台字体

    加载顺序：
      1. 平台字体文件路径（最可靠）
      2. SysFont 按名称查找
      3. pygame 默认字体（可能无法显示中文）
    """
    # 策略 1：从字体文件路径直接加载（最可靠）
    font = _load_by_platform_paths(size)
    if font:
        return font

    # 策略 2：SysFont 按名称查找
    font = _try_sysfont(_CJK_SYSFONT_NAMES, size, bold, italic)
    if font:
        return font

    # 策略 3：最终回退
    print(
        f"[Font] 警告：未能找到可用的 CJK 字体（size={size}），"
        "中文可能无法正常显示",
        file=sys.stderr,
    )
    try:
        return pygame.font.SysFont(None, size + 4, bold, italic)
    except Exception:
        return pygame.font.Font(None, size + 4)


def load_font(
    size: int, bold: bool = False, italic: bool = False
) -> pygame.font.Font:
    """加载等宽英文字体（游戏 UI 用）"""
    font = _try_sysfont(_MONO_SYSFONT_NAMES, size, bold, italic)
    if font:
        return font
    try:
        return pygame.font.SysFont(None, size, bold, italic)
    except Exception:
        return pygame.font.Font(None, size)


def load_cjk_fonts(*sizes: int, bold: bool = False) -> Tuple[pygame.font.Font, ...]:
    """一次加载多个字号的 CJK 字体，返回元组"""
    return tuple(load_cjk_font(s, bold) for s in sizes)


def load_fonts(*sizes: int, bold: bool = False) -> Tuple[pygame.font.Font, ...]:
    """一次加载多个字号的等宽字体，返回元组"""
    return tuple(load_font(s, bold) for s in sizes)
