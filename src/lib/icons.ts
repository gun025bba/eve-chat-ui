export function icon(name: string, className = ''): string {
  return `<svg class="i${className ? ` ${className}` : ''}" aria-hidden="true">` + `<use href="#i-${name}"/></svg>`;
}
export const COPY_SVG = icon('copy');
