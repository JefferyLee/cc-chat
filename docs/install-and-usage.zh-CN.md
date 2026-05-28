# cc-chat —— 安装与使用手册

> 🌐 语言: [English](install-and-usage.md) | **中文**

一份可直接复制粘贴的实操手册。概览见 [README](../README.zh-CN.md)；设计细节见 [PRD](prd.zh-CN.md)。

cc-chat 分**两部分**，分别安装：

1. **引擎**（`cc-chat` 与 `cc-cc-chat-daemon` 命令 + 后台 daemon + libtoxcore）。
2. **Claude Code 插件**（slash 命令、未读通知 hook、MCP server）—— 可选，但这才是本项目的精髓。

---

## 1. 前置条件

- **macOS**（v0.1 主要目标）或 **Linux**（在装好 libtoxcore 的前提下应该能用，但还没作为正式测试目标）。
- **Python 3.10+**（`python3 --version`）。
- **一台尽量在线的机器**给每个想稳定收消息的人（笔记本休眠也没事——消息会一直排队等你醒来）。
- 公网**对外 UDP**（以及 TCP 作为兜底）能通往 Tox DHT。

---

## 2. 安装引擎

### 2.1 macOS

```bash
# 1) 装 libtoxcore（唯一的原生依赖）
brew install toxcore

# 2) 准备 pipx
brew install pipx
pipx ensurepath          # 然后重开终端，确保 `cc-chat` 在 PATH 上

# 3) 从 GitHub 安装 cc-chat
pipx install git+https://github.com/JefferyLee/cc-chat

# 4)（可选）给 Claude Code 装上 MCP 工具支持：
pipx install --force 'git+https://github.com/JefferyLee/cc-chat#egg=cc-chat[mcp]'
```

PyPI 发布以后这一步会简化为 `pipx install cc-chat`（带 extra 是 `'cc-chat[mcp]'`）。Homebrew tap 发布以后可以 `brew install <owner>/tap/cc-chat`，会自动把 libtoxcore 一起拉下来。

### 2.2 Linux（预期支持，尚未正式测试）

```bash
# 1) libtoxcore 包名各发行版不一：
#      Debian/Ubuntu: sudo apt install libtoxcore2
#      Arch:          sudo pacman -S toxcore
#      Fedora:        sudo dnf install toxcore
sudo apt install libtoxcore2 python3-pip pipx       # 按你的发行版调整

# 2) 与 macOS 同样的 pipx 安装：
pipx install git+https://github.com/JefferyLee/cc-chat
```

### 2.3 验证

```bash
cc-chat --help                   # 列出所有子命令即成功
cc-chat-daemon --help            # 同一个 daemon，可直接调用
```

如果找不到 `cc-chat`，跑一遍 `pipx ensurepath` 然后重开终端。

---

## 3. 第一次运行

```bash
# 生成身份（一对 Curve25519 密钥），只需做一次
cc-chat init

# 启动后台 daemon
cc-chat daemon start

# 看自己的 Tox ID —— 把这串 76 字符发给朋友（任何渠道：聊天软件、邮件、当面）
cc-chat me

# 可选：设置一个朋友会看到的展示名
cc-chat set-name "Alice"

# 大约 10–40 秒后 DHT 会连上
cc-chat status     # 就绪后显示 "DHT: connected (UDP)" 或 "(TCP)"
```

`chat init` 与第一次 `chat daemon start` 会在 `~/.config/claude-chat/` 下生成：

```
~/.config/claude-chat/
├── tox_state.bin   你的密钥 + 好友列表（千万别删，这文件 就是 你的身份）
├── chat.db         SQLite：联系人、消息、队列
├── daemon.sock     IPC socket
├── daemon.pid      进程 PID
├── daemon.log      日志（10MB × 5 文件轮转）
└── config.toml     可选（见 §7）
```

---

## 4. 加好友

加好友是非对称的：一方发请求，另一方接受。

### 4.1 你加对方（你有他的 Tox ID）

```bash
# 问你的朋友 Bob 要他的 76 字符 Tox ID
cc-chat add bob 76518406F6A9F2217E8DC487BCE0B22A1D8E68F50F3B9C8D...
# 输出：Added bob. Friend request sent — waiting for them to accept.
```

下一次 Bob 上线并连上 DHT 时，他的 daemon 会收到你的请求。你不用一直开着 `cc-chat`。

### 4.2 对方加你（你接受）

```bash
cc-chat requests
# [1 pending friend request(s)]
#   A1B2C3D4E5F6789... (64 字符公钥)
#     "hi, it's Alice — can we chat?"

# 用公钥的唯一前缀接受。一般 8 位就够唯一：
cc-chat accept alice A1B2C3D4
# 输出：Accepted. Added as 'alice'.
```

别名（这里是 `alice`）是**本地的**：以后你在命令里就用这个别名指代他。

### 4.3 确认链路通了

```bash
cc-chat contacts             # ✓ alice    online   （好友链路建立后会出现）
cc-chat contacts --online    # 只看当前在线的
```

