import { useState } from 'react'
import { MeasuredText } from '../components/MeasuredText'
import { SiteShell } from '../components/SiteShell'
import { useI18n } from '../i18n/context'
import { links, sitePath } from '../site'
import { copyText, installPrompt } from './codexPrompt'

const copy = {
  en: {
    eyebrow: 'REMIS AGENT HUB · CODEX EDITION',
    title: 'Remis for Codex',
    lead: 'Install · diagnose · orchestrate',
    contract: 'Codex handles the workspace. Remis validates and delivers.',
    body: 'Not a second in-app assistant. This is the control surface that can reach Remis before launch, across tools, and between long-running jobs.',
    install: 'Copy one instruction. Codex installs Remis, completes first-run provider setup, and connects this workspace.',
    promptLabel: 'SEND ONE INSTRUCTION TO CODEX',
    promptPreview: 'Install Remis, complete first-run provider setup, and connect this workspace.',
    copyButton: 'Copy and open Codex',
    copied: 'Copied. Opening Codex…',
    copyOnly: 'Copy without opening',
    agents: 'SUPPORTED AI TOOLS',
    agentNote: 'Codex is the featured Build Week path. The same local contract stays open to other capable Agents.',
    capabilityEyebrow: 'WHY AN EXTERNAL AGENT?',
    capabilityTitle: 'Useful where an in-app assistant cannot reach.',
    mapEyebrow: 'CAPABILITY MAP',
    mapTitle: 'The cards are product capabilities. The Skill is the connector.',
    architectureEyebrow: 'EXECUTION ARCHITECTURE',
    architectureTitle: 'Two control surfaces. One reliable execution plane.',
    insideLabel: 'INSIDE REMIS',
    insideTitle: 'Embedded Remis Assistant',
    insideBody: 'Explains the current page, answers product questions, and guides the next in-app action.',
    outsideLabel: 'ACROSS THE WORKSPACE',
    outsideTitle: 'Codex and external Agents',
    outsideBody: 'Installs, updates, diagnoses, coordinates files and tools, and reconnects to durable Remis jobs.',
    safetyEyebrow: 'DESIGNED FOR STRONG AGENTS',
    safetyTitle: 'Powerful automation needs visible boundaries.',
    developerEyebrow: 'BUILD ON THE SAME CONTRACT',
    developerTitle: 'One local API for Codex, other Agents, and developers.',
    download: 'Download Remis',
    use: 'Use with Codex',
    developers: 'Developers',
    skill: 'Read the Agent Skill',
    quickstart: 'Open API quickstart',
    api: 'Inspect local OpenAPI',
  },
  zh: {
    eyebrow: 'REMIS AGENT HUB · CODEX EDITION',
    title: 'Remis for Codex',
    lead: '安装 · 诊断 · 编排',
    contract: 'Codex 负责工作区与工具链，Remis 负责校验与交付。',
    body: '它不是第二个内置助手，而是能在启动 Remis 之前、跨越多个工具、以及长任务之间持续工作的外部控制入口。',
    install: '复制一句话。Codex 会安装 Remis、完成首次 Provider 配置，并连接当前工作区。',
    promptLabel: '把一句指令发送给 CODEX',
    promptPreview: '安装 Remis，完成首次 Provider 配置，并连接当前工作区。',
    copyButton: '复制并打开 Codex',
    copied: '已复制，正在打开 Codex…',
    copyOnly: '仅复制，不打开',
    agents: '支持以下 AI 工具',
    agentNote: 'Codex 是 Build Week 的主入口；同一套本机合同也向其他可靠 Agent 开放。',
    capabilityEyebrow: '为什么还需要外部 AGENT？',
    capabilityTitle: '它能到达内置助手够不到的地方。',
    mapEyebrow: '能力地图',
    mapTitle: '卡片代表 Remis 的产品能力，Skill 只是连接器。',
    architectureEyebrow: '执行架构',
    architectureTitle: '两个控制入口，共用一个可靠执行层。',
    insideLabel: 'REMIS 内部',
    insideTitle: '内置 Remis 小助手',
    insideBody: '理解当前页面、回答产品问题，并引导用户完成下一步应用内操作。',
    outsideLabel: '跨越整个工作区',
    outsideTitle: 'Codex 与外部 Agent',
    outsideBody: '负责安装、更新、故障诊断、文件与工具协调，并重新连接可恢复的 Remis 长任务。',
    safetyEyebrow: '为强大的 AGENT 而设计',
    safetyTitle: '自动化越强，边界越要清楚。',
    developerEyebrow: '基于同一套合同继续构建',
    developerTitle: 'Codex、其他 Agent 和开发者共用一个本机 API。',
    download: '下载 Remis',
    use: '与 Codex 一起使用',
    developers: '开发者',
    skill: '查看 Agent Skill',
    quickstart: '打开 API 快速开始',
    api: '查看本机 OpenAPI',
  },
}

