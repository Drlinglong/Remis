# 中文文档索引

本目录包含 V3 Mod Localization Factory 项目的所有中文文档。

## 产品意图与契约
- [功能意图契约模板](product-intent-template.md) - 玲珑决定、Agent 核验、共同确认
- [项目文件发现与翻译上载](product-intent-project-file-discovery.md) - 已填写示例
- [初次翻译与增量翻译产品意图](product-intent-translation-workflows.md) - 用户目标、失败语义与基线边界
- [翻译主流程开发契约](developer/translation-workflow-contract.md) - 当前实现、差异与回归测试

## 快速开始
- [从零开始：第一次汉化](user-guides/getting-started.md) - **推荐首读**：项目管理建项 → 初次翻译 → 部署
- [常见问题解答 (FAQ)](user-guides/faq.md) - 常见问题和解决方案
- [Provider 配置速查](user-guides/provider-setup-index.md) - 设置 → API，各服务商入口
- [日志与诊断](user-guides/logs-and-diagnostics.md) - 出问题先看这里
- [工厂工作原理](user-guides/how_the_factory_works.md) - 流水线概念（原理向，非操作手册）

## 用户指南
- [从零开始：第一次汉化](user-guides/getting-started.md) - 项目制正确入口（先建项目，再初次翻译）
- [增量翻译](user-guides/incremental-update.md) - Mod 更新后复用旧译文、只翻变更
- [导入已有译文](user-guides/import-existing-translations.md) - 半成品 / 翻译上载
- [一键部署](user-guides/one-click-deploy.md) - 装进游戏；可选清理假本地化
- [假本地化说明](user-guides/fake-localization.md) - 假中文原理；优先内置清理，手动为备用
- [校对](user-guides/proofreading.md) - 三栏编辑器、补丁模式、保存与验证
- [智能工坊](user-guides/agent-workshop.md) - 扫描格式问题并用 AI 修复
- [词典与词汇表](user-guides/glossary.md) - 主词典 / 额外词典 / 项目词典与翻译启用
- [常见问题解答 (FAQ)](user-guides/faq.md) - 常见问题和解决方案
- [工厂工作原理](user-guides/how_the_factory_works.md) - 原理向流水线说明
- [日志与诊断](user-guides/logs-and-diagnostics.md) - 日志在哪、怎么看、如何反馈
- [校验与错误目录](user-guides/error-catalog.md) - 变量损坏、格式标签等白话解释
- [Provider 配置速查](user-guides/provider-setup-index.md) - API / 本地模型总入口（客户端设置页优先）
- [使用 Ollama 进行本地化翻译](user-guides/using_ollama.md) - Ollama 补充说明
- [使用自定义 OpenAI API](user-guides/using_custom_openai_api.md) - 自定义接口补充说明
- [使用 ModelScope 与 SiliconFlow](user-guides/using_modelscope_and_siliconflow.md) - 魔搭 / 硅基流动补充说明

## 安装与配置
- [开发环境搭建指南](developer/development-setup.md) - 仓库开发环境说明
- [CI、依赖维护与仓库门禁](developer/ci-setup.md) - GitHub Actions、Dependabot 与本地等价命令

## 产品 Copilot（设计草案，#132）
- [Copilot 文档入口](copilot/README.md) - 用户 RAG / Agent 操作说明 / 与开发者文档的边界
- [用户 Micro-RAG 语料边界](copilot/rag-corpus-boundary.md) - 索引白名单与黑名单（不喂 developer 文档）
- [Agent 操作说明书](copilot/agent-operations.md) - 可提议操作、禁止改源码、引导 GitHub 反馈

## 开发者文档
- [文档状态说明](../docs_status.md) - 当前文档入口与历史记录说明
- [AI 智能体开发规章](../agent.md) - 已降级的旧入口，保留兼容说明
- [架构概述](developer/architecture.md) - 系统架构和设计
- [RAG 架构与模型选型](technical/rag-design.md) - 本地/云端双轨制 RAG 设计与模型选型方案（工程选型，非用户语料）
- [重构决策指南](developer/refactor_decision_guide.md) - 什么时候该补丁，什么时候该重构
- [发布构建脚本指南](developer/build-release-script-guide.md) - `build_release.bat` 脚本的使用说明
- [Feature Flags 说明](developer/feature_flags.md) - 前端实验功能开关
- [动态标签验证器与工具](developer/dynamic_tag_validator_and_tools.md) - 当前验证器相关说明
- [格式化提示词改进与游戏特定规则](developer/format_prompt_improvements.md) - AI提示优化和游戏特定格式规则
- [多文件并行处理架构说明](developer/parallel-processing.md) - 并行处理技术详解
- [Workshop 描述生成器指南](developer/workshop_description_generator_guide.md) - 工具说明

## 词典系统
- [词典与词汇表（用户向）](user-guides/glossary.md) - **客户端怎么用**：主词典 / 额外词典 / 项目词典
- [词典系统概览](glossary/overview.md) - 机制与文件结构（偏开发/进阶）
- [词典工具使用](glossary/tools-guide.md) - parser.py / validator.py（开发向）
- [系统机制说明](glossary/system-mechanism.md) - 技术实现详解
- [碧蓝档案词典](glossary/blue-archive-guide.md) - 特定主题词典

## 导航
- [English Documentation](../en/index.md) - English documentation index
- [归档文档](../archive/README.md) - 历史记录与旧版总览
- [开发历史归档](../archive/developer-history/README.md) - 重构总结与设计冻结文档
- [返回文档中心](../documentation-center.md) - 返回文档中心
