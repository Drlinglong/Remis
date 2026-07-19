# 日志与诊断

> 面向使用 **Remis 打包客户端**（安装版 / 便携版）的普通用户。
> 当你遇到闪退、翻译失败、连不上 API 时，日志是最有用的线索。

## 1. 日志是干什么的？

日志是 Remis 在后台写下的「运行记录」。
你不需要读懂每一行，但在下面这些情况里很有用：

- 程序突然退出或界面卡住
- 提示 API Key 无效、超时、连接失败
- 翻译 / 校验中途失败
- 准备到 [GitHub Issues](https://github.com/Drlinglong/Remis/issues) 反馈问题时附上证据

**请勿**把完整的 API Key、账号密码贴到公开 Issue 或聊天里。粘贴前先打码。

---

## 2. 日志一般在哪里？（Windows 安装版 / 打包客户端）

打包后的 Remis 会把日志写到当前 Windows 用户的应用数据目录下：

```text
%APPDATA%\RemisModFactory\logs\
```

### 怎么打开这个文件夹？

**方法 A（推荐）**

1. 按键盘 `Win + R`
2. 输入：`%APPDATA%\RemisModFactory\logs`
3. 回车

**方法 B**

1. 打开文件资源管理器
2. 地址栏输入上面的路径并回车
   完整形态类似：
   `C:\Users\你的用户名\AppData\Roaming\RemisModFactory\logs`

> `AppData` 默认是隐藏文件夹。用 `%APPDATA%` 可以直接跳进去，不必先「显示隐藏项」。

### 常见文件名

| 文件 | 含义（通俗） |
|------|----------------|
| `remis_backend.log` | 主日志，优先看这个 |
| `remis_backend.log.1` 等 | 旧日志备份（文件轮转后产生） |
| `uvicorn_frozen.log` | 打包环境下网络服务相关日志（若存在） |

日志会自动轮转，单个文件过大时会生成备份，一般保留最近几份即可。

### 若文件夹不存在？

可能原因：

- 还从未成功启动过客户端
- 使用的不是当前这台电脑上的同一 Windows 用户
- 极少数便携/特殊启动方式把数据写到了别处

此时可：重新启动一次 Remis 再查看；或在反馈 Issue 时说明「找不到 logs 文件夹」以及你的启动方式。

---

## 3. 界面里也能看到一部分日志

翻译、校验等长时间任务进行时，界面上通常会有 **任务日志 / 进度输出**（滚动文本）。

- 适合立刻看到「卡在哪一步」
- 程序崩溃后，界面日志可能消失，这时仍以磁盘上的 `remis_backend.log` 为准

若将来客户端提供「打开日志文件夹」按钮，优先点按钮；本文路径仍可作为备用。

---

## 4. 出问题了，日志怎么看？

用记事本、VS Code 或任意文本编辑器打开 `remis_backend.log`：

1. 滚到 **文件末尾**（最新内容在下面）
2. 搜索这些词（不区分大小写也可以多试几次）：
   - `ERROR`
   - `Exception`
   - `Traceback`
   - `401` / `403` / `429`（常见 HTTP 状态，和 API 权限、配额有关）
   - `timeout` / `连接` / `Connection`
3. 把 **出错时间点附近** 的几十行记下来（或截图）

### 看不懂怎么办？

不需要全部理解。反馈时附上：

- 你在做什么（例如「点了开始翻译后约 2 分钟失败」）
- 游戏 / 项目名（可匿名）
- 用的哪家 AI 服务（**不要**附 Key）
- 日志末尾含 `ERROR` 的片段（已打码）

发到：<https://github.com/Drlinglong/Remis/issues>

---

## 5. 常见现象对照

| 现象 | 可先自查 | 日志里可能出现的线索 |
|------|----------|----------------------|
| 连不上 API | Key、Base URL、模型名、网络/代理 | 401、403、超时、DNS、Connection refused |
| 配额用尽 | 服务商控制台额度 | 429、quota、rate limit |
| 翻译中断 | 是否断网、是否关了电脑休眠 | 中途 ERROR、任务中止 |
| 启动即闪退 | 杀毒软件拦截、权限 | 若完全没有新日志，说明可能没写到磁盘就退出了 |
| 校验一堆红字 | 见 [错误目录](error-catalog.md) | 校验相关 message；不一定是程序崩溃 |

更完整的使用问题也可先看 [FAQ](faq.md)。

---

## 6. 反馈问题前的小清单

- [ ] 已尝试复现一次，并确认仍失败
- [ ] 已打开 `%APPDATA%\RemisModFactory\logs`
- [ ] 已复制/截取 **末尾 ERROR 段**，并去掉 API Key
- [ ] 写清：系统（如 Windows 10/11）、Remis 版本号（若界面或安装包能看到）、操作步骤
- [ ] 发到 GitHub Issues，而不是指望聊天助手修改客户端程序

> Remis 普通客户端 **无法在本机改软件源码**。功能请求与缺陷请走 GitHub，便于维护者修复并随版本发布。

---

## 7. 相关文档

- [常见问题 FAQ](faq.md)
- [一键部署](one-click-deploy.md)
- [假本地化说明](fake-localization.md)
- [智能工坊](agent-workshop.md)
- [校验与格式错误目录](error-catalog.md)
- [使用 Ollama](using_ollama.md)
- [自定义 OpenAI 兼容 API](using_custom_openai_api.md)