const conversations = {
  en: [
    {
      tag: '01 · INSTALL & UPDATE',
      user: 'Set up Remis in this workspace and make sure I can actually translate.',
      agent: 'The latest stable Remis is installed and healthy. Translation still needs a model provider. I opened API Settings so you can enter the key inside Remis. If “API key” is unfamiliar, I can explain it first.',
    },
    {
      tag: '02 · DIAGNOSE',
      user: 'Remis stopped halfway through yesterday. Find out what happened.',
      agent: 'The desktop app is closed, but the durable job record remains. I found a provider timeout after file 16 of 24. I can verify the connection, restart Remis, and resume from the saved checkpoint.',
    },
    {
      tag: '03 · ORCHESTRATE',
      user: 'Only localize the files changed in this branch, then prepare them for review.',
      agent: 'Git reports 6 changed localization files. I matched them to the Remis project, prepared an incremental plan, and will return the validated diff here. Paid model work still waits for your approval.',
    },
    {
      tag: '04 · VALIDATE & SHIP',
      user: 'Finish the release candidate and tell me what still needs a human.',
      agent: 'Remis validation passed with 0 errors and 3 wording warnings. I can prepare the installable package, update the release notes, and show the exact overwrite target before asking for approval.',
    },
  ],
  zh: [
    {
      tag: '01 · 安装与更新',
      user: '在这个工作区配置好 Remis，确保我真的可以开始翻译。',
      agent: '最新版稳定版 Remis 已安装并通过健康检查。翻译仍需要模型 Provider；我已打开 API 设置，请把密钥直接填在 Remis 里。如果你不清楚什么是 API key，我可以先解释。',
    },
    {
      tag: '02 · 故障诊断',
      user: 'Remis 昨天跑到一半停了，帮我查清楚发生了什么。',
      agent: '桌面应用已经关闭，但持久任务记录还在。第 16/24 个文件后出现 Provider 超时。我可以检查连接、重启 Remis，并从保存点继续。',
    },
    {
      tag: '03 · 跨工具编排',
      user: '只汉化这个分支里改过的文件，然后准备好让我审阅。',
      agent: 'Git 显示 6 个本地化文件发生变化。我已把它们关联到 Remis 项目并生成增量计划，完成后会把校验过的 diff 带回这里。付费模型调用仍需你批准。',
    },
    {
      tag: '04 · 校验与交付',
      user: '完成这个发布候选，并告诉我还有哪些内容必须人工处理。',
      agent: 'Remis 校验为 0 个错误、3 个措辞警告。我可以准备可安装包、更新发布说明，并在请求批准前展示确切覆盖目标。',
    },
  ],
}

const capabilityGroups = {
  en: [
    ['Project & Mod Management', 'Detect game and language', 'Import local mods', 'Inspect files and metadata', 'Track project status'],
    ['AI Localization', 'Translate one or many languages', 'Apply glossary and context', 'Choose model and provider', 'Resume interrupted jobs'],
    ['Validation & Repair', 'Preserve variables and syntax', 'Detect malformed output', 'Retry failed entries', 'Surface ambiguous text'],
    ['Review & Export', 'Show validation evidence', 'Keep human approval gates', 'Generate proofreading reports', 'Export installable packages'],
  ],
  zh: [
    ['项目与 Mod 管理', '识别游戏与语言', '导入本地 Mod', '检查文件和元数据', '追踪项目状态'],
    ['AI 本地化', '翻译一种或多种语言', '应用术语和上下文', '选择模型与 Provider', '恢复中断任务'],
    ['校验与修复', '保留变量和游戏语法', '发现畸形输出', '重试失败条目', '暴露歧义文本'],
    ['复核与导出', '展示校验证据', '保留人工审批门槛', '生成校对报告', '导出可安装包'],
  ],
}

