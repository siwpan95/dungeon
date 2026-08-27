# Savage Dungeon

一款基于 pygame-ce 的地牢 Roguelike 游戏。

## 语言 / 类型
- Python / pygame 图形界面 Roguelike

## 目录要点
- `main.py` —— 入口
- `core/`、`systems/`、`shared/` —— 核心逻辑、系统与共享模块
- `assets/`、`tools/`、`tests/` —— 资源、工具与测试
- `save.json` —— 存档示例

## 运行方式与依赖
- 运行：`F:\Python314\python.exe main.py`
- 依赖（`requirements.txt`）：pygame-ce>=2.5.0；numpy、scipy、sounddevice（可选，音频）

## 测试状态
- py_compile 语法检查通过（14 个 .py）
- GUI 窗口游戏，未运行（仅编译）
