export function createOutbox(options) {
  const state = { items: options.load(options.storageKey, []), timer: 0, failed: 0 };
  const context = { ...options, state };
  context.saveOutbox = () => options.save(options.storageKey, state.items);
  context.scheduleOutbox = (delay) => {
    clearTimeout(state.timer);
    state.timer = setTimeout(context.flushOutbox, delay);
  };
  context.enqueue = (op, key, payload) => enqueue(context, op, key, payload);
  context.flushOutbox = () => flush(context);
  context.write = (...args) => write(context, ...args);
  setInterval(() => {
    if (state.items.length) context.flushOutbox();
  }, 30000);
  return {
    state,
    saveOutbox: context.saveOutbox,
    scheduleOutbox: context.scheduleOutbox,
    enqueue: context.enqueue,
    flushOutbox: context.flushOutbox,
    write: context.write,
  };
}

function enqueue(context, op, key, payload) {
  const state = context.state;
  state.items = state.items.filter((item) => item.key !== key);
  state.items.push({ op, key, payload, tries: 0, nextAt: 0 });
  context.saveOutbox();
  context.renderSync();
  context.scheduleOutbox(0);
}

function rejected(context, operation, error) {
  if (context.isNet(error) || error.http >= 500 || error.http === 429) {
    operation.tries++;
    operation.nextAt = Date.now() + Math.min(60, 2 ** operation.tries) * 1000;
  } else if (operation.op === 'feedback' && error.code === 'feedback_comment_too_long' && operation.payload.comment) {
    operation.payload = { ...operation.payload, comment: operation.payload.comment.trim().slice(0, 139) };
    operation.tries = 0;
    operation.nextAt = 0;
  } else if (
    operation.op === 'feedback' &&
    error.code === 'invalid_feedback_reason' &&
    operation.payload.reasons?.length
  ) {
    operation.payload = { ...operation.payload, reasons: [] };
    operation.tries = 0;
    operation.nextAt = 0;
    context.fbReasonRejected(operation.payload.id);
  } else {
    context.state.items = context.state.items.filter((item) => item !== operation);
    context.state.failed++;
    operation.onFail?.();
  }
}

async function flush(context) {
  if (context.mode() !== 'server' || context.flushOutbox.busy) return;
  context.flushOutbox.busy = true;
  try {
    for (const operation of [...context.state.items]) {
      if (operation.nextAt > Date.now()) continue;
      try {
        await context.runOp(operation);
        context.state.items = context.state.items.filter((item) => item !== operation);
      } catch (error) {
        rejected(context, operation, error);
      }
    }
  } finally {
    context.flushOutbox.busy = false;
    context.saveOutbox();
    context.renderSync();
  }
  const next = context.state.items.reduce((earliest, item) => Math.min(earliest, item.nextAt), Infinity);
  if (next < Infinity) context.scheduleOutbox(Math.max(500, next - Date.now()));
}

async function write(context, op, key, payload, rollback, failText) {
  if (context.mode() !== 'server') return;
  try {
    await context.runOp({ op, payload });
    context.state.items = context.state.items.filter((item) => item.key !== key);
    context.saveOutbox();
    context.renderSync();
  } catch (error) {
    if (context.isNet(error) || error.http >= 500 || error.http === 429) return context.enqueue(op, key, payload);
    if (rollback?.(error) === 'handled') return;
    context.showToast(
      failText || '저장하지 못했어요',
      '다시 시도',
      () => context.write(op, key, payload, rollback, failText),
      4000,
    );
  }
}
