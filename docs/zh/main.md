<div align="center">
  <img src="/Project Remis.png" width="150" alt="Project Remis Logo">
  <h1>Project Remis</h1>
  <strong>P社Mod本地化工厂 (Paradox Mod Localization Factory)</strong>
  <p>
    <a href="https://github.com/Drlinglong/Remis/releases/latest"><img src="https://img.shields.io/github/v/release/Drlinglong/Remis?style=for-the-badge&logo=github&label=Release&labelColor=1a1a2e&color=4ecdc4" alt="Release Version"></a>
    <img src="https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python&labelColor=1a1a2e" alt="Python Version">
    </a>
    <img src="https://img.shields.io/github/license/Drlinglong/Remis?style=for-the-badge&label=License&labelColor=1a1a2e&color=lightgrey" alt="License">
  </p>

  <p>
    <a href="README.md"><img src="https://img.shields.io/badge/阅读文档-简体中文-blue.svg?style=flat-square"></a>
    <a href="README_EN.md"><img src="https://img.shields.io/badge/Read_Docs-English-green.svg?style=flat-square"></a>
  </p>

</div>

> 告别复制粘贴，拥抱自动化。本项目旨在为P社游戏（如维多利亚3、群星等）的Mod提供一套“一键启动”的高效本地化解决方案。

## 1. 项目愿景：翻译，不该成为门槛
并不是每个人都精通八国语言。

即使你真的精通，也未必愿意在下班后打开游戏时还要开动脑筋逐句翻译Mod。

这个项目的初衷，是简化这个过程——让你：

**看到一个喜欢的Mod，只需动动鼠标，就能玩到母语版本。**

它不是为“完美翻译”而生，而是为了让翻译，不再成为阻碍创意传播的门槛。

我们希望：
* 玩家可以一键本地化工坊的优秀Mod，哪怕只是粗翻，也能顺利游玩；
* 多语言创作者可以快速构建初稿，再精修润色，不再困在重复劳动中；
* 本地社区可以更低门槛地参与全球Mod生态建设。

这是一个让创作自由流动的工具，一个服务于“表达、理解、再创造”的工程。

在人工智能和大语言模型的时代，语言不该也不会成为玩家社区之间的沟通障碍。

***

## 2. 它为什么好用？——核心功能一览

我们把复杂的技术藏在了背后，让你能享受到最纯粹、最简单的汉化体验。

#### **强大的AI翻译核心**
*   **多种AI引擎任你选**: 内置支持Gemini、OpenAI、DeepSeek、Grok、Ollama等多种业界领先的AI翻译服务，你可以选择最顺手的一个。
*   **游戏术语，精准翻译**: 内置了智能词典系统。它就像一个了解游戏的老玩家，会自动识别出“船队”、“思潮”这类专门术语，并确保它们在整个Mod里翻译统一，告别机翻的生硬感。
*   **不怕奇怪文件**: P社游戏的文件格式有时很“调皮”，但我们的工具能轻松应对，保证所有文本都能被找到并翻译。
*   **大文件也不怕**: 遇到几万行的超大文本？工具会自动把它切成小块处理，稳定又可靠。
*   **完美保留原始格式**: 翻译后的文件会保持和原来一模一样的排版和注释，对Mod本身零影响。
*   **CLI工具支持**: 支持通过谷歌官方的Gemini CLI工具，每天享受千次免费的高质量AI翻译，无需额外付费。

#### **为P社游戏量身打造**
*   **支持多款游戏**: 为维多利亚3、群星、钢4等主流P社游戏都预设了专门的配置，开箱即用。
*   **“一键多语”模式**: 想把一个英文Mod同时翻译成中文、日文、德文？没问题，一键操作，工具会自动生成所有语言的本地化文件。
*   **智能处理Mod信息**: 不仅仅是游戏文本，工具还会自动翻译Mod的标题、简介，处理元数据和封面图，生成一个完整的汉化包。
*   **上下文精准翻译**: 在翻译前，你可以输入Mod的主题（比如“这是一个关于魔法的Mod”），AI就能更好地理解背景，提供更贴切的翻译。

