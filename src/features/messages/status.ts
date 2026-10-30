import type { RenderHost, RenderOptions } from './models.js';
export function messageStatus(answer: string, think: string | null, options: RenderOptions, host: RenderHost) {
  const message = options.msg,
    live = !!options.live;
  const oldFail = message?.status === 'incomplete' && message.errorCode && !host.isStop(message.errorCode);
  const emptyDone =
    !live &&
    !options.stopped &&
    message &&
    message.role !== 'user' &&
    !answer.trim() &&
    think === null &&
    (!message.status || message.status === 'complete');
  const failed = !live && ((message?.status === 'failed' && !host.isStop(message.errorCode)) || oldFail || emptyDone);
  if (
    !live &&
    !failed &&
    (options.stopped ||
      message?.status === 'incomplete' ||
      (message?.status === 'failed' && host.isStop(message.errorCode)))
  )
    return { cls: 'stopped', role: 'note' as const, text: host.stoppedText, retry: !!options.regen };
  if (failed)
    return {
      cls: 'stopped msg-note failed',
      role: 'note' as const,
      text: emptyDone && !message?.errorCode ? '답변을 받지 못했어요' : host.failText(message?.errorCode),
      retry: !!options.regen,
    };
  if (message?.status === 'generating' || options.resuming)
    return { cls: 'stopped msg-note resuming', role: 'status' as const, text: host.resumingText, retry: false };
  return null;
}
