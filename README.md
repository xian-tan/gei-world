# gei-world

一个 Python / pygame 实现的六边形回合制策略游戏。当前 `v0.1` 目标是稳定单机可玩 MVP：玩家通过建城、生产、移动、战斗和攻城击败 AI 对手。

## 当前状态

- UI 可视化游戏已可运行。
- 核心闭环已具备：新游戏、移动、建城、生产、结束回合、AI 回合、保存/加载、战斗/攻城、胜负、重开。
- 当前测试基线：`98 passed`。
- 已开始多人联机前置改造：保留默认轮流回合玩法，并新增同时回合制核心、UI 本地玩家视角、会话抽象、网络 DTO、本机服务端权威原型、本地双客户端调试入口、进程内多人房间 UI 原型、HTTP + 轮询传输层、HTTP 网络会话、HTTP 多人 UI 接入、多人退出/重连基础、HTTP 房间加入/重连流程和 HTTP 房间表单输入。

## 下载运行 v0.1

推荐普通玩家从 GitHub Releases 下载对应系统的压缩包：

- macOS：`GeiWorld-macos-v0.1.0.zip`
- Windows：`GeiWorld-windows-v0.1.0.zip`

下载后解压，运行其中的 `GeiWorld` 应用或可执行文件即可。

macOS 包未经过 Apple Developer ID 公证。如果提示“已损坏”或无法打开，可在终端执行一次：

```bash
xattr -dr com.apple.quarantine /path/to/GeiWorld.app
open /path/to/GeiWorld.app
```

其中 `/path/to/GeiWorld.app` 替换为解压后的实际路径。

## 从源码运行

建议使用 Python 3.11+。

```bash
git clone <your-repo-url>
cd gei-world
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python scripts/ui_game.py
```

本地开发也可以继续使用项目内 Conda 环境：

```bash
./.conda/bin/python scripts/ui_game.py
./.conda/bin/python scripts/multiplayer_http_server.py --host 127.0.0.1 --port 8000
./.conda/bin/python scripts/remote_multiplayer_demo.py --url http://127.0.0.1:8000
./.conda/bin/python -m pytest
```

## 游戏操作

开始界面：

- `SPACE`：单人轮流回合新游戏
- `T`：单人同时回合新游戏
- `M`：本机多人原型（进程内双人房间）
- `H`：打开 HTTP 多人表单（需先启动服务，可创建/加入/重连房间）
- `L`：打开存档列表
- `ESC`：弹出退出确认

游戏内基础操作：

- 左键：选择单位/城市、同格对象切换；点击无可选对象的空地会取消选中
- 右键：移动/攻击选中单位
- 黄色边框：当前单位可右键移动范围
- 橙色轮廓：结束回合前仍有移动力的单位提示
- 青色轮廓：选中城市后的城市经济范围，范围内己方领土会提供收入
- `B` / 建城按钮：选中移民后，在移民当前位置建城
- 城市面板：生产移民/士兵，士兵可批量生产
- 选中士兵：可用滑块选择移动人数，按 `M` 设为最大数量，按 `1`-`9` 设为对应数量
- `WASD` / 方向键：移动地图
- 滚轮：缩放地图
- 多人原型中按 `TAB`：在玩家1/玩家2视角之间切换
- 多人原型中按 `Q`：离开当前多人房间
- 游戏结束后 `R` 重新开始，`ESC` 弹出退出确认

## 保存和加载

- 游戏内点击“保存”会打开 `slot_1` 到 `slot_5` 多个保存槽位。
- 开始界面按 `L` 或游戏内点击“加载”会打开存档列表。
- 发布版默认存档位置为用户数据目录：
  - macOS：`~/Library/Application Support/gei-world/saves`
  - Windows：`%APPDATA%/gei-world/saves`
  - Linux：`$XDG_DATA_HOME/gei-world/saves` 或 `~/.local/share/gei-world/saves`
- 可用环境变量 `GEI_WORLD_SAVE_DIR` 覆盖存档目录。

## 发布构建

本地构建当前系统包：

```bash
python -m pip install -r requirements.txt pyinstaller
python scripts/build_release.py --version v0.1.0
```

构建产物会输出到 `release-artifacts/`。

GitHub Actions 已配置在推送 `v*` tag 时自动在 macOS / Windows 两个平台构建包，并上传到 GitHub Release：

```bash
git tag v0.1.0
git push origin main
git push origin v0.1.0
```

## 文档

- [MVP 验收清单](docs/MVP验收清单.md)
- [UI 使用说明](docs/UI使用说明.md)
- [使用说明](docs/使用说明.md)
- [项目状态](docs/PROJECT_STATUS.md)
- [后续执行计划](docs/后续执行计划.md)
- [多人联机与双回合模式规划](docs/多人联机与回合模式规划.md)
- [多人联机联调指南](docs/多人联机联调指南.md)
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
├── scripts/             # 启动、演示和发布脚本
└── docs/                # 文档
```

## 当前已知限制

- UI 新游戏暂不支持自定义玩家名、玩家数、地图类型和随机种子。
- AI 仍是基础策略，不保证高质量对战。
- 当前地形只有陆地和海洋。
- 暂无网络多人、科技树、建筑扩展和复杂单位体系。
