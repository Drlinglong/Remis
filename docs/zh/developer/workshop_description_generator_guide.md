# 创意工坊描述生成器 技术文档

> **Legacy 说明：** 本文记录旧工具页实现，不再代表 3.1.x 重建目标。新的项目关联、
> 版本记录、入口和安全边界以
> [Steam 工坊开发契约](steam-workshop-contract.md) 为准。

## 1. 功能概述

“创意工坊描述生成器”是一个集成在“工具”页面下的高级功能，旨在为Mod作者提供一个自动化、智能化的Steam创意工坊描述页面创建工具。它通过结合用户提供的本地化信息模板和从Steam Web API自动获取的Mod原始描述，利用AI大语言模型（LLM）将其整合、翻译并排版成符合Steam BBCode格式的精美描述文本，极大地简化了多语言发布流程。

## 2. 模块构成

该功能主要由以下几个部分构成：

-   **后端核心逻辑**: `scripts/core/workshop_formatter.py`
-   **后端API端点**: `scripts/web_server.py`
-   **AI指令模板**: `scripts/config/prompts.py`
-   **前端UI组件**: `scripts/react-ui/src/components/tools/WorkshopGenerator.jsx`
-   **前端页面集成**: `scripts/react-ui/src/pages/ToolsPage.jsx`

## 3. 工作流程

用户的操作从前端界面发起，通过后端API调用核心逻辑，最终将结果返回给前端，具体流程如下：

1.  **前端加载**:
    *   `WorkshopGenerator.jsx` 组件挂载时，会向后端 `GET /api/projects` 发起请求，获取（当前为模拟的）项目列表，用于填充“从项目选择”的下拉菜单。

2.  **用户输入与配置**:
    *   用户选择“从项目选择”或“手动输入”模式。
    *   用户输入或选择创意工坊ID。
    *   用户在“中文信息模板”文本域中，编写或修改Mod的中文标题、简介、制作人员名单等信息。
    *   用户选择生成描述的“目标语言”。如果选择“自定义”，则需额外输入语言名称。

3.  **生成请求**:
    *   用户点击“生成描述”按钮，`handleGenerate` 函数被触发。
    *   前端将 `item_id`, `user_template`, `target_language`, `project_id` (可选), `custom_language` (可选) 等参数打包，向后端 `POST /api/tools/generate_workshop_description` 发起请求。

4.  **后端处理**:
    *   `web_server.py` 中的 `generate_workshop_description` 端点接收到请求。
    *   **步骤一：获取原始描述**
        *   调用 `workshop_formatter.get_workshop_item_details(item_id)` 函数。
        *   该函数向Steam Web API (`ISteamRemoteStorage/GetPublishedFileDetails`) 发送POST请求，获取指定`item_id`的工坊物品详情。
        *   经过严格的错误处理（网络异常、API返回错误、JSON结构校验），成功则返回原始的英文描述字符串，失败则返回`None`，并由API端点向前端抛出`HTTPException`。
    *   **步骤二：AI翻译与排版**
        *   调用 `workshop_formatter.format_description_with_ai(...)` 函数。
        *   函数首先根据`target_language`和`custom_language`从 `scripts/config/prompts.py` 中的 `STEAM_BBCODE_PROMPTS` 字典选择合适的英文指令模板。
        *   将用户提供的`user_template`和第一步获取的`original_description`拼接成一份完整的待处理文本。
        *   调用Gemini AI Handler (`gemini_handler.py`)，将拼接后的文本和选定的Prompt模板发送给AI。
        *   AI根据指令，将文本翻译成目标语言，并使用BBCode进行专业排版，最后返回纯BBCode字符串。
    *   **步骤三：结果归档**
        *   调用 `workshop_formatter.archive_generated_description(...)` 函数。
        *   根据`project_id`或`workshop_id`，在项目的 `generated_descriptions` 目录下，创建一个以Mod名和时间戳命名的`.md`文件。
        *   将AI生成的BBCode内容写入该文件。
        *   返回文件的完整保存路径。

5.  **返回结果**:
    *   后端API将AI生成的`bbcode`和文件`saved_path`打包成JSON，返回给前端。
    *   前端收到响应后，更新`generatedBbcode`和`successMessage`状态，将结果显示在输出框中，并解除加载状态。

## 4. 未来扩展方向

-   **数据库集成**:
    *   `GET /api/projects` 端点目前返回的是模拟数据。未来应接入项目的数据库，动态查询真实的项目列表及其关联的创意工坊ID。
    *   `archive_generated_description` 函数目前只实现了文件归档。未来可以增加数据库操作，将每次生成的历史记录（项目ID、时间、文件路径等）存入数据库，方便版本追溯。
-   **模板库**:
    *   允许用户保存和加载自定义的`user_template`，方便在不同项目中复用。
-   **预览功能**:
    *   在前端实现一个简单的BBCode转HTML的预览窗口，让用户在复制前就能看到大致的排版效果。
