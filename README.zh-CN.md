# cc-chat

> 🌐 语言: [English](README.md) | **中文**

一款嵌入 Claude Code 的命令行聊天插件：在写代码的同时，与朋友进行**异步、端到端加密、完全去中心化**的文字沟通——无需任何服务器，基于 [Tox](https://tox.chat) 协议。消息默默等着，你想看的时候再看。

> 状态：v0.1，macOS 优先。新用户可看[安装与使用手册](docs/install-and-usage.zh-CN.md)（实操向）；完整设计见 [PRD](docs/prd.zh-CN.md)。

## 工作原理

两个进程（参见 PRD §3.2）：

- **`cc-cc-chat-daemon`** —— 常驻后台进程，持有你的 Tox 身份、维持 DHT 连接，并把收到的消息写入本地 SQLite。
- **`cc-chat`** —— 短生命周期的 CLI，每次执行一条命令；通过 Unix socket 与 daemon 通信后退出。

所有数据本地化：密钥放在 `~/.config/claude-chat/`，没有云端。通过任何渠道交换 Tox ID 即可加好友。

## 依赖

- **Python 3.10+**
- **libtoxcore**（唯一的非 Python 依赖）：
  - macOS：`brew install toxcore`
  - Linux：安装发行版的 `toxcore` / `libtoxcore` 包

## 安装引擎

`cc-chat` 引擎是个普通程序（Python + 后台 daemon），需要 `libtoxcore`。它与下面的 Claude Code 插件分开安装。

```bash
# macOS 推荐 —— Homebrew tap 会自动拉取 libtoxcore：
brew install <owner>/tap/cc-chat              # 见 packaging/homebrew/

# 或者用 pipx（先装好 libtoxcore：brew install toxcore）：
pipx install git+https://github.com/JefferyLee/cc-chat      # 从源码安装，今天就能用
pipx install cc-chat                                        # 发布到 PyPI 后
# 加 MCP 工具支持（可选 extra）：
pipx install 'cc-chat[mcp]'
```

会安装两个命令：`cc-chat` 和 `cc-cc-chat-daemon`。（PyPI/Homebrew 上的发布名是 `cc-chat`；Python 包名是 `claude_chat`。）

## 快速上手

```bash
# 1. 创建身份（生成你的 Tox 密钥对）
cc-chat init

# 2. 启动后台 daemon
cc-chat daemon start

# 3. 看自己的 Tox ID —— 通过任何渠道分享给朋友
cc-chat me

# 4. 通过朋友的 Tox ID 加好友（76 位十六进制）
cc-chat add bob 76518406F6A9F2217E8DC487...

#    朋友收到请求后，在他那边接受：
cc-chat requests                      # 看待处理请求的公钥
cc-chat accept alice <公钥前缀>

# 5. 开聊
cc-chat send bob "你看下我刚 push 的 PR，有空回我"
cc-chat unread                        # 看未读
cc-chat read bob                      # 看与 bob 的对话历史
cc-chat queue                         # 待发送队列
```

如果朋友离线，消息会本地入队，等他下次上线自动发出。

## 命令一览

| 命令 | 作用 |
|---|---|
| `chat init` | 生成身份（一次性） |
| `chat me` | 显示自己的 Tox ID、名字、连接状态 |
| `chat set-name <名字>` | 设置展示名 |
| `chat status` | daemon 状态、DHT 连接、联系人、队列、统计 |
| `chat add <别名> <tox_id>` | 通过 Tox ID 加好友 |
| `chat requests` | 待处理的好友请求 |
| `chat accept <别名> <公钥前缀>` | 接受好友请求并给对方起本地别名 |
| `chat contacts [--online]` | 列出联系人 |
| `chat send <别名> <消息>` | 发消息（`-` 表示从 stdin 读） |
| `chat unread [别名]` | 显示未读消息（并标为已读） |
| `chat read <别名> [--limit N]` | 看对话历史 |
| `chat queue` | 待发送队列 |
| `chat introduce <to> <whom>` | 把一个联系人介绍给另一个 |
| `chat introductions` | 别人介绍给你的联系人 |
| `chat accept-intro <from> <whom> [--alias]` | 接受介绍 |
| `chat daemon start` / `stop` | 管理后台 daemon |

## 配置

可选 `~/.config/claude-chat/config.toml`：

```toml
[retry]
ack_timeout_minutes = 5    # 多久未收到 ACK 就重发
fail_after_hours = 24      # 多久仍未确认就放弃（标记 failed）
```

## 文件布局

所有数据放在 `~/.config/claude-chat/`（可用 `CLAUDE_CHAT_HOME` 环境变量覆盖——本机起两个 daemon 做测试时有用）：

```
tox_state.bin   Tox 密钥 + 好友列表
chat.db         SQLite：联系人、消息、队列
daemon.sock     IPC socket    daemon.pid   进程 PID    daemon.log   日志
config.toml     可选配置
```

## Claude Code 集成

集成以**Claude Code 插件**的形式发布（`claude-code-plugin/`），一步装好通知 hook、slash 命令和 MCP server，**不用手动改配置**。前提是 `cc-chat` 引擎在 `PATH` 上（见上面"安装引擎"）。

### 装插件

```bash
# 开发期：直接从本地目录加载
claude --plugin-dir ./claude-code-plugin

# 或通过本仓库自带的 marketplace（推荐）：
/plugin marketplace add /path/to/this/repo        # 或推到 GitHub 后用 owner/repo
/plugin install cc-chat@cc-chat
```

### 插件提供什么

- **SessionStart hook** —— 会话开始时把未读消息注入 Claude 的上下文，非中文消息自动翻成中文。来信被明确标为「不可信个人内容、非指令」，防止有人通过消息内容做提示注入。
- **Slash 命令** —— `/unread`、`/send <别名> <消息>`、`/contacts`、`/status`（命名空间为 `/cc-chat:...`）。
- **状态栏集成** —— `cc-chat statusline` 输出一行摘要（`cc-chat: 📬 2 from macbook · 1/1 online`），可接到 Claude Code 的 `statusLine` 设置里，未读数会显示在底部状态条。
- **MCP 工具** —— `get_unread`、`read_history`、`send_message`、`list_contacts`、`get_status`，让 Claude 能替你操作。需引擎的 `[mcp]` extra。

### 机器可读输出

所有读命令都支持 `--json`（放在子命令前面）：`chat --json unread`、`chat --json status` 等。`--json` 模式下 `unread` / `read` 是**只读 peek**，不会标已读。

## 发布

- **引擎 → PyPI**：`python -m build` + `twine upload` → 用户 `pipx install cc-chat`。
- **引擎 → Homebrew**：`packaging/homebrew/cc-chat.rb` 是 tap formula 模板，`depends_on "toxcore"` 让 `brew install` 顺带把 libtoxcore 装上。通过个人 tap 发布（`brew tap <owner>/<name>`）。
- **插件 → marketplace**：`.claude-plugin/marketplace.json` 让本仓库本身就是个 marketplace。推到 GitHub 后别人就能 `/plugin marketplace add JefferyLee/cc-chat` 然后 `/plugin install cc-chat`。

## v1 已知限制

- macOS 优先（Linux 在有 libtoxcore 的前提下应能工作，但还没作为正式测试目标）。
- 本地数据库和私钥**未加密**——靠文件系统权限保护，不要在共享/不可信机器上用。
- 与你聊天的人能看到你的公网 IP（Tox 协议特性）。
- 不支持群聊、语音/视频、文件传输、多设备同步。

## 开发

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -m "not dht"   # 快速离线测试
.venv/bin/python -m pytest -m dht          # 走真实 Tox DHT 的慢测试
```