#### **省心省力的辅助功能**
*   **自动生成校对清单**: 翻译完成后，会自动生成一份`校对进度表.csv`文件。你可以用Excel打开它，清晰地看到原文和译文的对比，方便你精修润色。
*   **翻译后自动“体检”**: 工具会检查翻译好的文件有没有格式错误，并生成一份报告，帮你提前发现问题。
*   **安全第一**: 万一翻译过程中网络中断或AI出错，工具会为你保留一份原文文件作为备份，保证你的Mod不会因此损坏。

> 想要一探“本地化工厂”的内部工作流程？我们为你准备了一份通俗易懂的[技术细节概览](./docs/zh/user-guides/how_the_factory_works.md)，让你零基础也能看懂！

***

## 3. 使用方法

> **想在本地运行模型？**
> 如果您关心数据隐私、希望离线使用，或不想支付API费用，我们强烈推荐您使用 Ollama 进行本地化。
> [点击此处查看 Ollama 设置与使用指南](./docs/zh/user-guides/using_ollama.md)。

得益于全新的打包技术，使用本项目变得前所未有的简单。**无需安装Python，无需配置环境，真正开箱即用。**

### 第1步：下载与解压
1.  从发布页面下载最新的 **便携版 (Portable)** 压缩包（例如 `Project_Remis_v1.1.0.zip`）。
2.  将它解压到你电脑的任意位置。
3.  运行setup.bat,它将自动安装依赖项，引导你输入API密钥，将其设置为环境变量，以便后续本地化流程。

> **提示：准备你的API Key！**
> 本工具是AI翻译的“搬运工”，它本身不提供翻译能力。你需要自行准备API密钥才能进行翻译。
> 在运行过程中，程序会提示您选择AI服务并输入对应的API密钥。请确保您已准备好所选AI服务（如Gemini、OpenAI等）的有效API密钥。

>  **重要提醒**:
>  申请API密钥需要注册账户并绑定银行卡。
>  使用API可能会产生费用，具体以服务商收费条款为准。
>  请注意**妥善保管**API密钥，否则可能会被刷爆银行卡！

### 第2步：放入Mod源文件
1.  打开刚刚解压的文件夹，你会看到一个名为 `source_mod` 的文件夹。
2.  将你想要汉化的整个Mod文件夹，完整地复制并粘贴到 `source_mod` 里面。

    > **强烈建议**：为了方便识别，最好把从创意工坊下载的、名字为一串数字的Mod文件夹，重命名为Mod的实际名称。

    正确的目录结构应该像这样：
    ```
    Project_Remis_v1.1.0/              # <-- 解压后的根目录
    ├── app/                           # <-- 程序核心文件 (请勿改动)
    │   ├── source_mod/                # <-- 1. 把你的Mod文件夹放在这里
    │   │   └── 你的Mod叫这个名字/
    │   │       └── ...
    │   └── my_translation/            # <-- 3. 汉化好的Mod会出现在这里
    ├── packages/
    ├── python-embed/
    ├── setup.bat                      # <-- (首次运行) 自动安装与配置
    └── run.bat                        # <-- 2. 双击我，启动汉化！
    ```

### 第3步：运行汉化！
1.  **首次使用**：请先双击运行 `setup.bat` 文件。它会自动安装依赖项，并引导你设置API密钥。
2.  **开始汉化**：双击 `run.bat` 文件。
3.  之后，你只需要根据弹出的中文提示，一步步选择即可：
    *   选择界面语言与使用的AI服务。
    *   选择你要玩的游戏。
    *   选择你要汉化哪个Mod。
    *   选择Mod的原文是什么语言，以及你想把它翻译成什么语言。
    *   选择启用或禁用词典的模糊匹配。
    *   在工程总览中确认你的上述所有选择， 然后启动翻译！
3.  等待程序运行完成。成功后，汉化好的Mod包会自动出现在 `my_translation` 文件夹里。

