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

### 8.3 电脑 A 创建房间

电脑 A：

1. 主菜单点击「多人联机」（或按 `H`）。
2. 服务地址填：`http://<A_TAILSCALE_IP>:8000`，名字填你的昵称。
3. 选择回合模式（轮流 / 同时）与地图类型；需要的话填写房间密码。
4. 点击「创建房间」，进入等待大厅，界面显示 6 位**房间码**（如 `K7QP2M`）。
5. 把房间码（和密码）发给电脑 B。对方加入后，电脑 A 会自动进入对局。

### 8.4 电脑 B 加入房间

电脑 B：

1. 主菜单点击「多人联机」。
2. 服务地址填：`http://<A_TAILSCALE_IP>:8000`，名字填你的昵称。
3. 房间码填电脑 A 给的房间码（大小写均可），有密码则填写密码。
4. 点击「加入房间」，直接进入对局。

客户端身份由游戏自动记在本机，不需要再抄写任何 ID。

## 9. 建议测试用例

### 9.1 同时回合

1. 用「同时回合」创建并加入房间。
2. 两台电脑各自移动或建城。
3. 电脑 A 点击结束回合（或按 Enter），顶部状态显示“已结束 · 等待其他玩家”。
4. 电脑 B 结束回合后，两边都进入下一回合。

### 9.2 轮流回合

1. 用「轮流回合」创建并加入房间。
2. 房主先行动；对手在房主结束前无法行动。
3. 房主结束后，对手可以行动。

### 9.3 离线和重连

1. 电脑 B 游戏内按 `Q` 离开房间（或直接关掉游戏）。
2. 电脑 A 看到“已离线”提示；轮到离线玩家时服务器会自动跳过其回合，房主也可按 `F` 立即跳过。
3. 电脑 B 打开「多人联机」，服务地址、名字、房间码保持不变，点击「重新连接」。
4. 电脑 A 看到“已重新连接”提示。

直接关闭游戏而没有按 `Q` 时，服务器在约 60 秒未收到请求后才判定离线。

### 9.4 房主退出

1. 电脑 A 游戏内按 `Q` 离开房间。
2. 电脑 B 看到“房主已退出，房间关闭”提示，且不能继续行动。

### 9.5 保存与恢复房间

1. 房主在对局中点击顶部「保存」，消息栏显示**恢复码**。
2. 之后任意时间，房主在「多人联机」中把恢复码填到房间码处、名字填原对局中的名字，点击「恢复已保存房间」。
3. 房主会拿到一个新的房间码；其他玩家用**原来的名字**和新房间码点击「加入房间」，即可回到自己的席位。

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
保存与恢复房间：通过/失败，备注：
HTTP 轮流回合：通过/失败，备注：
普通玩家离线/重连：通过/失败，备注：
房主退出关闭房间：通过/失败，备注：

发现问题：
1.
2.
3.
```
