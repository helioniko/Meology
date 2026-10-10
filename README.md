# Meology · 拾记

[简体中文](#简体中文) | [English](#english)

**V1.0.1 · Windows 10 / 11 x64**

## 简体中文

### 项目介绍

看完邵艾伦采访孙割的播客，深度吸收了孙学、薄肌思维、黄毛思维。孙割说人要全面拥抱AI，每个人都要彻底数据化，一个人如果不能被AI完全读取，那在未来将没有任何的意义。所以开发了这个小软件来让AI能读懂每个个体，
我自己会持续使用。有任何问题可以在github上反馈，也可以发到我的个人邮箱：dongyang@stu.xmu.edu.cn  我使用中遇到问题也会持续更新

**Meology 是一个以本地数据为基础、由 AI 辅助整理的个人档案与记忆管理工具。**

你可以在桌面小窗中随手记录发生的事情、新的想法、生活变化或未来计划。Meology 会借助你选择的 AI，将这些输入提取为简洁的信息，逐步建立并更新你的个人档案。

这份档案可以涵盖学习、工作、健康、人际关系、兴趣、经历、目标等多个方面。初次填写的问卷只是起点：随着新的记录不断加入，档案可以增加新的主题和属性，持续变得更详细。

例如，第一次记录篮球训练时，可以建立篮球相关主题；之后再逐步补充训练经历、学习进展和具体目标。

**个人资料独立于 AI 模型保存。** 更换 AI 服务不会重建档案；使用其他 AI 时，可以按当前问题检索相关资料，让它结合你的个人情况回答，而无需每次重新介绍自己。

### 工作方式

```text
填写初始档案 / 随手记录
          ↓
AI 提取、去重、补充与更新
          ↓
普通信息自动整理 · 核心变化集中审核
          ↓
持续增长的本地个人档案
          ↓
按问题检索相关资料 → 提供给其他 AI
```

Meology 长期保存提取后的关键信息，而不是持续累积完整聊天记录。尚未整理的输入会暂存在本地；成功提取后清除原文，保留必要的来源信息和变更历史。

### 主要功能

| 功能 | 说明 |
| --- | --- |
| 桌面随手记录 | 使用紧凑小窗输入事件、想法和计划，支持固定到 Windows 桌面。 |
| 持续扩展个人档案 | 从具体事实开始建档，后续发现新主题、增加新属性，并补充或更新已有资料。 |
| AI 批量整理 | 使用自定义 API，按设定周期集中提取信息，默认每小时整理一次。 |
| 核心信息审核 | 关键个人信息变化与 AI 推测需要确认，普通明确事实自动整理。 |
| 日程提取 | AI 整理时识别明确的未来安排，经时间校验后加入日程。 |
| 跨 AI 使用 | 通过 MCP、本机 HTTP 接口或复制相关背景，让其他 AI 使用个人资料。 |
| 本地数据管理 | 使用 SQLite 保存资料，提供备份、JSON 导入导出和空间占用查看。 |
| 界面与引导 | 支持中文 / English、颜色设置、首次使用教程和系统托盘。 |

小窗采用原生桌面界面，管理窗口按需打开。空闲小窗不常驻 WebView2 浏览器进程。

### 下载与安装

前往 [Releases](https://github.com/helioniko/Meology-v1.0.1-GitHub/releases)，下载：

```text
Meology-1.0.1-Setup-x64.exe
```

双击安装后，通过桌面快捷方式或开始菜单启动。

**系统要求：**

- Windows 10 2004 及以上，或 Windows 11。
- 64 位 x64 系统。
- 无需另外安装 Python、Git 或 VS Code。
- 如果电脑缺少 WebView2，安装向导需要联网补齐。

当前安装包尚未进行发布者代码签名。

### 快速开始

1. **阅读内置教程**：首次打开先展示使用教程，之后可在“管理 → 设置 → 使用教程”重新查看。
2. **建立初始档案**：选择愿意填写的方向，回答具体问题；所有问题均可跳过。
3. **配置 AI**：在设置中选择 API 模式，或 DeepSeek / 豆包网页模式。
4. **随手记录**：在小窗输入事件、想法或计划，点击发送。
5. **查看整理结果**：在管理窗口查看个人档案、日程，以及需要审核的核心变化。
6. **用于其他 AI**：根据准备提问的内容生成相关背景，或配置支持 MCP 的客户端。

关闭或隐藏小窗后，可通过系统托盘管理程序；彻底退出请选择托盘菜单中的“退出”。

### AI 整理模式

#### API 模式

支持 **OpenAI Chat Completions 兼容接口**，可自行配置服务地址、API Key 和模型。

- 默认每小时批量整理。
- 可选择每 10 分钟、半小时、1 小时、半天或一天整理。
- 使用内置整理提示词和结构化校验，将 AI 输出用于更新档案。
- 更换服务或模型不影响已经保存的个人资料。
- 调用费用与额度由所选 AI 服务决定。

具体服务和模型需要支持兼容接口，并能返回符合整理协议的结果。提取失败或返回格式不合格时，待整理输入会保留以便重试。

#### 网页模式

目前提供 **DeepSeek 和豆包** 的官网入口及手动整理流程：

1. 在 Meology 中准备整理内容。
2. 复制到所选 AI 的官方网站发送。
3. 将 AI 返回的整理结果复制回 Meology。
4. 校验通过后更新档案，并生成必要的审核项或日程。

网页模式需要手动发送和回填，不会自动操作网页、读取登录状态或调用网页免费额度。是否收费以及可用额度由对应平台决定。

### 让其他 AI 使用个人资料

Meology 提供三种方式：

| 方式 | 使用场景 |
| --- | --- |
| 复制相关背景 | 在软件中输入准备问的问题，生成相关资料，再复制给任意支持文本输入的 AI。 |
| MCP | 支持 MCP 的客户端可以调用只读工具，按问题查询资料、展开来源。 |
| 本机 HTTP API | 开发者可以通过带访问密钥的本机接口集成检索功能。 |

检索只返回与问题相关的、已确认且允许分享的资料。结果受条数和字符预算约束，避免把整个档案放进每一次对话。

默认使用本地关键词与标签检索；可选语义检索需要单独配置 Embedding 服务，默认关闭。

**兼容范围：**客户端能否直接连接，取决于它是否提供 MCP 或自定义工具入口。云端 AI 无法直接访问你电脑的本机地址；没有连接入口时，可以使用复制相关背景的方式。

详细配置见 [其他 AI 接入说明](其他AI接入说明.md)。

### 本地数据与隐私

安装版的资料与程序文件分开保存：

```text
程序目录：%LOCALAPPDATA%\Programs\Meology
数据目录：%LOCALAPPDATA%\Meology
数据库：  %LOCALAPPDATA%\Meology\data\personal.sqlite3
备份目录：%LOCALAPPDATA%\Meology\backups
```

- 资料以你主动填写和发送的信息为基础。
- 使用云端 API 整理时，允许分享的相关内容会发送给所选服务。
- API 密钥使用 Windows 当前用户账户加密保存，不包含在 JSON 导出中。
- 升级和卸载保留个人数据；卸载程序不会自动清除档案。
- 数据库和交换格式具有独立版本，结构更新通过迁移处理。
- 可通过 JSON 导入导出或备份迁移资料；换电脑后需要重新配置 API 密钥。
- 备份可能包含备份时尚未整理的临时输入。

详细说明见 [数据格式与兼容性](数据格式与兼容性.md)。

### 从源码运行与构建

开发环境：**Windows x64 + Python 3.12**。

在项目根目录执行：

```powershell
python -m venv .local-cache/build-venv
.local-cache/build-venv/Scripts/python.exe -m pip install -r packaging/requirements-build.txt
.local-cache/build-venv/Scripts/python.exe -X utf8 app.py --desktop
```

生成安装包：

```powershell
.local-cache/build-venv/Scripts/python.exe packaging/build.py
```

安装包输出到 `release/`。构建脚本会下载并校验所需构建工具，因此首次构建需要联网。

主要技术：

- **Python / Tkinter**：原生桌面小窗。
- **pywebview / WebView2**：按需打开的管理界面。
- **SQLite / FTS5**：本地存储与关键词检索。
- **MCP / HTTP**：外部 AI 的只读检索接口。
- **PyInstaller / Inno Setup**：Windows 安装包构建。

构建说明见 [Windows 安装与发布](docs/Windows安装与发布.md)。

### 文档与反馈

- [使用说明](使用说明.md)
- [其他 AI 接入说明](其他AI接入说明.md)
- [数据格式与兼容性](数据格式与兼容性.md)
- [Windows 安装与发布](docs/Windows安装与发布.md)

欢迎通过 [Issues](https://github.com/helioniko/Meology-v1.0.1-GitHub/issues) 提交问题、使用反馈和功能建议，也欢迎提交 Pull Request。

报告问题时，建议附上软件版本、Windows 版本和复现步骤。

### 许可证

本仓库目前尚未添加项目级 `LICENSE` 文件。第三方依赖的许可证随安装包提供。

---

## English

### Overview

After watching Allen Shao’s podcast interview with Justin Sun, I was deeply inspired by “Sunology,” “thin-muscle thinking,” and “blond-guy thinking.”
Sun said that we should fully embrace AI and digitize every aspect of ourselves—that anyone who cannot be fully read and understood by AI will have no relevance in the future. Inspired by this idea, I built this little app to help AI understand each person as an individual.
I’ll continue using it myself and updating it as I encounter issues. If you run into any problems, please report them on GitHub or email me at d2352340996@gmail.com.

**Meology is a local-first personal profile and memory manager with AI-assisted organization.**

Use its compact desktop window to capture events, thoughts, changes in your life, and future plans. Meology sends eligible input to your chosen AI service, extracts concise information, and gradually builds and updates your personal profile.

The profile can cover education, work, health, relationships, interests, experiences, and goals. The initial questionnaire is only a starting point: new entries can introduce new topics and attributes as your profile grows.

For example, your first basketball training entry can introduce a basketball topic. Later entries can add training experiences, learning progress, and specific goals.

**Your personal data is stored independently of the AI model.** Switching providers does not rebuild your profile. When using another AI, you can retrieve information relevant to your question, helping it respond with your personal context without requiring you to introduce yourself again.

### How It Works

```text
Initial profile / Everyday input
              ↓
AI extraction, deduplication, and updates
              ↓
Routine facts organized · Core changes reviewed
              ↓
A growing local personal profile
              ↓
Question-based retrieval → Context for other AIs
```

Meology retains extracted information rather than accumulating complete chat transcripts. Unprocessed input is stored temporarily. After successful extraction, the original text is cleared while necessary source metadata and change history are retained.

### Features

| Feature | Description |
| --- | --- |
| Desktop capture | Record events, thoughts, and plans in a compact window that can be pinned to the Windows desktop. |
| Growing personal profile | Start with concrete facts, discover new topics, add attributes, and refine existing information. |
| Scheduled AI organization | Process input in batches through a configurable API, once per hour by default. |
| Core information review | Review important personal changes and AI inferences; organize routine explicit facts automatically. |
| Schedule extraction | Add explicit future arrangements identified by AI after validating their dates and times. |
| Cross-AI context | Share relevant information through MCP, a local HTTP API, or copied context. |
| Local data management | Store data in SQLite, with backups, JSON import/export, and storage usage information. |
| Interface and onboarding | Chinese and English UI, configurable colors, a first-run guide, and system tray controls. |

The capture window uses a native desktop interface. The management window opens on demand; the idle capture window does not keep a WebView2 browser process running.

### Download and Install

Visit [Releases](https://github.com/helioniko/Meology-v1.0.1-GitHub/releases) and download:

```text
Meology-1.0.1-Setup-x64.exe
```

Run the installer, then launch Meology from the desktop shortcut or Start menu.

**Requirements:**

- Windows 10 version 2004 or later, or Windows 11.
- 64-bit x64 system.
- No separate Python, Git, or VS Code installation required.
- Internet access during installation if WebView2 needs to be installed.

The current installer is not publisher code-signed.

### Quick Start

1. **Read the guide:** the first-run guide appears before profile setup and remains available in settings.
2. **Create your initial profile:** choose topics and answer concrete questions. Every question is optional.
3. **Configure AI:** select API mode or the DeepSeek / Doubao website workflow.
4. **Capture information:** enter an event, thought, or plan in the desktop window and send it.
5. **Review results:** open the management window to view your profile, schedule, and pending core changes.
6. **Use your context elsewhere:** generate context for a question or connect an MCP-compatible client.

Use the system tray to manage the application after hiding the window. Select **Exit** in the tray menu to quit completely.

### AI Organization Modes

#### API Mode

Supports **OpenAI Chat Completions-compatible APIs**, with configurable service URL, API key, and model.

- Processes input once per hour by default.
- Available intervals: 10 minutes, 30 minutes, 1 hour, 12 hours, or 24 hours.
- Uses built-in organization prompts and structured validation to update the profile.
- Switching providers or models preserves existing personal data.
- Pricing and quotas depend on the selected AI service.

Providers and models must support the compatible interface and return results that meet the organization protocol. Failed extraction or invalid output leaves pending input available for retry.

#### Website Mode

Provides official website links and a manual workflow for **DeepSeek and Doubao**:

1. Prepare the organization request in Meology.
2. Copy it to the selected AI website and send it.
3. Copy the AI's result back into Meology.
4. After validation, update the profile and create any required review items or schedule entries.

This workflow requires manual sending and result import. It does not automate websites, read login sessions, or automatically use free website quotas. Availability and pricing depend on the platform.

### Using Your Data with Other AIs

Meology offers three integration paths:

| Method | Use case |
| --- | --- |
| Copy relevant context | Enter your intended question, generate relevant information, and paste it into any AI that accepts text. |
| MCP | MCP-compatible clients can query relevant information and expand sources through read-only tools. |
| Local HTTP API | Developers can integrate retrieval through an authenticated local interface. |

Retrieval returns relevant, confirmed information that is permitted for sharing. Item limits and character budgets help avoid including the entire profile in every conversation.

Local keyword and tag retrieval is enabled by default. Optional semantic retrieval requires a separately configured embedding service and is disabled by default.

**Compatibility:** direct integration depends on whether the client exposes MCP or custom tool support. Cloud AI services cannot directly access your computer's local address. Copying relevant context remains available when direct integration is unavailable.

See [AI Integration Guide](其他AI接入说明.md) for configuration details.

### Local Data and Privacy

The installed application keeps personal data separate from program files:

```text
Application: %LOCALAPPDATA%\Programs\Meology
Data:        %LOCALAPPDATA%\Meology
Database:    %LOCALAPPDATA%\Meology\data\personal.sqlite3
Backups:     %LOCALAPPDATA%\Meology\backups
```

- Information comes from the profile answers and entries you provide.
- When using a cloud API, eligible content is sent to your selected service for organization.
- API keys are encrypted using the current Windows user account and excluded from JSON exports.
- Upgrades and uninstallation preserve personal data.
- Database and exchange formats are versioned, with migrations for structural changes.
- Use JSON import/export or backups to move your data. Configure API keys again on another computer.
- Backups may contain input that was still pending when the backup was created.

See [Data Format and Compatibility](数据格式与兼容性.md) for details.

### Run from Source and Build

Development environment: **Windows x64 with Python 3.12**.

From the project root:

```powershell
python -m venv .local-cache/build-venv
.local-cache/build-venv/Scripts/python.exe -m pip install -r packaging/requirements-build.txt
.local-cache/build-venv/Scripts/python.exe -X utf8 app.py --desktop
```

Build the installer:

```powershell
.local-cache/build-venv/Scripts/python.exe packaging/build.py
```

Output is written to `release/`. The build script downloads and verifies required build tools, so the initial build requires internet access.

Main technologies:

- **Python / Tkinter:** native desktop capture window.
- **pywebview / WebView2:** on-demand management interface.
- **SQLite / FTS5:** local storage and keyword retrieval.
- **MCP / HTTP:** read-only retrieval for external AI clients.
- **PyInstaller / Inno Setup:** Windows application packaging.

See [Windows Installation and Release Guide](docs/Windows安装与发布.md) for build details.

### Documentation and Contributions

- [Usage Guide](使用说明.md)
- [AI Integration Guide](其他AI接入说明.md)
- [Data Format and Compatibility](数据格式与兼容性.md)
- [Windows Installation and Release Guide](docs/Windows安装与发布.md)

Bug reports, feedback, and feature requests are welcome through [Issues](https://github.com/helioniko/Meology-v1.0.1-GitHub/issues). Pull requests are also welcome.

When reporting a problem, include the application version, Windows version, and reproduction steps.

### License

This repository does not currently include a project-level `LICENSE` file. Third-party dependency licenses are included with the installer.
