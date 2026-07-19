const SECRET_RE = /\b(api[_-]?key|token|authorization|secret)\b\s*[:=]\s*[^\s,;]+/gi;
const WINDOWS_PATH_RE = /\b[A-Za-z]:\\[^\r\n]*/g;

export function sanitizeCopilotLogLine(value, maxLength = 500) {
  return String(value ?? '')
    .replace(SECRET_RE, '$1=[REDACTED]')
    .replace(WINDOWS_PATH_RE, '[LOCAL_PATH]')
    .slice(0, maxLength);
}