### 第4步：在游戏中启用Mod
1.  进入 `my_translation` 文件夹，找到刚刚生成的汉化Mod包（例如 `zh-CN-你的Mod叫这个名字`）。
2.  将这个文件夹完整地复制到游戏对应的 `mod` 目录中。
    *   **维多利亚3**: `C:\Users\你的用户名\Documents\Paradox Interactive\Victoria 3\mod`
    *   **群星 (Stellaris)**: `C:\Users\你的用户名\Documents\Paradox Interactive\Stellaris\mod`
    *   **钢铁雄心4 (HOI4)**: `C:\Users\你的用户名\Documents\Paradox Interactive\Hearts of Iron IV\mod`
    *   **十字军之王3 (CK3)**: `C:\Users\你的用户名\Documents\Paradox Interactive\Crusader Kings III\mod`
3.  启动游戏启动器，在“播放集”中，同时启用**原Mod**和**汉化Mod**。
4.  **关键一步**：确保**汉化Mod**在列表中的排序**低于**原Mod。
5.  开始游戏，享受你的母语体验吧！

### 故障排除
- **程序闪退或报错？**
  - **API Key问题**：请检查你的API Key是否正确、有效，以及账户余额是否充足。
  - **Mod文件不完整**：请确保你复制了整个Mod文件夹，而不是只有里面的 `localization` 文件夹。
- **翻译不生效？**
  - 检查在游戏启动器里，汉化Mod的加载顺序是否在原Mod**之下**。
  - 请尝试删除原始mod中的假汉化文件。某些模组自带了**假本地化文件**，这会导致本地化补丁无法生效。您需要手动删除这些文件。
  - 请前往`SteamLibrary\steamapps\workshop\content\529340\3535929411（将这串数字替换为你正在汉化的MOD的创意工坊ID）\localization`下，**删除MOD原始语言文件夹之外的所有文件夹**。
  - 例如，如原始mod为英文，则你需要删除localization下除了english文件夹之外的所有文件夹。
  - 你也可以选择将该本地化补丁的内容**覆盖**到原MOD文件夹中。这样能减少恼人的校验文件过程，steam也不会再尝试重新从工坊下载缺失的假本地化文件。
- **翻译质量不佳？**
  - 你可以尝试在 `data/glossary` 文件夹中为对应游戏添加或修改词典文件，这能显著提升术语的准确性。
  - 在开始翻译时，根据提示输入Mod的主题或关键词，也能帮助AI更好地理解上下文。

如果您遇到了更多问题，请查阅 [常见问题 (FAQ)](docs/zh/user-guides/faq.md) 获取更详细的解决方案。

***

## 4. 词典系统：让AI说“人话”的秘密武器

### 4.1. 它是如何工作的？
简单来说，词典就是一份“游戏术语小抄”。

在翻译开始前，我们会把这份小抄交给AI，并告诉它：“遇到这些词，必须严格按照小抄上的来翻译，不许自己发挥。”

**举个例子：**
*   **没有词典时**: AI可能会把 '''convoy''' 随意翻译成“护航”、“车队”或“护卫队”。
*   **有了词典后**: AI会严格按照我们的要求，在任何地方都把它准确地翻译为“船队”。

正是这个机制，保证了汉化Mod的专业性和一致性。

### 4.2. 词典文件在哪里？
你可以在 `data/glossary/` 目录下找到并编辑各个游戏的词典文件：
*   **Victoria 3**: `data/glossary/victoria3/glossary.json`
*   **Stellaris**: `data/glossary/stellaris/glossary.json`

### 4.3. 词典来源说明与致谢
本项目的游戏专用词典，其数据来源于以下优秀的官方及社区汉化项目，我们在此向所有原贡献者致以最诚挚的感谢！

*   **Victoria 3 词典来源**: 维多利亚3 汉化 更新V1.2、Morgenröte | 汉语、Better Politics Mod 简体中文汉化、牛奶汉化
*   **Stellaris 词典来源**: 鸽组汉化词典、Shrouded Regions汉化词典、L网群星mod汉化集词典

