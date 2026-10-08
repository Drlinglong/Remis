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

## Paradox Mods 必须填写 Summary

Mod Editor 会同时发布到 Steam Workshop 与 Paradox Mods。Steam 可以发布成功，而 Paradox 一侧单独报错：

> Upload failed: Missing mod Summary (PDX only).

这表示 `metadata.lua` 缺少 ModDef 的 `short_description` 字段（编辑器显示名 **Summary (PDX only)**）。
它只显示在 Paradox Mods 门户，Steam 不使用；原生限制最多 200 个字符。直接用 `metadata.lua` 打包的
Mod 需要在生成 metadata 的源头加入，例如：

```lua
'short_description','Build a Recon Center to unlock Ceres, a large permanent asteroid colony ...',
```

原生 `PDX_PrepareForUpload` 依次要求以下字段非空，缺任一项都会以同样格式报错，请一次性补齐：

- 已登录 Paradox 账号
- `title`、`short_description`、`description`、`image`（封面）、`lua_revision`
- 更新已有 Paradox 物品时还需要 `last_changes`

其他需要提前知道的原生行为：

- **图片大小**：Steam 封面和每张截图不超过 1 MB；Paradox 不超过 2 MB。按 1 MB 准备可同时满足两边。
  图片路径写成 `Mod/<Mod ID>/Images/<文件名>`，并确认发行包含有该目录。
- **版本显示**：Paradox 页面的版本只显示 ModDef 的 `version`（三段式版本号的最后一段），
  例如 1.0.0 会显示为 0。这是原生行为，不影响使用。

## 上传后不要覆盖安装目录里的 metadata

首次上传成功后，Mod Editor 会把新建物品的 `steam_id`（以及 Paradox 的 `pdx_id`）写进 Mod，并调用
`SaveWholeMod()` 重新保存**整个 Mod 目录**（`metadata.lua`、`items.lua` 和 `Data/` 下的文件都会被改写）。

如果之后用构建工具生成的 `metadata.lua` 覆盖安装目录，这些 ID 会丢失，下次上传会在 Steam 上**新建
一个重复物品**，而不是更新原物品。因此：

1. 首次上传后，把物品 ID 从 Steam 页面链接（`?id=` 后的数字）或 Paradox 页面记下来，写回生成
   metadata 的源头，让以后每次构建都带上 `steam_id` / `pdx_id`。
2. 需要改元数据时，先确认安装目录里的 `metadata.lua` 是否已有这些 ID；没有把握时，停止上传并请用户
   核对物品页面，不要盲目重新上传。
3. 补完 ID 后，用 Mod Editor 打开确认它识别为“更新已有物品”，再上传。

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
