# Tailscale 非局域网联机指南

本文说明如何用 Tailscale 让两台不在同一个局域网的电脑联机运行 `gei-world` HTTP 多人原型。适用于 macOS 和 Windows。

当前游戏网络层是 HTTP + 轮询：只要两台电脑都能访问同一个服务地址，就可以联机。Tailscale 会给每台电脑分配一个虚拟内网 IP，例如 `100.x.y.z`，两台电脑通过这个 IP 互相访问，不需要路由器端口转发。

## 1. 适用场景

推荐使用 Tailscale 的情况：

- 两台电脑不在同一个 Wi-Fi / 局域网。
- 不想配置公网服务器、路由器端口转发或防火墙穿透。
- 只是朋友/内部联调，不需要公开给陌生玩家访问。

不适合的情况：

- 希望任何玩家无需安装额外软件即可联机。
- 希望做正式公网大厅/匹配服务。

这些场景后续应考虑公网服务器部署。

## 2. 设备分工

假设：

- 电脑 A：运行 HTTP 多人服务，也可作为房主客户端。
- 电脑 B：加入方客户端。
- 两台电脑都安装 Tailscale，并登录到同一个 Tailscale 账号或同一个 tailnet。
- 两台电脑代码版本一致。

## 3. 安装 Tailscale

### 3.1 macOS

方式一：官网下载并安装：

```text
https://tailscale.com/download/mac
```

方式二：如果使用 Homebrew：

```bash
brew install --cask tailscale
```

安装后：

1. 打开 `Tailscale` 应用。
2. 登录账号。
3. 确认菜单栏 Tailscale 图标显示已连接。

### 3.2 Windows

官网下载并安装：

```text
https://tailscale.com/download/windows
```

安装后：

1. 打开 `Tailscale`。
2. 登录账号。
3. 确认任务栏 Tailscale 图标显示已连接。

## 4. 获取电脑 A 的 Tailscale IP

### 4.1 macOS

可在 Tailscale 菜单栏里查看本机 IP，也可以执行：

```bash
tailscale ip -4
```

输出示例：

```text
100.101.102.103
```

### 4.2 Windows PowerShell

可在 Tailscale 托盘菜单里查看本机 IP，也可以执行：

```powershell
tailscale ip -4
```

如果提示找不到 `tailscale` 命令，直接从 Tailscale 应用界面复制本机 `100.x.y.z` 地址即可。

下文用 `<A_TAILSCALE_IP>` 表示电脑 A 的 Tailscale IP。

## 5. 联通性检查

电脑 B 测试能否看到电脑 A。

### 5.1 macOS / Windows PowerShell

```bash
ping <A_TAILSCALE_IP>
```

期望能看到响应。如果 `ping` 被系统防火墙拦截，也不一定代表 HTTP 不通，可以继续做下一步 HTTP 测试。

## 6. 启动 gei-world HTTP 多人服务

在电脑 A 的项目根目录执行。

### 6.1 macOS

```bash
cd /Users/ruiling/Desktop/未命名文件夹/gei-world
./.conda/bin/python scripts/multiplayer_http_server.py --host 0.0.0.0 --port 8000
```

### 6.2 Windows PowerShell

进入项目目录后执行：

```powershell
cd C:\path\to\gei-world
.\.conda\python.exe scripts\multiplayer_http_server.py --host 0.0.0.0 --port 8000
```

如果 Windows 上没有 `.conda\python.exe`，但已经激活了项目 Python 环境，可用：

```powershell
python scripts\multiplayer_http_server.py --host 0.0.0.0 --port 8000
```

期望输出：

```text
多人 HTTP 服务已启动: http://0.0.0.0:8000
```

保持该终端不要关闭。

## 7. 电脑 B 验证 HTTP 服务可访问

服务地址使用：

```text
http://<A_TAILSCALE_IP>:8000
```

### 7.1 macOS

```bash
./.conda/bin/python scripts/remote_multiplayer_demo.py --url http://<A_TAILSCALE_IP>:8000 --turn-mode simultaneous
```

### 7.2 Windows PowerShell

```powershell
.\.conda\python.exe scripts\remote_multiplayer_demo.py --url http://<A_TAILSCALE_IP>:8000 --turn-mode simultaneous
```

或在已激活环境中：

```powershell
python scripts\remote_multiplayer_demo.py --url http://<A_TAILSCALE_IP>:8000 --turn-mode simultaneous
```

期望输出包含：

```text
✓ HTTP 远端多人流程完成
```

如果这一步通过，说明 Tailscale 非局域网链路可用。

## 8. UI 联机流程

两台电脑都启动 UI。

### 8.1 macOS

```bash
./.conda/bin/python scripts/ui_game.py
```

### 8.2 Windows PowerShell

```powershell
.\.conda\python.exe scripts\ui_game.py
```

或：

```powershell
python scripts\ui_game.py
```

### 8.3 电脑 A 创建等待房

电脑 A：

