# gei-world

一个 Python / pygame 实现的六边形回合制策略游戏：移民建城、经营收入、生产士兵、扩张领土，攻下或消灭全部对手即可获胜。

## 特性

- **单人对电脑**：2~4 名玩家，电脑分简单 / 普通 / 困难三档；支持多人共用一台电脑的热座模式。
- **两种回合模式**：轮流回合，或所有人同时行动、全部结束后进入下一回合。
- **三种地图**：大陆（2~3 块大陆）、盘古大陆、群岛；小 / 中 / 大三种尺寸，可指定种子复现。
- **网络联机**：服务端权威的 HTTP 房间；6 位房间码、可选密码，掉线自动跳过、重新连接，对局可保存到服务端后恢复。跨网络推荐配合 Tailscale。
- **规则**：城市每回合只能生产一次、防御随时间增长、攻城失败会削弱守军；领土只能连片扩张；无城市且无移民即被淘汰；100 回合未分胜负时按分数判胜。

## 下载运行

推荐普通玩家从 GitHub Releases 下载对应系统的压缩包（`GeiWorld-macos-*.zip` / `GeiWorld-windows-*.zip`），解压后运行 `GeiWorld`。

macOS 包未经过公证，若提示“已损坏”：

```bash
xattr -dr com.apple.quarantine /path/to/GeiWorld.app
```

## 从源码运行

需要 Python 3.10+。

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
gei-world                  # 或 python -m ui
gei-world-server --host 0.0.0.0 --port 8000        # 多人服务端
```

本仓库开发约定使用项目内 Conda 环境：

```bash
./.conda/bin/python -m ui                                   # 启动游戏
./.conda/bin/python scripts/multiplayer_http_server.py      # 启动多人服务端
./.conda/bin/python scripts/simulate.py --games 50          # AI 对战平衡模拟
./.conda/bin/python -m pytest                               # 测试
./.conda/bin/python -m ruff check .                         # 静态检查
```

## 操作

| 操作 | 说明 |
| --- | --- |
| 左键 | 选择单位 / 城市，同格再次点击切换；点击小地图跳转视角 |
| 右键 | 移动或攻击（黄色边框为可达范围，悬停显示路径） |
| 拖拽 / WASD / 方向键 | 平移地图；滚轮缩放（在日志上滚动可翻页） |
| `B` | 选中移民后建城 |
| `N` | 选中下一个仍可移动的单位 |
| `M` / `1`-`9` | 设置士兵移动人数（默认整栈移动） |
| `Enter` | 结束回合（仍有单位可动时会提醒并高亮） |
| `TAB` | 热座 / 调试房切换玩家视角 |
| `Q` / `F` | 离开多人房间 / 房主跳过离线玩家的回合 |
| `F1` | 快捷键帮助 |
| `ESC` | 取消选择、关闭弹窗或打开退出菜单 |

主菜单快捷键：`N` 新游戏、`H` 多人联机、`L` 读取存档。

## 多人联机

1. 一台电脑运行服务端：`gei-world-server --host 0.0.0.0 --port 8000`。
2. 房主在「多人联机」填服务地址和名字，选择回合模式与地图，点「创建房间」，把显示的房间码发给对手。
3. 对手填同一服务地址、名字和房间码，点「加入房间」，双方自动开局。
4. 掉线后填同样的服务地址、名字、房间码点「重新连接」；房主可在对局中「保存」得到恢复码，之后用「恢复已保存房间」继续。

详见 [多人联机联调指南](docs/多人联机联调指南.md) 与 [Tailscale 非局域网联机指南](docs/Tailscale非局域网联机指南.md)。开发调试可设置 `GEI_WORLD_DEV=1` 显示本机双客户端等调试入口。

## 存档

- 单机对局：顶部「保存」写入 `slot_1`~`slot_5`，「读取」或主菜单「读取存档」打开列表。
- 默认目录：macOS `~/Library/Application Support/gei-world/saves`，Windows `%APPDATA%/gei-world/saves`，Linux `~/.local/share/gei-world/saves`；可用 `GEI_WORLD_SAVE_DIR` 覆盖。
- 多人对局的保存在服务端完成（同一用户数据目录下的 `server_rooms/`）。

## 发布构建

```bash
python -m pip install -r requirements.txt pyinstaller
python scripts/build_release.py --version v0.2.0
```

推送 `v*` tag 时 GitHub Actions 会在 macOS / Windows 构建并发布；每次推送都会运行 ruff 与测试（`.github/workflows/ci.yml`）。

## 项目结构

```text
src/                 核心规则（引擎、地图、单位、城市、战斗、视野、回合、AI、存档、多人服务端与协议）
ui/                  pygame 客户端
  client_controller.py   主循环与按键分发
  controllers/           菜单、对局流程、地图交互、存档、多人等职责模块
  systems/               渲染、HUD、输入、摄像机
scripts/             启动、服务端、AI 模拟、联机调试与发布脚本
tests/               自动化测试
docs/                设计与联机文档
```

## 文档

- [优化设计（开发路线与执行结果）](docs/优化设计.md)
- [需求文档](docs/需求文档.md)
- [多人联机联调指南](docs/多人联机联调指南.md)
- [Tailscale 非局域网联机指南](docs/Tailscale非局域网联机指南.md)

## 已知限制

- 地形只有陆地和海洋，暂无科技树、建筑与更多兵种。
- 多人服务为明文 HTTP 轮询，无账号与限流，只建议在局域网或 Tailscale 等可信网络中使用。
- 数值经 AI 对战模拟调整过，但仍需要更多真人对局反馈。