const architecture = [
  ['Shared Agent Contract', 'Capabilities, operational rules, and safety boundaries', '能力发现、操作规则与安全边界'],
  ['Remis Local API', 'Stable structured interface', '稳定的结构化接口'],
  ['Remis Workflow Engine', 'Translation · validation · repair · persistence · review', '翻译 · 校验 · 修复 · 持久状态 · 复核'],
  ['Localized Mod', 'Installable, validated output', '可安装、已校验的输出'],
]

const agentTools = [
  ['Codex', '⌁'],
  ['Claude Code', '✦'],
  ['OpenClaw', '◌'],
  ['Cursor', '‹›'],
]

const safety = {
  en: [
    ['Localhost only', 'The Agent API stays on this machine.'],
    ['Keys stay in Remis', 'Codex never reads or displays provider secrets.'],
    ['Approval before spending', 'Paid model work starts only after a plan-specific approval.'],
    ['Approval before overwrite', 'Export targets and conflicts are previewed first.'],
    ['Validated outputs', 'Variables, syntax, encoding, and structure are checked.'],
    ['Audit trail', 'Plans, retries, repair, approvals, and recovery state persist locally.'],
    ['Release check first', 'Every workflow starts by checking the latest official GitHub Release.'],
  ],
  zh: [
    ['只监听本机', 'Agent API 只在这台机器上运行。'],
    ['密钥留在 Remis', 'Codex 不读取也不显示 Provider 密钥。'],
    ['花钱前批准', '付费模型任务必须先批准对应计划。'],
    ['覆盖前批准', '先展示导出目标和冲突，再决定是否写入。'],
    ['输出必须校验', '变量、语法、编码和结构都接受检查。'],
    ['操作可追踪', '计划、重试、修复、批准和恢复状态保存在本机。'],
    ['工作前检查版本', '每次工作流开始前都检查官方最新 GitHub Release。'],
  ],
}

