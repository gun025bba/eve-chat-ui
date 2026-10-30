import type { ComponentChildren } from 'preact';
// Only exact <mark> tokens are syntax. Every other byte remains a JSX text node.
export function Snippet({ text }: { text?: string }) {
  const children: ComponentChildren[] = [];
  const stack = [children];
  for (const token of String(text || '').split(/(<\/?mark>)/)) {
    if (token === '<mark>') {
      const nested: ComponentChildren[] = [];
      stack[stack.length - 1].push(<mark>{nested}</mark>);
      stack.push(nested);
    } else if (token === '</mark>') {
      if (stack.length > 1) stack.pop();
    } else stack[stack.length - 1].push(token);
  }
  return <>{children}</>;
}
