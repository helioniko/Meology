# 只上传 Meology V1.0.1：GitHub 教程

## 已准备的上传目录

`X:\杂项\personal\Meology-v1.0.1-GitHub`

这个目录是独立的发布仓库：只有一次源码提交和 `v1.0.1` 标签。它不连接原开发仓库，也不带原来的旧提交和旧标签。原开发目录仍保留本地历史。

源码和安装包会上传到同一个 GitHub 项目：源码在 Code 页面，安装包在 Releases 页面。`release` 目录被 Git 忽略，因此安装包需要单独作为 Release 附件上传。

## 1. 登录 GitHub

在浏览器打开 https://github.com 并登录自己的账号。记住右上角头像下面显示的用户名。

## 2. 用 VS Code 打开上传目录

VS Code → 文件 → 打开文件夹，选择上面的 `Meology-v1.0.1-GitHub`。

不要选择原来的 `personal-memory`。本教程以新发布目录为准。

按 Ctrl+Shift+G 打开源代码管理，当前分支应为 main；这里只有一次 V1.0.1 提交。源码已经提交，无需再次初始化 Git。

## 3. 发布源码

1. 按 Ctrl+Shift+P。
2. 搜索 `Publish to GitHub`，选择「发布到 GitHub」。
3. 如有提示，在浏览器登录 GitHub，并授权 Visual Studio Code。
4. 仓库名填写 `Meology`；如果已被你的账号使用，可以换成 `Meology-App`。
5. 想让别人浏览源码和下载软件，选择 Public；只自己保存，选择 Private。
6. 等待发布完成，在浏览器打开新仓库。

这个方法会创建 GitHub 仓库、添加远程连接并上传当前提交，所以采用此方法时不必提前在网页新建仓库。参见 [VS Code 官方发布教程](https://code.visualstudio.com/docs/sourcecontrol/repos-remotes#publish-to-github)。

上传成功后，Code 页面应能看到 README、Python 源码、static、locales、packaging 等。提交历史应该只有一次提交。

## 4. 上传最终版标签

VS Code → 终端 → 新建终端。复制执行：

```powershell
Set-Location -LiteralPath 'X:\杂项\personal\Meology-v1.0.1-GitHub'
git push origin v1.0.1
```

这里只上传 `v1.0.1` 标签。不要对原开发目录执行上传。

## 5. 上传安装好的软件

1. 在 GitHub 项目页面右侧找到 Releases，点击 Create a new release；已有发布页面时点击 Draft a new release。
2. Choose a tag 选择已经上传的 `v1.0.1`。
3. 标题填写 `拾记 · Meology V1.0.1`。
4. 写版本说明；可复制下面的示例。
5. 在附件框选择安装包，等待上传完成。
6. 确认附件已经显示，再点击 Publish release。

参见 [GitHub 官方 Release 教程](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository?tool=webui)。

附件位于上传目录的 `release` 文件夹：

- 必须上传：`Meology-1.0.1-Setup-x64.exe`
- 可一起上传：`Meology-1.0.1-Setup-x64.exe.sha256`
- 可一起上传：`release-manifest.json`

版本说明示例：

```text
拾记 Meology V1.0.1

桌面记录与本地个人档案工具，支持持续扩展档案、日程、核心变化审核、中英文界面和内置使用教程。

支持自定义 AI API 定时整理，也支持 DeepSeek / 豆包官网手动整理，并可通过 MCP 或复制相关背景供其他 AI 使用。

安装方法：下载 Meology-1.0.1-Setup-x64.exe，双击安装，从桌面或开始菜单启动。

系统要求：Windows 10 2004+ / Windows 11 x64，无需另装 Python。缺少 WebView2 时需要联网补齐。

首次打开先看教程，再填档案；以后从「管理 → 设置 → 使用教程」重新查看。

AI 服务需要自行配置。当前安装包未做发布者代码签名。
```

## 6. 核对上传结果

- Code：能看到 V1.0.1 源码和 README。
- Commits：只有本次初始提交，没有旧开发历史。
- Tags：只有 v1.0.1。
- Releases：有 V1.0.1 和安装包附件。
- 从网页重新下载 exe，确认文件名称和本地一致。

Code → Download ZIP 下载的是源码；给普通用户分享 Releases 页面，让他们下载 exe 安装。

## 7. 以后更新

原 `personal-memory` 继续用于开发，发布目录用于对外上传。以后把新版本代码同步到发布目录，提交后推送，并为新安装包新建 Release。不要把原开发目录的 `.git` 文件夹复制到发布目录。

在发布目录内修改后，VS Code 源代码管理中的「提交」保存本地版本，「推送」上传到 GitHub。安装包需要继续在 Releases 中上传。

如果想设置之后提交的作者，使用本仓库配置，不影响全局其他项目：

```powershell
git config user.name "你的显示名"
git config user.email "你的提交邮箱"
```

GitHub → Settings → Emails 可查看用于提交的邮箱；希望隐藏真实邮箱时复制该页面提供的 noreply 邮箱。最初的 Codex 作者标识不影响仓库属于你的 GitHub 账号。参见 [GitHub 提交邮箱说明](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address)。

## 找不到 Publish to GitHub 时的备用方法

只在没有通过上述方式创建仓库时使用：

1. 打开 https://github.com/new，新建 Meology 仓库。
2. 选择 Public 或 Private。因为本机已有源码提交，此时不要在线初始化 README、.gitignore 或许可证文件。
3. 创建后复制仓库的 HTTPS 地址。
4. 在发布目录的 VS Code 终端执行以下命令，把「你的用户名」换成实际用户名：

```powershell
Set-Location -LiteralPath 'X:\杂项\personal\Meology-v1.0.1-GitHub'
git remote add origin https://github.com/你的用户名/Meology.git
git push -u origin main
git push origin v1.0.1
```

随后继续上面的 Release 附件上传。不要同时重复两种创建仓库流程。

参见 [GitHub 上传已有本机仓库教程](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github?platform=windows)。

`working tree clean` 表示已经保存，没有新变化，是正常状态。若出现 `not a git repository`，先检查终端路径。若提示 `remote origin already exists`，运行 `git remote -v` 检查已有连接，不必再次添加。推送报错时保留错误内容，不用强制推送。