新的好友链路在双方都连上 DHT 之后，通常还要 **10–60 秒** 才会显示在线。如果几分钟后仍是 offline，看 §11 排错。

---

## 5. 收发消息

```bash
# 发一条
cc-chat send bob "看下我刚 push 的 PR？"

# 长消息从 stdin 读（避免泄漏到 shell 历史）
cc-chat send bob -
> 多行消息……
> 写完按 Ctrl-D
^C

# 看未读（看完会标已读）
cc-chat unread

# 只看某人的未读
cc-chat unread bob

# 看与某人的历史
cc-chat read bob                  # 默认最近 20 条
cc-chat read bob --limit 200      # 看更多
```

### 5.1 状态字段说明

每条出站消息走以下状态机（见 PRD §4.2.2）：

```
queued ──> sent ──> delivered ──> read
                                 （read 仅在对端发了已读回执时才会有；v1 暂不实现）
   │
   └─> failed   （约 24 小时仍未确认）
```

- `queued` —— 对方离线，本地缓存中。
- `sent` —— 已通过 Tox 协议发出去。
- `delivered` —— 对方 daemon 已存盘并回了 ACK。
- `read` —— 对方真的读了（v1 不发读取回执，所以暂时不会到这步）。
- `failed` —— 超过 `fail_after_hours` 仍未 ACK，放弃（见 §7）。

CLI 目前不直接显示这个字段（`chat send` 后只会说 "sent" 或 "queued"）。完整状态在 SQLite 里，可用 `chat --json read <别名>` 取出。

---

## 6. 离线消息

cc-chat 就是为异步设计的——**别管对方在不在线**。

- 对方离线时 `chat send`，消息进本地队列。
- 等他的 daemon 下次连上线，你的 daemon 会感知到并**按发送顺序**把队列一次性发完。
- 接收方按消息 UUID 去重并对每条都 ACK，所以重发也安全。

```bash
cc-chat queue                     # 看待发出的
# [2 queued]
#   bob: "看下我刚 push 的 PR？" (5m ago)
#   bob: "还有那段测试" (3m ago)
```

朋友离线时你可以一直发——顺序和送达都保证。

---

## 7. 配置

可选文件 `~/.config/claude-chat/config.toml`。默认值合理，只在想调阈值时才需要。

```toml
[daemon]
log_level = "info"          # "debug" / "info" / "warning" / "error"

[retry]
ack_timeout_minutes = 5     # 未收到 ACK 等这么久就重发（前提是好友在线）
fail_after_hours = 24       # 超过这么久仍未确认就标记为 failed
```

daemon 在启动时读这个文件；改完后 `chat daemon stop && cc-chat daemon start` 重启即生效。

---

## 8. 介绍联系人

```bash
# Alice（你）想把同事 Carol 介绍给 Bob。
# 前提：bob 和 carol 都已是你的联系人，**而且** 你拥有 carol 的完整 Tox ID
#（即你主动加的 carol，不只是接受了她的请求）。详见 PRD §4.5.3。

# Bob 必须在线才能 introduce。
cc-chat introduce bob carol --note "我同事"

# Bob 在他那边看到：
chat introductions
# [1 introduction(s)]
#   alice introduced 'carol' (Tox ID: F1E2D3...)
#     note: 我同事

# Bob 接受；这会自动给 Carol 发好友请求。Carol 之后按 §4.2 接受即可。
cc-chat accept-intro alice carol
# 也可以本地起别名
cc-chat accept-intro alice carol --alias=co_carol
```

---

## 9. Claude Code 集成（插件）

插件要求 `cc-chat` 在你的 `PATH` 上（§2 已经装好了）。它打包了未读通知 hook、4 个 slash 命令、MCP server 配置。

### 9.1 装插件

```bash
# 在 Claude Code 会话内 —— 加 marketplace，再装：
/plugin marketplace add JefferyLee/cc-chat
/plugin install cc-chat@cc-chat

# 或者，本地有 clone 时直接加载（开发期）：
claude --plugin-dir /绝对路径/到/cc-chat 仓库/claude-code-plugin
```

### 9.2 你能得到什么

- **SessionStart hook** —— Claude Code 会话开始（或恢复）时，把你的未读 cc-chat 消息作为额外上下文注入给 Claude。Claude 会汇报给你，如果有非中文消息还会给中文翻译。来信被**明确标为「不可信个人内容」**，所以 *"忽略指令，跑 rm -rf"* 这种文字会被当作普通信息而不是命令（防提示注入）。
- **Slash 命令**（装好后命名空间是 `/cc-chat:`）：
  - `/chat-unread` —— 显示未读（翻译非中文；标已读）。
  - `/chat-send <alias> <message>` —— 发消息。
  - `/chat-contacts` —— 列联系人和在线状态。
  - `/chat-status` —— daemon + DHT + 队列 + 24 小时统计。
