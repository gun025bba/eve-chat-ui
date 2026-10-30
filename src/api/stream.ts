// Cancellation can reject after fetch aborts (notably WebKit); synchronous catch alone cannot handle it.
export function cancelReader(reader: { cancel: () => Promise<unknown> } | null) {
  try {
    reader?.cancel().catch(() => {});
  } catch {}
}
