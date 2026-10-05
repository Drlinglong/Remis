# 火星求生 Mod Editor 上传前检查

本指南供 Remis Agent 在准备把火星求生 Mod 上传到 Steam Workshop 时使用。Remis 的
Agent API 预检与官方 Mod Editor 的上传校验是两件事，必须分别完成。

## 先分清两道检查

1. **Remis 预检**：按 Agent Skill 要求调用
   `GET http://127.0.0.1:1453/api/agent/preflight`，核对 Remis 当前版本、最新正式版本和
   工作流准备状态。它不会检查 Mod Editor 的发布字段，也不代表 Mod 已经可以上传。
2. **Mod Editor 上传校验**：最终打包和上传由官方 Mod Editor 完成。Remis 负责本地化准备
   和发布素材管理，不会替用户完成火星 Mod 的最终打包或 Workshop 上传。

## 中文在编辑器里显示乱码时

如果 Mod Editor 无法正常显示中文，不要根据乱码标题、描述或作者名来判断打开的是哪一份
Mod，也不要盲目点击字段。用 ASCII 的 Mod ID 和 Mod 文件夹路径识别目标：对照准备上传的
输出目录与该 Mod 的 `metadata.lua` 中 `id`，确认编辑器当前选中的就是这份输出。Mod 标题
相似或相同不能证明它们是同一份 Mod；旧安装副本可能缺少新包里的字段。

如果中文元数据需要保留，不能仅凭编辑器里的乱码判断文件已损坏或保存正确。保存后应检查
实际输出文件的 UTF-8 内容是否与预期一致；若无法可靠验证，就停止发布并请用户核对，不要
盲目重存或覆盖源 Mod。需要在编辑器中辨认的临时/正式标识可使用 ASCII 字符，但不要擅自
改写用户希望保留的正式标题或描述。

## `Last Changes` 报错的处理

如果 Mod Editor 弹出以下错误：

> Please fill in the 'Last Changes' field of your mod before uploading.

这表示当前选中的 Mod 没有可用的本次更新说明。它本身不表示 Remis 导出失败、FPK 损坏或
Steam 故障。按以下步骤处理：

1. 在左侧选中准备上传的**顶层 Mod**，并用 Mod ID/路径确认它是正确的输出副本。
2. 在右侧 **Mod properties** 中找到 **Last Changes** 字段。若面板未显示完整，先滚动面板。
3. 填写简短、具体且与本次实际改动相符的更新说明，然后用 Mod Editor 的保存操作保存 Mod。
   若中文不可读，可填写准确的 ASCII 英文说明；不要为了通过检查编造版本号、修复项或测试结果。
4. 重新触发 Mod Editor 的校验/上传动作。只有该错误消失且编辑器或 Steam 明确确认上传成功，
   才能报告发布完成。

可用以下英文结构起草说明；必须把方括号替换成已经核实的事实：

```text
First release: [language] localization for [mod and content scope], adapted to [source version].
```

不要原样提交带方括号的模板，也不要只写 `Update`。如果无法从实际文件差异或已确认的工作
记录判断改动范围，先查明事实，不要猜。

## 如果填写后仍然报错

- 再次核对左侧选中的 Mod ID、目录路径与准备上传的输出是否完全匹配；不要依赖乱码标题辨认。
- 确认文字保存在这个 Mod 的 **Last Changes** 字段，而非标题、描述或其他字段。
- 确认说明不是空字符串或纯空白，保存后再触发校验。
- 若字段已保存但仍出现同一错误，停止重复上传尝试，记录 Mod ID、目录和报错，交由用户或
  Mod 作者检查；不要绕过 Mod Editor 校验，也不要改动另一个同名副本。

## 完成状态怎么报告

- **Remis 预检通过**：只说明 Remis 检查通过，不等于 Mod 已打包或可上传。
- **`Last Changes` 已补齐**：只说明此字段已处理，不等于上传成功。
- **上传完成**：仅在编辑器或 Steam 明确确认成功后报告，并保留可核对的 Workshop 页面或物品 ID。
- 对外上传必须在用户明确授权范围内进行；仅要求准备或检查时，不上传。
