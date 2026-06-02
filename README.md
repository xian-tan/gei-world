# gei-world

一个 Python / pygame 实现的六边形回合制策略游戏原型。当前目标是稳定单机可玩 MVP：玩家通过建城、生产、移动、战斗和攻城击败 AI 对手。

## 当前状态

- UI 可视化游戏已可运行。
- 核心闭环已具备：新游戏、移动、建城、生产、结束回合、AI 回合、保存/加载、战斗/攻城、胜负、重开。
- 当前测试基线：`54 passed`。

## 快速开始

本项目约定使用本地 Conda 环境执行 Python 命令：

```bash
./.conda/bin/python -m pytest
./.conda/bin/python scripts/ui_game.py
```

如果只想试玩，运行：

```bash
./.conda/bin/python scripts/ui_game.py
```

开始界面快捷键：

- `SPACE`：新游戏
- `L`：加载默认存档 `saves/ui_save.json`
- `ESC`：退出

游戏内基础操作：

- 左键：选择单位/城市，或移动选中单位
- 黄色边框：当前单位可移动范围
- 右键：取消当前选择
- `B` / 建城按钮：选中移民后，在移民当前位置建城
- 城市面板：生产移民/士兵
- `WASD` / 方向键：移动地图
- 滚轮：缩放地图
- 游戏结束后 `R` 重新开始，`ESC` 退出

## 文档

- [MVP 验收清单](docs/MVP验收清单.md)
- [UI 使用说明](docs/UI使用说明.md)
- [使用说明](docs/使用说明.md)
- [项目状态](docs/PROJECT_STATUS.md)
- [后续执行计划](docs/后续执行计划.md)
- [需求文档](docs/需求文档.md)

## 项目结构

```text
gei-world/
├── README.md
├── requirements.txt
├── pytest.ini
├── src/                 # 核心游戏逻辑
├── ui/                  # pygame UI
├── tests/               # 自动化测试
├── scripts/             # 启动和演示脚本
├── docs/                # 文档
└── saves/               # 本地存档目录
```

## 常用命令

```bash
# UI 游戏
./.conda/bin/python scripts/ui_game.py

# 带说明的 UI 演示入口
./.conda/bin/python scripts/ui_demo.py

# 命令行演示
./.conda/bin/python scripts/demo.py
./.conda/bin/python scripts/interactive_game.py
./.conda/bin/python scripts/enhanced_demo.py

# 全量测试
./.conda/bin/python -m pytest
```

## 当前已知限制

- UI 新游戏暂不支持自定义玩家名、玩家数、地图类型和随机种子。
- UI 存档槽固定为 `saves/ui_save.json`。
- AI 仍是基础策略，不保证高质量对战。
- 当前地形只有陆地和海洋。
- 暂无网络多人、科技树、建筑扩展和复杂单位体系。