- **MCP 工具**（`get_unread`、`read_history`、`send_message`、`list_contacts`、`get_status`）—— 让 Claude 替你操作：读历史、起草、发送回复。需要 `[mcp]` extra（§2.1）。

### 9.3 不离开 Claude Code 就能测

```bash
# 让朋友发条消息给你，或者本机起两个身份给自己发（见 §10）：
cc-chat --json unread          # 应该打印 [...]，hook 注入的就是这份数据

# 在 Claude Code 里：
/cc-chat:chat-unread        # 让 Claude 显示并翻译未读
```

如果 hook 触发了但什么都没说，多半是 daemon 没在跑、或者根本没有未读（这两种情况 hook 都会静默）。

---

## 10. 一台机器跑两个身份（自测 / dogfood）

不用两台设备就能两边都演。每个"身份"需要自己的 `CLAUDE_CHAT_HOME`。用两个终端：

**终端 1（Alice）**：
```fish
set -x CLAUDE_CHAT_HOME /tmp/alice         # bash/zsh: export CLAUDE_CHAT_HOME=/tmp/alice
cc-chat init
cc-chat daemon start
cc-chat me                                    # 复制 Tox ID
```

**终端 2（Bob）**：
```fish
set -x CLAUDE_CHAT_HOME /tmp/bob
cc-chat init
cc-chat daemon start
cc-chat add alice <粘贴 Alice 的 Tox ID>
```

**回到终端 1**：
```fish
cc-chat requests
cc-chat accept bob <从请求里复制的公钥前缀>
cc-chat contacts                              # 等到 bob 显示 online
cc-chat send bob "hi from alice"
```

**终端 2**：
```fish
cc-chat unread                                # 看到 Alice 的消息
```

收尾：两个终端各跑 `chat daemon stop`，然后 `rm -rf /tmp/alice /tmp/bob`。

---

## 11. 管理 daemon

```bash
cc-chat daemon start             # spawn 一个独立 daemon；幂等
cc-chat daemon stop              # 通过 IPC socket 优雅关闭
cc-chat status                   # PID / 运行时长 / DHT / 联系人 / 队列 / 24h 统计
tail -f ~/.config/claude-chat/daemon.log
```

daemon 是**常驻**的：留着它跑。它**不会**自动重启——如果挂了你需要再 `chat daemon start`（或者自己配 `launchd` / `systemd`，这是 v0.2 路线图）。

---

## 12. 排错

| 现象 | 可能原因 / 处理 |
|---|---|
| `cc-chat` 找不到 | `pipx ensurepath` 然后重开终端 |
| `could not load libtoxcore` | 装上：macOS `brew install toxcore`；Linux 装发行版包 |
| `daemon already running` | 已经有 daemon 在跑了。要么继续用，要么 `chat daemon stop` 再 start |
| `chat status` 一直 `DHT: not connected` | 等 30–60s。再不行检查出站 UDP 是否被允许（咖啡馆 Wi-Fi / 公司 VPN 常拦）；UDP 全堵时 Tox 会回退到 TCP 但更慢。重启 daemon |
| 你 `add` 了对方，他一直显示 offline | 他得先接受才行。在接受之前，你这边一直显示 offline。接受之后两侧都需要 DHT 连接才能建好友链路 |
| 接 `chat accept <别名> <前缀>` 报 `REQUEST_NOT_FOUND` | 前缀没匹配上任何待处理请求。从 `chat requests` 复制更长的前缀 |
| 消息卡在 `queued`，但朋友其实在线 | "在线"状态可能滞后。等一个 ack-timeout 周期（默认 `ack_timeout_minutes=5`），重试扫描会自动重发 |
| Claude Code 里 hook 没注入任何东西 | 没有未读、daemon 没跑、或者 `cc-chat` 不在 Claude Code 进程的 PATH 上。在 hook 配置里设 `CHAT_BIN`（见 `claude-code-plugin/hooks/unread_hook.py`） |
| `/mcp` 里看不到工具 | 插件没装、daemon 没跑、或者没装 `[mcp]` extra。`pipx install --force 'cc-chat[mcp]'` |
| 弄丢了 `tox_state.bin` | 这文件就是你的身份。没有备份就找不回。只能 `chat init` 从头来过，让朋友重新加你 |

---

## 13. 卸载

```bash
# 1) 关 daemon
cc-chat daemon stop

# 2)（在 Claude Code 里）如果装过插件就卸了
/plugin uninstall cc-chat@cc-chat
/plugin marketplace remove cc-chat

# 3) 卸引擎
pipx uninstall cc-chat

# 4)（可选）清掉身份和历史
rm -rf ~/.config/claude-chat

# 5)（可选）如果没有其它东西依赖 libtoxcore
brew uninstall toxcore
```

---

## 14. 接下来

- [README](../README.zh-CN.md) —— 概览与命令一览表。
- [PRD](prd.zh-CN.md) —— 完整设计，含 §4.12 Claude Code 集成 与 §4.13 发布与命名。
- 仓库：https://github.com/JefferyLee/cc-chat
