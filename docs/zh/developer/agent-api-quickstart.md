# Remis for Codex：Agent API 快速开始

Remis 是可靠的游戏本地化执行层。Codex 是自然语言控制层：理解工作区、解释计划、调用本机 API，并在安全门槛前停下来等待用户决定。

Skill 只是 Agent 的操作说明书。真正完成工作的仍然是 Remis 桌面应用、FastAPI 服务、工作流引擎、校验与修复系统、项目存储，以及人工复核和导出界面。

## 安装操作 Skill

把下面这段话交给你的 Agent：

> 从 https://github.com/Drlinglong/Remis clone 并安装 Remis，阅读仓库内的 Agent Skill，在本机启动并确认可以使用。安装成功后告诉我 Remis 已就绪。然后简要说明：OpenAI、Google 等外部供应商需要 API key 才能使用其服务；API key 是可能关联计费的私密访问凭据，只能填写在 Remis 设置 → API 设置中，不能贴进对话。LM Studio、Ollama 等本地 Provider 不需要 API key。

Codex 会从下面的位置发现仓库 Skill：

```text
.agents/skills/remis-agent/SKILL.md
```

## 检查本地服务

启动已安装的桌面应用，或者从仓库根目录运行
`scripts\developer_tools\windows\run-dev.bat`。默认端口为 `1453`；如果启动器通过
`REMIS_BACKEND_PORT` 打印了其他端口，以实际端口为准。然后检查：

```powershell
Invoke-RestMethod http://127.0.0.1:1453/api/health
Invoke-RestMethod http://127.0.0.1:1453/api/agent/preflight
Invoke-RestMethod http://127.0.0.1:1453/api/agent/capabilities
```

能力接口只返回可公开的游戏、语言、Provider 与工作流信息，不会返回 Provider 密钥。

每次开始新工作流之前都要调用 `preflight`。它会实时检查官方 GitHub 的最新 Release，并报告 Provider 设置是否缺失。首次安装后，应先在 **Remis 设置 > API 设置** 中配置云端 Provider 密钥，或者明确选择并测试一个无需密钥的本地 Provider。API key 是模型 Provider 发放的秘密凭据，用于身份认证，通常也关联计费；它应该只填进 Remis，不能贴到 Agent 对话里。

## 受控调用流程

```mermaid
flowchart TD
    C[Codex 理解用户意图] --> S[Remis Skill 应用操作规则]
    S --> I[检查 Mod 并生成计划]
    I --> A{是否需要用户批准}
    A -- 零费用 dry run --> R[Remis localhost API]
    A -- 用户已批准 --> R
    A -- 未批准 --> X[停止且不产生副作用]
    R --> W[Remis 工作流引擎]
    W --> V[校验与有界修复]
    V --> H{是否需要人工复核}
    H -- 需要 --> Q[在 Remis 中复核]
    H -- 不需要 --> E{是否批准导出或覆盖}
    E -- 已批准 --> O[可安装的汉化 Mod]
    E -- 未批准 --> X
```

详细 payload、状态和错误语义见
`.agents/skills/remis-agent/references/api-workflow.md`。

## 信任边界

- **只监听本机：** Remis 默认绑定本地地址。
- **密钥留在 Remis：** Agent 响应和能力发现都不会包含模型 API key。
- **工作前检查版本：** 每次 Agent 工作流都先对照官方 GitHub Release 检查当前安装版本。
- **花钱前批准：** 真正调用模型的翻译必须使用对应计划的明确批准。
- **模型修复前批准：** 模型修复是独立的费用与写操作门槛。
- **导出前批准：** 先展示目标路径、风险和覆盖状态，再允许部署。
- **输出必须校验：** 游戏变量、语法、编码和目录结构继续接受确定性检查。
- **操作可追踪：** 计划、任务、修复、批准和可恢复快照保存在本机 Remis 数据中。

## 当前边界

在底层工作流具备安全的协作式停止点之前，Agent API 会明确报告暂停与取消尚不支持。Codex 必须如实说明，不能假装运行中的任务已暂停。

服务运行时可在 `http://127.0.0.1:1453/docs` 查看交互式 API 文档。
