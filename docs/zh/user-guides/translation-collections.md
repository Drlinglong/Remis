# 翻译合集

翻译合集把同一款游戏的多个 Remis 项目和已生成的语言输出组合成一个可管理的交付。每个合集有独立标题、目标语言、成员项目和稳定的合集 Mod 身份；它不会把多个 Mod 的译文混成一个项目，也不会代替成员项目的翻译流程。

## 创建和管理

在项目管理中打开 **翻译合集**，新建合集并选择游戏、标题和目标语言。随后添加该游戏的项目成员，并为每个成员选择已经生成的目标语言输出。一个项目只能作为一个成员加入一次；所选输出语言必须属于合集的目标语言。

每个成员都要为合集中的每种目标语言选择且只选择一个已生成的输出，不能漏选。合集保存后可以继续调整成员和输出。合集记录有版本号；更新和发布绑定会基于当前版本提交。如果页面提示内容已变化或版本冲突，先重新载入合集，再核对并重试，避免覆盖另一处更新。

## 预览、检查和导出

先运行合集计划。预览会检查成员项目、所选语言输出、源文件状态和合集身份，并列出将要生成的文件与阻断项。输入在计划后发生变化时，计划会过期；重新生成计划后再导出。

Surviving Mars 会严格检查每个成员的完整文本覆盖；未批准的文本、硬编码文本或 source-copy 内容会阻止合集导出。其他游戏的预览会检查成员输出和文件，但翻译覆盖完整度属于未验证警告，不会单凭此项阻止导出。Paradox 游戏使用全局本地化覆盖：不同成员若包含相同 key，不能假设分开的成员目录就能安全同时启用。预览应列出冲突 key 和对应成员；移除冲突成员或选择兼容组合后再导出。预览未报告冲突也不代表游戏运行时兼容。

导出是一次本地文件写入，需要明确批准。合集不会自动调用翻译模型、安装 Mod 或上传 Steam。导出后检查回执、文件清单和保存位置，再按游戏要求手动安装或发布。

## 游戏交付方式

对于 **Surviving Mars**，合集生成一个多语言可选 Mod。它只在对应成员 Mod 已启用、且游戏语言匹配时加载该成员的文本；原 Mod 仍需启用。成员及其选择的译文仍分别识别，因此共享 ID 的冲突译文会阻止导出。每个成员仍须为所有目标语言提供完整、已批准的文本输出。

其他游戏采用分发包：每个成员保留独立目录，合集不会把它们合并成一个 Mod。目录分开只是打包方式，并不能解决 Paradox 全局本地化 key 冲突；请依据预览中的冲突成员信息，只选择能够一起启用的成员。其他游戏的文件输出覆盖率未验证，预览会显示警告。

合集不保证不同 Mod 彼此兼容，也不验证游戏运行时、存档或加载顺序。安装和游戏内检查仍由用户完成。

## Steam 发布身份

若要更新自己发布的 Surviving Mars 合集 Mod，先在游戏自带的 Mod Editor 中手动发布并取得该合集自己的 Steam ID，再回到合集发布设置中绑定。绑定使用版本校验，修改旧版本时需要先刷新合集。其他游戏按各自的 Mod 制作和发布流程操作；Remis 不提供它们的游戏内 Mod Editor。

不要填写成员项目原作者的 Steam ID。Remis 仅保存合集的发布身份并在本地导出中使用；它不会登录 Steam、创建工坊条目、上传或更新文件。Surviving Mars 的发布和更新由你在游戏的 Mod Editor 中手动完成；Paradox 游戏使用其各自的上传工作流。

## Agent API

通过 Agent 操作前，先调用 `/api/agent/preflight`。基础 API 为 `/api/translation-collections`；Agent 镜像为 `/api/agent/translation-collections`。两者提供相同的合集 CRUD、项目输出选项、计划、导出、发布绑定和历史操作。

| 操作 | 方法与路径 |
|---|---|
| 列出/新建合集 | `GET /api/translation-collections` / `POST /api/translation-collections` |
| 读取/更新/删除合集 | `GET /api/translation-collections/{id}` / `PUT /api/translation-collections/{id}` / `DELETE /api/translation-collections/{id}` |
| 查看成员项目可用输出 | `GET /api/translation-collections/project-options/{project_id}` |
| 生成导出预览 | `POST /api/translation-collections/{id}/plan` |
| 批准并执行本地导出 | `POST /api/translation-collections/{id}/export`，请求必须包含 `approved: true` |
| 绑定或更新 Steam 发布身份 | `PUT /api/translation-collections/{id}/publication`，提交 `expected_revision`、`steam_id` 和 `approved: true` |
| 查看合集导出历史 | `GET /api/translation-collections/{id}/history` |

Agent API 将以上路径前缀替换为 `/api/agent/translation-collections`。每次新工作流前都要先检查 preflight；计划结果需先展示给用户，只有得到明确批准后才执行导出或更新发布绑定。导出前读取计划中的检查结果和 `allowed_actions`，成功后检查持久化回执与实际输出路径。

## 相关指南

- [项目管理](project-management.md)
- [Surviving Mars Mod 本地化](surviving-mars.md)
- [Steam 工坊与发布素材](steam-workshop.md)
