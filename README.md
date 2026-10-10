# Meology · 拾记

**V1.0.1 — 在桌面随手记录，逐步建立自己的个人档案。**

Meology 将事件、想法和新的个人信息提取为简洁、持续成长的本地资料。它保存你的个人数据，AI 服务负责整理；你可以更换模型，也可以按问题获取相关背景供其他 AI 使用。

## 下载与安装

打开本项目的 **Releases** 页面，下载 `Meology-1.0.1-Setup-x64.exe`，双击安装。普通用户使用安装包即可。

支持 Windows 10 2004+ / Windows 11 x64；不需要另装 Python。若电脑缺少 WebView2，安装向导需要联网补齐。当前安装包未做发布者代码签名。

## 开始使用

1. 通过桌面图标或开始菜单启动。
2. 首次打开先看使用教程，再选择愿意填写的档案方向；每项都可跳过。
3. 在小窗输入事件或想法后发送。
4. 在「管理 → 设置」配置 AI，调整语言和颜色；使用教程也在这里。
5. 从管理窗口查看档案、日程、记忆审核与「其他 AI」相关背景。
6. 通过系统托盘菜单退出软件。

API 模式默认每小时批量整理，可更改周期。网页模式提供 DeepSeek / 豆包的手动复制、发送与回填流程。AI 用于提取信息，不在小窗生成聊天回复。成功提取后清除原始输入；核心变化和 AI 推测需要审核。

## 数据与 AI

安装版个人数据独立位于 `%LOCALAPPDATA%\Meology`，升级和卸载保留数据。切换界面语言或 AI 模型不会重建档案。API 服务与密钥由使用者自行配置，使用费用取决于所选服务。

MCP 客户端可查询相关的已确认、允许分享的资料；其他 AI 可使用复制相关背景的方式。连接方法见 [其他 AI 接入说明](其他AI接入说明.md)。

## 从源码运行与构建

在 Windows x64 上使用 Python 3.12：

```powershell
python -m venv .local-cache/build-venv
.local-cache/build-venv/Scripts/python.exe -m pip install -r packaging/requirements-build.txt
.local-cache/build-venv/Scripts/python.exe -X utf8 app.py --desktop
```

生成安装包：

```powershell
.local-cache/build-venv/Scripts/python.exe packaging/build.py
```

构建时需要网络下载和校验构建工具。安装版使用内附 Python 和依赖；第三方许可随安装包提供。

[安装与发布说明](docs/Windows安装与发布.md) · [数据格式](数据格式与兼容性.md) · [使用说明](使用说明.md)

这个仓库从 V1.0.1 开始，仅包含最终版源码快照；此前的本地开发提交没有导入。个人数据库、密钥、备份与测试文件未纳入仓库。
