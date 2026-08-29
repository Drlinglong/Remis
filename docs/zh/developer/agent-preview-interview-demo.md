# Remis Agent Preview 面试演示与备用录制脚本

## 演示前准备

1. 安装本地生成的 **Remis Agent Preview**，确认安装目录和
   `%APPDATA%\RemisAgentPreview` 均与 stable Remis 分离。
2. 在 Preview 的“设置 → API 设置”中自行配置可撤销、受限的演示 provider key。
   不在聊天、录屏、日志或仓库中展示 key。
3. 选择演示 provider/model，并确认余额或本地模型状态。不要预先批准任何付费任务。
4. 使用内置安全 Mod：
   `%APPDATA%\RemisAgentPreview\demos\Vic3_Agent_Preview_Demo`。

## 两分钟主路径

| 时间 | 操作与讲述 |
| --- | --- |
| 0:00–0:15 | 启动 Remis Agent Preview，指出它有独立安装和数据目录；stable Remis 不受影响。 |
| 0:15–0:35 | 在当前页面打开浮动小助手，询问“这个页面怎样开始第一次翻译？”。展示回答的 sources、confidence、grounding 与自动 page context。 |
| 0:35–1:05 | 输入“使用这个 Victoria 3 测试 Mod，创建一个英译中的本地化项目并准备初次翻译”。选择上述 Mod 路径，确认 source=`en`、target=`zh-CN`、provider/model。 |
| 1:05–1:25 | 展示 `localize_mod_v1` 结构化计划中的路径、项目、语言、provider/model、费用和读写副作用。强调此时尚未执行。 |
| 1:25–1:45 | 点击批准；只执行服务端保存且仍有效的计划。记录返回的真实 task ID。 |
| 1:45–2:00 | 跳转 Task Center，核对同一 task ID 和持久化状态。准确表述为“任务已启动”，不宣称翻译已完成。 |

## 备用录屏方案

- 录制 1920×1080、30 fps，窗口只包含 Preview；关闭通知并隐藏桌面私人路径。
- 从 Preview 已启动、演示 provider 已配置的状态开始录制，key 输入过程不录。
- 按上表一次连续录制；若模型暂时不可用，保留 Help Copilot grounding、计划批准门和失败状态，
  不剪辑成虚假的成功。
- 结尾停留在 Task Center 约 5 秒，让 task ID、状态与时间可读。
- 录屏仅保存在本地验证证据目录，不上传、不嵌入仓库。

## 诚实边界

此 Preview 暴露的是已有 Help Copilot 与 `localize_mod_v1` 工作流，不是通用多步骤 DAG Agent。
未知 action、多余参数、模型伪造风险/确认字段、过期计划、重复执行和批准后参数替换仍必须被拒绝。
当前缺口继续以 `docs/zh/developer/agent-copilot-contract.md` 为准。
