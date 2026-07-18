import { useState } from 'react'
import { MeasuredText } from '../components/MeasuredText'
import { SiteShell } from '../components/SiteShell'
import { useI18n } from '../i18n/context'
import { links, sitePath } from '../site'
import { copyText, installPrompt } from './codexPrompt'

const copy = {
  en: {
    eyebrow: 'REMIS FOR CODEX · LOCAL-FIRST AGENT OPERATIONS',
    title: 'Turn Codex into a production game-localization operator.',
    lead: 'Translate mods · preserve game syntax · validate every output',
    body: 'Remis combines AI translation, terminology control, format validation, repair workflows, persistence, and human review in one local application. Codex gives you a natural-language way to operate it.',
    install: 'Install once. Localize with any AI agent.',
    promptLabel: 'COPY THIS TO CODEX',
    copyButton: 'Copy and open Codex',
    copied: 'Prompt copied. Opening Codex…',
    copyOnly: 'Copy prompt',
    agents: 'Works as an operator guide for',
    capabilityEyebrow: 'CODEX CAN MAKE REMIS DO',
    capabilityTitle: 'A complete workflow, explained as real conversations.',
    mapEyebrow: 'CAPABILITY MAP',
    mapTitle: 'The cards are product capabilities. The Skill is the connector.',
    architectureEyebrow: 'EXECUTION ARCHITECTURE',
    architectureTitle: 'Natural-language planning above a deterministic workflow.',
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
    eyebrow: 'REMIS FOR CODEX · 本地优先的 AGENT 操作层',
    title: '把 Codex 变成真正能交付的游戏汉化操作员。',
    lead: '汉化 Mod · 保留游戏语法 · 校验每一份输出',
    body: 'Remis 把 AI 翻译、术语控制、格式校验、修复工作流、持久状态和人工复核放进同一个本地程序。Codex 则让你用自然语言操作这套完整能力。',
    install: '安装一次，就能让任何 AI Agent 操作 Remis。',
    promptLabel: '把这段话复制给 CODEX',
    copyButton: '复制并打开 Codex',
    copied: '已复制，正在打开 Codex…',
    copyOnly: '只复制提示词',
    agents: '可作为以下 Agent 的操作说明',
    capabilityEyebrow: 'CODEX 能让 REMIS 做什么',
    capabilityTitle: '用真实对话理解完整工作流。',
    mapEyebrow: '能力地图',
    mapTitle: '卡片代表 Remis 的产品能力，Skill 只是连接器。',
    architectureEyebrow: '执行架构',
    architectureTitle: '自然语言负责计划，确定性工作流负责交付。',
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
      tag: '01 · INSTALL',
      user: 'Install Remis and check whether it is ready.',
      agent: 'Remis is running locally. API health: OK. A newer official Release was checked. No provider key is configured yet—open Remis API Settings first. I can explain what an API key is. Never paste it here.',
    },
    {
      tag: '02 · LOCALIZE',
      user: 'Translate this Victoria 3 mod to Simplified Chinese. Use the glossary and preserve every variable.',
      agent: 'Detected 24 localization files and 3,842 entries. A translation plan is ready. It may use paid model credits—approve before I start?',
    },
    {
      tag: '03 · REPAIR',
      user: 'Check failed entries and repair anything safe to fix.',
      agent: '12 entries failed validation. 9 are safe repair candidates. 3 remain for human review because the source is ambiguous. Approve model-backed repair?',
    },
    {
      tag: '04 · EXPORT',
      user: 'Validate everything and prepare the final mod.',
      agent: 'Errors: 0 · Warnings: 3 · Untranslated: 0 · Variables: passed. Export would overwrite an existing folder. Approve this exact target?',
    },
  ],
  zh: [
    {
      tag: '01 · 安装',
      user: '安装 Remis，检查它是否已经可以使用。',
      agent: 'Remis 已在本机运行，API 健康检查正常，并已检查官方最新 Release。目前还没有配置 Provider 密钥，请先打开 Remis API 设置。如果你不清楚什么是 API key，我可以解释；不要把密钥贴进对话。',
    },
    {
      tag: '02 · 汉化',
      user: '把这个 Victoria 3 Mod 汉化成简体中文，使用已有术语库，并保留所有变量。',
      agent: '检测到 24 个本地化文件、3,842 个条目。翻译计划已准备好，可能产生模型费用。是否批准开始？',
    },
    {
      tag: '03 · 修复',
      user: '检查失败条目，把能安全修复的内容修好。',
      agent: '12 个条目未通过校验，其中 9 个可以安全尝试修复；3 个因原文有歧义而保留给人工复核。是否批准模型修复？',
    },
    {
      tag: '04 · 导出',
      user: '完成校验并准备最终 Mod。',
      agent: '错误：0 · 警告：3 · 未翻译：0 · 变量校验：通过。导出会覆盖已有目录，是否批准这个确切目标？',
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
  ['Codex', 'Natural-language planning and interaction', '自然语言计划与交互'],
  ['Remis Skill', 'Operational rules, safety boundaries, and API guidance', '操作规则、安全边界与 API 指南'],
  ['Remis Local API', 'Stable structured interface', '稳定的结构化接口'],
  ['Remis Workflow Engine', 'Translation · validation · repair · persistence · review', '翻译 · 校验 · 修复 · 持久状态 · 复核'],
  ['Localized Mod', 'Installable, validated output', '可安装、已校验的输出'],
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
        <div className="container codex-hero__grid">
          <div className="codex-hero__copy">
            <p className="eyebrow">{text.eyebrow}</p>
            <MeasuredText as="h1" className="codex-display">{text.title}</MeasuredText>
            <p className="codex-lead">{text.lead}</p>
            <p className="codex-body">{text.body}</p>
            <div className="agent-chips" aria-label={text.agents}>
              <span>{text.agents}</span>
              <b>Codex</b><b>Claude Code</b><b>OpenClaw</b>
            </div>
          </div>

          <div className="install-console">
            <div className="install-console__head">
              <span>{text.promptLabel}</span>
              <i>localhost:1453</i>
            </div>
            <p>{text.install}</p>
            <pre><code>{installPrompt}</code></pre>
            <button type="button" onClick={() => handleCopy(true)}>
              {copyState === 'copied' ? text.copied : text.copyButton}
              <span aria-hidden="true">↗</span>
            </button>
            <button className="copy-only" type="button" onClick={() => handleCopy(false)}>
              {copyState === 'error' ? 'Clipboard unavailable' : text.copyOnly}
            </button>
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
