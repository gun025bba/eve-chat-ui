import type { FeedbackMessage } from '../../api/feedback.js';
import type { MemoryRef } from './memory-chips.js';
import type { createMessageParts } from './parts.js';
import type { createTimeline } from './timeline.js';
import type { Note } from './tool-note.js';
export type MessageModel = FeedbackMessage & {
  role?: string;
  content?: string;
  status?: string;
  errorCode?: string | null;
  origin?: string;
  sources?: unknown;
  memoryRefs?: MemoryRef[];
  fresh?: unknown;
  tools?: unknown;
};
export type ToolInfo = { tools?: unknown; note?: Note | null };
export interface Bubble extends HTMLElement {
  _streamed?: boolean;
  _live?: boolean;
  _sources?: unknown;
  _tline?: HTMLElement | null;
  _tsDrop?: (() => void) | null;
  _freshAt?: number;
  _ti?: ToolInfo | null;
}
export type RenderOptions = {
  live?: boolean;
  slow?: boolean;
  resuming?: boolean;
  thinkSecs?: number;
  usage?: string;
  regen?: boolean;
  msg?: MessageModel;
  stopped?: boolean;
  sources?: unknown;
  actions?: boolean;
};
export type RenderHost = {
  box: HTMLElement;
  parts: ReturnType<typeof createMessageParts>;
  timeline: ReturnType<typeof createTimeline>;
  showThink: () => boolean;
  memoryActive: () => boolean;
  isServer: () => boolean;
  nextSourceId: () => string;
  feedbackAttach: (actions: HTMLElement, message: FeedbackMessage) => void;
  feedbackDetach: (actions: HTMLElement) => void;
  feedbackClear: () => void;
  memoryClick: (id: string) => void;
  regenerate: () => void;
  isStop: (code?: string | null) => boolean;
  failText: (code?: string | null) => string;
  stoppedText: string;
  resumingText: string;
};
