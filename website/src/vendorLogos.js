import { assetPath } from './site'

const definitions = {
  alibaba: ['Alibaba', 'alibaba.png'],
  'allen-ai': ['Allen AI', 'allen-ai.png'],
  anthropic: ['Anthropic', 'anthropic.svg'],
  'arcee-ai': ['Arcee AI', 'arcee-ai.png'],
  chutes: ['Chutes', 'chutes.png'],
  cursor: ['Cursor', 'cursor.svg'],
  deepseek: ['DeepSeek', 'deepseek.png'],
  designflow: ['DesignFlow', 'designflow.png'],
  google: ['Google', 'google.png'],
  'hermes-agent': ['Hermes Agent', 'hermes-agent.png'],
  'inception-labs': ['Inception Labs', 'inception-labs.png'],
  inclusionai: ['InclusionAI', 'inclusionai.png'],
  meta: ['Meta', 'meta.png'],
  minimax: ['MiniMax', 'minimax.png'],
  'mistral-ai': ['Mistral AI', 'mistral-ai.png'],
  'moonshot-ai': ['Moonshot AI', 'moonshot-ai.png'],
  'nex-agi': ['Nex AGI', 'nex-agi.svg'],
  nvidia: ['NVIDIA', 'nvidia.png'],
  openai: ['OpenAI', 'openai.png'],
  openclaw: ['OpenClaw', 'openclaw.svg'],
  'prime-intellect': ['Prime Intellect', 'prime-intellect.png'],
  quiver: ['Quiver', 'quiver.png'],
  recraft: ['Recraft', 'recraft.png'],
  stepfun: ['StepFun', 'stepfun.png'],
  tencent: ['Tencent', 'tencent.png'],
  xai: ['xAI', 'xai.svg'],
  xiaomi: ['Xiaomi', 'xiaomi.png'],
}

export const vendorLogos = Object.freeze(Object.fromEntries(
  Object.entries(definitions).map(([id, [label, file]]) => [
    id,
    Object.freeze({
      id,
      label,
      file,
      src: assetPath(`vendors/${file}`),
    }),
  ]),
))

export function getVendorLogo(vendorId) {
  return vendorLogos[vendorId] ?? null
}
