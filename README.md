# Savage Dungeon

## 仓库角色定位（投资组合分级 ②）

> 本仓在 siwpan 投资组合（D:/projects/repos，共 133 仓）中定级为 **② 精选旗舰**，领域 **游戏作品**。
> **角色**：游戏旗舰。
> **维护策略**：② 旗舰 / 枢纽仓库打磨保留，作为能力展示或收敛点；② 保留类仓库低优先维持、不主动扩张。
> 投资组合统一分级索引（多机可查）：[组合分级决策索引 · allin 事实源](https://gitee.com/siwpan/allin/blob/master/docs/事实源/组合分级决策索引.md)。

> 仓库：<https://gitee.com/siwpan/dungeon> ｜ 许可：MIT（见 [LICENSE](LICENSE)）

一款基于 pygame-ce 的地牢 Roguelike 游戏。

## 语言 / 类型
- Python / pygame 图形界面 Roguelike

## 目录要点
- `main.py` —— 入口
- `core/`、`systems/`、`shared/` —— 核心逻辑、系统与共享模块
- `assets/`、`tools/`、`tests/` —— 资源、工具与测试
- `save.json` —— 存档示例

## 运行方式与依赖
- 运行：`python main.py`
- 依赖（`requirements.txt`）：pygame-ce>=2.5.0；numpy、scipy、sounddevice（可选，音频）

## 测试状态
- py_compile 语法检查通过（14 个 .py）
- GUI 窗口游戏，未运行（仅编译）

## 规则内核接入判定（R2 · 2026-08-27）

本作检定体系为 **Savage Worlds** 骰系（特性骰 d8 + 野性骰 d6、Raise、暴击失败，
`core/savage_dice.py`），alloy.trpg 覆盖域为 D&D 三宝书 + GURPS Basic Set——
**不同规则体系，无同构原语可接**；按「只接同构原语、绝不破坏行为契约」原则保留
仓内自研 `SavageDice`（`tests/test_savage_dice.py` 36 项钉住行为，基线全绿）。
将来若引入 D&D/GURPS 检定：`from alloy.trpg import roll_3d6, gurps_success_chance`
（接入模式参照 running-group-simulator 的 `core/dice.py`）。