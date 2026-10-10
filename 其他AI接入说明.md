# 其他 AI 接入说明（Meology V1.0）

个人数据保存在本机，模型只负责提取信息或消费检索结果。推荐标准 MCP；没有自定义接口入口的 AI 使用按问题生成的背景。以下协议已用官方 MCP Python SDK 验证；各 AI 的实际账户连接仍需要你在对应客户端配置。

## 任意网页和客户端：复制相关背景

1. 在拾记点击「其他 AI」，填写准备问的问题。
2. 点击「生成相关背景」，检查结果；默认最多 5 条、1800 字符，可在设置调整。
3. 点击「复制问题和背景」，粘贴给 ChatGPT、Claude、Gemini 或其他 AI。
4. 需要更详细的信息时点击来源编号，再复制该条详细信息。

只读取已确认、普通隐私级别、允许分享、未归档的相关资料。待整理原文和未批准的核心新值不进入检索。原始聊天整理后已清除，来源编号对应的是提取的关键信息；无法找回已清除的完整聊天。字符预算有助于降低 token 用量，但字符数不等于所有模型的 token 数，客户端反复调用也会增加用量。

## 本机 MCP：Claude Desktop、Cursor、Gemini CLI 等

在拾记「其他 AI → 复制本机 MCP 配置」，把 JSON 合并到客户端的 MCP 配置，不要覆盖其已有的服务器。安装版配置使用内附的 `MeologyMCP.exe` 与数据库绝对路径，不需要另装 Python；源码版使用当前 Python 和 `memory_interface.py --stdio`。搬动程序或换电脑后重新复制配置。

不同客户端支持的入口及字段以各自官方文档为准：

- [Claude 本机 MCP 配置](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
- [Cursor MCP 配置](https://prod.cursor.com/help/customization/mcp)
- [Gemini CLI MCP 配置](https://geminicli.com/docs/tools/mcp-server/)

连接后可以说：「先调用 personal-memory 查询与这个问题相关的资料，再结合我的情况回答。」AI 是否主动调用工具仍取决于客户端、工具开关和它的指令。Gemini CLI 的支持不代表 Gemini 网页也支持自定义 MCP。

stdio 客户端在本机启动一个只读检索进程，不必保持拾记窗口打开。这里的只读指个人资料不能通过外部工具修改；可重建索引和可选向量缓存仍会更新。资料修改和核心审核只在拾记完成。

## HTTP MCP 与普通 API

在拾记「其他 AI」启用 HTTP 访问并生成独立访问密钥。密钥与聊天 API 密钥无关，仅在生成窗口显示，保存在 Windows 用户加密的凭据文件。重新生成后旧密钥失效。复制带密钥的 MCP 配置给支持 HTTP MCP 的本机客户端。

- MCP：`http://127.0.0.1:8766/mcp`
- 普通 API：`POST http://127.0.0.1:8766/v1/context`
- 指定来源：`POST http://127.0.0.1:8766/v1/sources`
- OpenAPI：`GET http://127.0.0.1:8766/openapi.json`

以上是默认端口；被其他软件占用时安装版自动改用空闲端口，请以「其他 AI」显示和复制的地址为准。这些 HTTP 地址仅在拾记运行时可用，全部需要 `Authorization: Bearer <访问密钥>`。HTTP 访问默认关闭；设置中可随时关闭。管理界面的 8765 端口不作为外部 AI 接口。

查询请求示例（正文为 JSON）：

```json
{"question":"结合我的工作情况，我适合怎样学习？","limit":5,"max_chars":1800}
```

返回 `context`、来源列表、字符数和检索提示。展开来源示例：`{"ids":[12],"max_chars":1800}`。参数会受软件中配置的预算约束。

## 云端网页版 AI

云端服务器不能访问你电脑的 `127.0.0.1`。支持自定义远程 MCP 的账号，需要它支持的连接通道。

- ChatGPT：可按 [官方 Secure MCP Tunnel 指南](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) 把本机 stdio MCP 服务接入；再参考 [自定义 MCP 指南](https://developers.openai.com/api/docs/guides/custom-mcp-server)。需要对应账户、组织/工作区权限与隧道配置，本版未替你连接实际账号。
- Claude 网页：参考 [官方远程连接器说明](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)。如果采用 HTTPS 转发，应只转发 8766 的检索接口，保留访问密钥校验；外部客户端是否支持固定请求头或 OAuth，以其入口为准。
- 其他网页：若支持标准 MCP，使用它的远程连接方式。若不提供自定义连接入口，使用本页第一种复制背景方式。

本版没有实现 OAuth 登录或自动公网发布。HTTPS 转发需正确转发本机 Host，并处理受信任 Origin；不应把管理端口或整个数据库暴露到公网。协议通用不等于每个消费型网页产品都开放接入。

## 工具与检索

| 工具 | 用途 | 默认限制 |
| --- | --- | --- |
| `get_personal_context` | 根据当前问题检索相关个人信息 | 5 条、1800 字符 |
| `get_personal_sources` | 展开已知来源编号的详细关键信息 | 1–3 个编号、1800 字符 |

默认在本机使用 SQLite FTS5、中文相邻词片段和主题标签，不额外调用模型。标签帮助归类，不代表对用户性格或事实的判断。可选语义检索独立选择服务和 Embedding 模型，默认关闭；开启后会把允许分享的片段和问题发送给该服务并计入调用预算。失败自动回到关键词检索，不改写数据库事实。

MCP 使用 UTF-8 换行 JSON 的 stdio，以及无会话状态的 Streamable HTTP。参考 [官方 MCP 传输规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。没有写入、执行 SQL 或一次导出整个数据库的外部工具。

## 验证

V1.0 已通过临时数据库回归及内附 MCP 可执行文件的只读查询验证。按用户要求，验证完成后删除测试脚本和测试依赖；历史测试代码仍可从 Git 的旧版本查阅。生产功能无需 MCP Python SDK。
