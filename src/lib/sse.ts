export type SSEHandler = (data: string, event: string | null, id: string | null) => void;

export function createSSEParser(onData: SSEHandler) {
  let buffer = '';
  const push = (chunk: string) => {
    buffer += chunk;
    let boundary = buffer.search(/\r?\n\r?\n/);
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary).replace(/^\r?\n\r?\n/, '');
      const lines = block.split(/\r?\n/);
      const field = (key: string) => {
        const line = lines.filter((value) => value.startsWith(`${key}:`)).pop();
        return line == null ? null : line.slice(key.length + 1).replace(/^ /, '');
      };
      const data = lines
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).replace(/^ /, ''))
        .join('\n');
      if (data) onData(data, field('event'), field('id'));
      boundary = buffer.search(/\r?\n\r?\n/);
    }
  };
  return {
    push,
    flush() {
      if (buffer.trim()) {
        const tail = buffer;
        buffer = '';
        this.push(`${tail}\n\n`);
      }
    },
  };
}