***

## 5. 项目架构
如果您对本项目的开发和调试感兴趣，可以查阅 [项目文档](docs/documentation-center.md)。
下图展示了本项目的内部结构，它保证了工具的稳定和未来的扩展能力。
```
scripts/
├── main.py                           # 【总启动器】唯一的程序入口
├── config.py                         # 【全局配置】存放语言数据库、API设置等
│
├── core/                             # 【核心引擎】可复用的底层功能模块
│   ├── api_handler.py                # 【API处理器工厂】统一管理不同AI服务接口
│   ├── gemini_handler.py             # 【Gemini处理器】Google Gemini API接口
│   ├── gemini_cli_handler.py         # 【Gemini CLI处理器】调用谷歌官方CLI
│   ├── openai_handler.py             # 【OpenAI处理器】OpenAI API接口
│   ├── qwen_handler.py               # 【Qwen处理器】阿里云通义千问API接口
│   ├── deepseek_handler.py           # 【DeepSeek处理器】DeepSeek API接口
│   ├── grok_handler.py               # 【Grok处理器】Grok API接口
│   ├── ollama_handler.py             # 【Ollama处理器】Ollama 本地化部署接口
│   ├── glossary_manager.py           # 【词典管理器】游戏专用术语词典加载与管理
│   ├── file_parser.py                # 【文件解析器】解析P社特有的.yml格式
│   ├── file_builder.py               # 【文件构建器】重建本地化文件
│   ├── directory_handler.py          # 【目录处理器】处理文件夹结构
│   ├── asset_handler.py              # 【资源处理器】处理元数据和资源文件
│   ├── proofreading_tracker.py       # 【校对追踪器】生成校对进度表
│   ├── post_processing_manager.py    # 【后处理管理器】格式验证与报告生成 ✨
│   ├── parallel_processor.py         # 【并行处理器】多文件并发处理
│   └── ... (其他核心模块)
│
├── workflows/                        # 【工作流】具体的业务流程
│   └── initial_translate.py          # 【初始翻译】主要的翻译工作流程
│
├── hooks/                            # 【钩子系统】扩展解析器功能
│   └── file_parser_hook.py          # 【文件解析钩子】自定义文件解析逻辑
│
└── utils/                            # 【辅助工具】通用功能模块
    ├── post_process_validator.py     # 【后处理验证器】游戏特定语法规则验证 ✨
    ├── punctuation_handler.py        # 【标点符号处理器】多语言标点符号转换
    └── ... (其他辅助工具)
```

***

## 6. 合作与未来计划
本项目是一个在你的反馈和我的协助下共同成长的开源项目。我们已经为未来规划了许多激动人心的功能，并已在GitHub的Issues中立项。

我们欢迎任何形式的反馈、建议和代码贡献！

***

### 许可协议 (License)

本项目采用**双许可证模式**：

1.  **代码部分**（所有 `.py` 源代码文件）  
    采用 **[GNU Affero General Public License v3.0 (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0.html)**  
    简单来说，你可以自由使用、修改和分发代码，但任何修改后的版本也必须开源，并且如果你将其用于在线服务，也必须提供源代码。

2.  **数据与文档部分**（词典、`.md` 文档等）  
    采用 **[知识共享 署名-非商业性使用-相同方式共享 4.0 国际 (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)**  
    简单来说，你可以自由分享和修改，但必须署名、不能用于商业目的，并且衍生作品必须采用相同的许可。

### ❤️ 致谢与署名 (Credits and Attribution)

如果您使用了“P社Mod本地化工厂”来制作或辅助制作您的Mod本地化文件，并将其上传到了Steam创意工坊或其他平台，我们恳请您在Mod的描述中进行简单的署名，并附上本工具的GitHub仓库链接。

您的署名是对我们工作的最大认可和支持，也能帮助到更多有需要的Mod作者。非常感谢！

**仓库地址:** `https://github.com/Drlinglong/Remis` 