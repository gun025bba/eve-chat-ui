export function createOperations(api) {
  async function runOp(o) {
    const p = o.payload,
      id = encodeURIComponent(p.id);
    if (o.op === 'feedback')
      return p.rating
        ? api(`/v1/messages/${id}/feedback`, {
            method: 'PUT',
            body: JSON.stringify({ rating: p.rating, reasons: p.reasons || [], comment: p.comment || '' }),
          })
        : api(`/v1/messages/${id}/feedback`, { method: 'DELETE' });
    if (o.op === 'patch') return api(`/v1/threads/${id}`, { method: 'PATCH', body: JSON.stringify(p.patch) });
    if (o.op === 'archive') return api(`/v1/threads/${id}`, { method: 'DELETE' });
    if (o.op === 'readThread')
      return api(`/v1/threads/${id}/read`, { method: 'POST', body: '{}' }).catch((e) => {
        if (e.http === 404) return null;
        throw e;
      }); // CT Q6
    if (o.op === 'read')
      return api(`/v1/messages/${id}/read`, { method: 'POST', body: '{}' }).catch((e) => {
        if (e.http === 404) return null;
        throw e;
      }); // 선톡 읽음 (spec A3.3)
  }
  return runOp;
}
