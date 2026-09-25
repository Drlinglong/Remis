# Surviving Mars FPK 解包器探测记录

只读探测日期：2026-09-25。对象是本机 Steam Workshop 的 `ModContent.fpk`，未改动原件；未启动游戏、未运行 UnpackMars、未对其他游戏包批量操作。

## 工具与来源

- nickelc/hpk 官方最新 release 为 **v0.3.12**（2023-10-04），Windows x64 MSVC 包：<https://github.com/nickelc/hpk/releases/tag/v0.3.12>。`Cargo.toml` 标注 **GPL-3.0**：<https://github.com/nickelc/hpk/blob/v0.3.12/Cargo.toml>。
- 官方 Windows ZIP 的 `.sha256` 为 `6B1184DD35C26FEC8C07E36A6FA6E01DE4B7453AAB099C513FEFA499EE081005`，本机下载文件 SHA-256 一致。解压出的 `hpk.exe` SHA-256：`CF7D601B5F3981409743CED317DF775D7899C7A7F4D72910564C4FD2DD91EA45`；版本输出 `hpk 0.3.12`。
- UnpackMars 的 Nexus 作者页显示 v1.09.09，最后更新 2021-09-09；描述为递归解包游戏 HPK 并反编译 Lua 的 PowerShell 脚本，依赖 hpk.exe、Java、unluac.jar 和 PowerShell 7.2，并称脚本为 “MIT style license”：<https://www.nexusmods.com/survivingmars/mods/135?tab=description>。此脚本面向整套游戏目录的递归处理，本探测没有下载或执行它。

## 输入与结果

- 原件：`I:\SteamLibrary\steamapps\workshop\content\3215050\3679917456\ModContent.fpk`，9,561,971 bytes，SHA-256 `6172B0F49135824271C887930C2601D9E92E36A314169756DB8F78B14102E962`；隔离副本 SHA-256 相同。
- 副本及工具均位于被 Git 忽略的 `J:\V3_Mod_Localization_Factory-worktrees\multi-game-adapters\.runtime\tool-probes\hpk-0.3.12\`。
- 副本头 36 bytes：`46-4C-50-4B-20-00-00-00-01-00-00-00-20-00-00-00-00-00-00-00-33-0A-00-00-73-00-00-00-04-00-00-00-73-00-00-00`，magic 为 ASCII `FLPK`。
- 在副本上只执行了 `hpk list ModContent.fpk.copy`，结果退出码 1、错误 `Hpk(InvalidHeader)`；副本长度仍为 9,561,971 bytes。没有运行 extract。
- hpk v0.3.12 源码的 archive signature 常量是 `BPUL`：<https://github.com/nickelc/hpk/blob/v0.3.12/src/hpk/mod.rs>。与本包 `FLPK` 不同，因此旧 hpk 格式不兼容；UnpackMars 只是递归调用 hpk 与 Lua 反编译器，不能解决这个头格式差异。

## 对 Remis 自动化的结论

不要把 hpk/UnpackMars 接到 `.fpk` 自动解包流程中，也不要用修改 magic 或猜测偏移的办法绕过 `InvalidHeader`。该探测只证明 hpk 不认这个输入；它没有证明 FPK 内部没有可复用的数据结构。

## 有界 FLPK 文本样本原型

后续只读实验在被 Git 忽略的 `.runtime/tool-probes/flpk/` 中实现了一个临时原型，并新增通用诊断脚本 `scripts/developer_tools/probe_mars_flpk.py`。脚本只读取归档、在内存中解压受支持文本文件并可与一个源目录比较；不写出归档内容、不导入或执行 Lua、不识别未知 flag 为原始数据。它设置归档、索引、条目、深度、单文件/总输出和 Zstandard 窗口上限，并拒绝越界/重叠索引、路径大小写冲突、危险路径分量、非预期 Zstandard 帧大小、窗口超限和帧尾额外数据。

本机归档对照 `source_mod/Exotic Minerals Expanded` 的结果：**22 个文本 Lua 文件全部逐字节相同**（15 个 `Code/*.lua`、5 个 `Data/**/*.lua`、根目录 `items.lua` 和 `metadata.lua`），总解压 304,843 bytes；0 个仅换行差异、0 个不同。另有 28 个 `0x10` flag 项（图像类资源）保持未解码。完整源副本交付会原样复制资产，因此不会解码或改写图像字节；用户可见的 34 个 PNG 文件按字节保留。输入归档 SHA-256 前后仍为 `6172B0F49135824271C887930C2601D9E92E36A314169756DB8F78B14102E962`。本机 `K:\MiniConda\python.exe`（Python 3.13.5）已安装 `zstandard 0.23.0`，没有安装或升级依赖；Remis 后端仍使用原来的 `local_factory` 环境。

通用脚本以合成畸形输入验证了拒绝行为：子索引越过声明索引区域、忽略大小写重复路径、帧内容大小与外层声明不符、以及有效 Zstandard 帧后的额外字节均被拒绝。它是针对已观察到的单一 FLPK/ZSTD 变体的实验诊断器，不是生产解包器；图像 flag、其他 FLPK 版本/flag、压缩变体、游戏加载顺序、Mod Editor 导入、运行时效果及存档实例兼容性都没有得到验证。精确匹配只证明这些源文本样本被恢复，不证明 CSV 多语言元数据已自动生成或游戏会加载新增语言。

正式接入可从已经验证的文本子集开始，明确返回 `text_only` 覆盖范围，增加隔离快照写入、可重放清单、审批接口和更多独立样例回归；不能把未知图像 flag 当成已支持。目标是不依赖日常手点编辑器。官方 `AsyncUnpack` 可作为其他变体的后续适配路线，当前未验证独立命令行入口；不把它当作本次离线文本读取必须先经过的手工步骤。

受管回归测试：`tests/test_mars_flpk_probe.py` 使用纯合成归档和帧；通过 `K:\MiniConda\python.exe -m unittest tests.test_mars_flpk_probe -v`，8 项全部通过，包括正常恢复与原件不变、未知 flag、越界索引、循环、路径冲突/Windows 设备名、截断帧、错误展开长度和帧尾多余数据。开发工具的 zstandard 依赖尚未加入产品运行时。
