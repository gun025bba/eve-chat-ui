export function el<K extends keyof HTMLElementTagNameMap>(tag: K, className?: string, text?: unknown) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text != null) element.textContent = text as string;
  return element;
}
