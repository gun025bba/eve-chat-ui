export interface ThinkParts {
  think: string | null;
  answer: string;
  thinking: boolean;
}

export function splitThink(text: string): ThinkParts {
  const match = text.match(/^\s*<think>([\s\S]*?)(<\/think>|$)([\s\S]*)$/);
  if (!match) return { think: null, answer: text, thinking: false };
  return { think: match[1].trim(), answer: match[3].replace(/^\s+/, ''), thinking: match[2] === '' };
}

const STOP_RE = /\n*\*\(중지됨\)\*\s*$/;
export function stripStopMark(value: unknown): string {
  return String(value || '').replace(STOP_RE, '');
}
