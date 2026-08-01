# 封面图生成器：产品意图契约

封面图生成器帮助汉化者快速制作可上传、风格统一的本地化 Mod 封面。国旗、标题和品牌
元素是核心能力；它不是完整图片编辑器。当前实现见
[封面图生成器开发契约](developer/thumbnail-generator-contract.md)，操作方法见
[用户指南](user-guides/tools-thumbnail-generator.md)。

## 文档状态

- 产品状态：稳定、低频使用的正式工具
- 产品决定人：玲珑
- 首次确认：2026-07-31
- 历史来源：[Issue #8](https://github.com/Drlinglong/Remis/issues/8)

## 输入与编辑

用户可以手动上传原图、背景和品牌标识。未来选择项目后，可以自动读取原 Mod 的
`thumbnail` 作为初始图，用户仍可替换。

原图不是正方形时，用户应明确选择裁剪或补齐，Remis 不应静默裁掉内容。画布可添加：

- 汉化包标题、原 Mod 名称和自定义文字；
- 目标语言或国旗，包括一键添加全部旗帜；
- 用户上传的品牌标识；
- 边框、遮罩和背景颜色；
- 可拖动、缩放和调整的图片与文字元素。

## 输出与项目关联

当前兼容默认值为 512 × 512 PNG，文件名 `thumbnail.png`。这符合 Remis/Paradox 输出
习惯，但不是 Steam Workshop 的通用尺寸上限。Steam 的通用 UGC 文档列出 PNG、JPG、
GIF 预览图片，没有列出 WebP，因此当前不把 WebP 作为工坊兼容输出格式。

参考：[Steamworks ISteamUGC 文档](https://partner.steamgames.com/doc/api/isteamugc)。

现在可以下载到本机。未来项目集成可以：

- 可选保存最新一张生成结果，不建立数据库版本历史；
- 保存到项目翻译输出目录；
- 在展示准确目标路径并确认后，覆盖翻译输出中的 `thumbnail.png`。

绝不能修改或删除原 Mod／源目录中的文件。替换目标只允许是用户批准的翻译输出路径。

## Agent 与外部生图

Remis 内部不调用付费 AI 生图。Remis for Codex 可以在用户明确授权后建议使用外部图片
模型生成素材，再由用户导入。Agent 也可以读取项目名、游戏和本次目标语言，预填参数、
打开生成器，并在批准后保存或覆盖翻译输出图片。

Agent 不能修改源 Mod、删除图片，也不能上传 Steam Workshop。上传仍由用户使用平台或
游戏启动器完成。

## 明确非目标

- 自动上传 Steam Workshop；
- 自动修改原 Mod；
- 内置付费 AI 生图；
- Photoshop 式完整编辑器；
- 无确认覆盖翻译输出；
- 保存封面历史版本或复杂资产数据库。