1. 开始界面按 `H`。
2. 服务地址填：`http://<A_TAILSCALE_IP>:8000`
3. 玩家名填：`玩家1`。
4. 回合模式填：`simultaneous` 或 `sequential`。
5. 点击“仅创建等待房”。
6. 记录 UI 显示的：
   - 房间 ID，例如 `room_1`
   - 客户端 ID，例如 `client_1`

### 8.4 电脑 B 加入房间

电脑 B：

1. 开始界面按 `H`。
2. 服务地址填：`http://<A_TAILSCALE_IP>:8000`
3. 房间 ID 填电脑 A 创建的房间 ID。
4. 玩家名填：`玩家2`。
5. 回合模式填与电脑 A 一致，例如 `simultaneous`。
6. 点击“加入房间”。

期望电脑 B 进入游戏。

### 8.5 电脑 A 重连进房间

电脑 A：

1. 开始界面按 `H`。
2. 服务地址填：`http://<A_TAILSCALE_IP>:8000`
3. 房间 ID 填刚创建的房间 ID。
4. 客户端 ID 填创建等待房时显示的客户端 ID。
5. 点击“重连房间”。

期望电脑 A 进入同一局，控制 `玩家1`。

## 9. 建议测试用例

### 9.1 同时回合

1. 用 `simultaneous` 创建并加入房间。
2. 两台电脑各自移动或建城。
3. 电脑 A 点击结束回合。
4. 电脑 B 确认电脑 A 显示等待状态后，再点击结束回合。
5. 验证整轮推进到下一回合。

期望：

- 两名玩家同回合都能行动。
- 一方结束后不能继续行动。
- 全部玩家结束后推进下一回合。

### 9.2 轮流回合

1. 用 `sequential` 创建并加入房间。
2. 玩家1先行动。
3. 玩家2在玩家1未结束前尝试行动，应不可行动或收到失败提示。
4. 玩家1结束后，玩家2可行动。

期望严格轮流。

### 9.3 离线和重连

1. 电脑 B 游戏内按 `Q` 离开房间。
2. 电脑 A 应看到玩家2离线提示。
3. 电脑 B 用房间 ID + 自己的客户端 ID 点击“重连房间”。
4. 电脑 A 应看到玩家2重新连接提示。

### 9.4 房主退出

1. 电脑 A 游戏内按 `Q` 离开房间。
2. 电脑 B 应看到房间关闭提示。
3. 电脑 B 不应能继续行动。

当前策略：房主退出会关闭房间，这是预期行为。

## 10. 常见问题

### 10.1 电脑 B 连接失败

检查：

1. 两台电脑 Tailscale 是否都显示已连接。
2. 是否登录到同一个 tailnet。
3. 服务地址是否使用电脑 A 的 Tailscale IP：`http://100.x.y.z:8000`。
4. 电脑 A 服务是否用 `--host 0.0.0.0` 启动。
5. 电脑 A 终端是否仍在运行 HTTP 服务。
6. Windows 防火墙是否拦截 Python。

### 10.2 Windows 防火墙弹窗怎么选

如果 Windows 弹出“允许 Python 通信”的防火墙提示，建议至少允许“专用网络”。Tailscale 通常会被归入专用网络环境。

如果没弹窗但连不上，可手动检查 Windows Defender 防火墙，允许当前 Python 解释器入站连接，或临时换端口测试。

### 10.3 macOS 防火墙拦截

如果 macOS 开启了防火墙并阻止 Python 接入：

1. 打开“系统设置”。
2. 进入“网络”或“隐私与安全性”里的防火墙设置。
3. 允许 Python / 终端接收入站连接。

### 10.4 `tailscale ip -4` 命令不存在

可以直接从 Tailscale 应用界面复制本机 `100.x.y.z` 地址；命令不是必须。

### 10.5 端口 8000 被占用

电脑 A 可换端口，例如：

```bash
./.conda/bin/python scripts/multiplayer_http_server.py --host 0.0.0.0 --port 8001
```

电脑 B 服务地址同步改为：

```text
http://<A_TAILSCALE_IP>:8001
```

Windows PowerShell 对应：

```powershell
.\.conda\python.exe scripts\multiplayer_http_server.py --host 0.0.0.0 --port 8001
```

## 11. 安全说明

Tailscale 方案比直接公网暴露安全很多，因为只有同一个 tailnet 内的设备能访问服务。

但当前游戏 HTTP 服务本身仍然没有：

- 房间密码
- 用户账号
- API 鉴权
- TLS
- 限流

所以建议只把 Tailscale tailnet 分享给可信设备。正式公网联机前仍需补安全能力。

## 12. 联调记录模板

```text
日期：
代码 commit：
电脑 A 系统：macOS / Windows
电脑 B 系统：macOS / Windows
电脑 A Tailscale IP：
服务地址：http://<A_TAILSCALE_IP>:8000

remote_multiplayer_demo：通过/失败，备注：
HTTP 同时回合：通过/失败，备注：
HTTP 轮流回合：通过/失败，备注：
普通玩家离线/重连：通过/失败，备注：
房主退出关闭房间：通过/失败，备注：

发现问题：
1.
2.
3.
```