export function CodexPage() {
  const { locale } = useI18n()
  const language = locale === 'zh' ? 'zh' : 'en'
  const text = copy[language]
  const [copyState, setCopyState] = useState('idle')

  async function handleCopy(openCodex) {
    const copyOperation = copyText(installPrompt)
    if (openCodex) {
      window.open(links.codex, '_blank', 'noopener,noreferrer')
    }
    try {
      await copyOperation
      setCopyState('copied')
    } catch {
      setCopyState('error')
    }
  }

  return (
    <SiteShell activePage="codex">
      <div className="codex-subnav" aria-label={text.use}>
        <div className="container">
          <a href={links.releases}>{text.download}</a>
          <a className="is-active" href={sitePath('codex/')}>{text.use}</a>
          <a href="#developers">{text.developers}</a>
        </div>
      </div>

      <section className="codex-hero">
        <div className="codex-hero__backdrop" aria-hidden="true" />
        <div className="container codex-hero__stage">
          <header className="codex-hero__copy">
            <p className="eyebrow">{text.eyebrow}</p>
            <h1 className="codex-display">{text.title}</h1>
            <p className="codex-lead">{text.lead}</p>
            <p className="codex-contract">{text.contract}</p>
            <p className="codex-body">{text.body}</p>
          </header>

          <div className="install-console">
            <div className="install-console__head">
              <span>{text.promptLabel}</span>
              <i>01 / 01</i>
            </div>
            <div className="install-console__instruction">
              <p>{text.install}</p>
              <code>{text.promptPreview}</code>
            </div>
            <button type="button" onClick={() => handleCopy(true)}>
              {copyState === 'copied' ? text.copied : text.copyButton}
              <span aria-hidden="true">↗</span>
            </button>
            <button className="copy-only" type="button" onClick={() => handleCopy(false)}>
              {copyState === 'error' ? 'Clipboard unavailable' : text.copyOnly}
            </button>
          </div>

          <div className="agent-rail" aria-label={text.agents}>
            <p>{text.agents}</p>
            <div className="agent-rail__tools">
              {agentTools.map(([name, mark], index) => (
                <span className={index === 0 ? 'is-featured' : ''} key={name}>
                  <i aria-hidden="true">{mark}</i>
                  <b>{name}</b>
                </span>
              ))}
              <span className="agent-rail__more">
                <i aria-hidden="true">＋</i>
                <b>{language === 'zh' ? '更多 Agent' : 'More agents'}</b>
              </span>
            </div>
            <small>{text.agentNote}</small>
          </div>
        </div>
      </section>

      <section className="codex-section codex-section--paper">
        <div className="container">
          <p className="eyebrow eyebrow--dark">{text.capabilityEyebrow}</p>
          <MeasuredText as="h2" className="codex-section-title">{text.capabilityTitle}</MeasuredText>
          <div className="conversation-grid">
            {conversations[language].map((item) => (
              <article className="conversation-card" key={item.tag}>
                <span>{item.tag}</span>
                <div><b>You</b><p>{item.user}</p></div>
                <div><b>Codex</b><p>{item.agent}</p></div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="codex-section codex-section--ink">
        <div className="container">
          <p className="eyebrow">{text.mapEyebrow}</p>
          <MeasuredText as="h2" className="codex-section-title">{text.mapTitle}</MeasuredText>
          <div className="capability-map">
            {capabilityGroups[language].map(([title, ...items], index) => (
              <article key={title}>
                <span>0{index + 1}</span>
                <h3>{title}</h3>
                <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="codex-section codex-architecture">
        <div className="container">
          <p className="eyebrow">{text.architectureEyebrow}</p>
          <MeasuredText as="h2" className="codex-section-title">{text.architectureTitle}</MeasuredText>
          <div className="control-surfaces">
            <article>
              <span>{text.insideLabel}</span>
              <h3>{text.insideTitle}</h3>
              <p>{text.insideBody}</p>
            </article>
            <i aria-hidden="true">＋</i>
            <article>
              <span>{text.outsideLabel}</span>
              <h3>{text.outsideTitle}</h3>
              <p>{text.outsideBody}</p>
            </article>
          </div>
          <div className="control-plane">
            {architecture.map(([name, english, chinese], index) => (
              <div key={name}>
                <span>0{index + 1}</span>
                <strong>{name}</strong>
                <p>{language === 'zh' ? chinese : english}</p>
              </div>
            ))}
          </div>
          <blockquote>
            <strong>Codex is the natural-language control plane.</strong>
            <span>Remis is the reliable execution plane.</span>
          </blockquote>
        </div>
      </section>

      <section className="codex-section codex-section--paper">
        <div className="container">
          <p className="eyebrow eyebrow--dark">{text.safetyEyebrow}</p>
          <MeasuredText as="h2" className="codex-section-title">{text.safetyTitle}</MeasuredText>
          <div className="safety-cards">
            {safety[language].map(([title, body]) => (
              <article key={title}><span aria-hidden="true">✓</span><h3>{title}</h3><p>{body}</p></article>
            ))}
          </div>
        </div>
      </section>

      <section id="developers" className="codex-section codex-developers">
        <div className="container developer-callout">
          <div>
            <p className="eyebrow">{text.developerEyebrow}</p>
            <MeasuredText as="h2" className="codex-section-title">{text.developerTitle}</MeasuredText>
          </div>
          <div className="developer-links">
            <a href={links.agentSkill} target="_blank" rel="noreferrer">{text.skill}<span>↗</span></a>
            <a href={links.agentQuickstart} target="_blank" rel="noreferrer">{text.quickstart}<span>↗</span></a>
            <a href={links.agentApi}>{text.api}<span>→</span></a>
          </div>
        </div>
      </section>
    </SiteShell>
  )
}
