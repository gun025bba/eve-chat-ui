import { MD_LI, mdInd } from './markdown-blocks.js';

function afterList(head: string): boolean {
  const lines = head.replace(/\t/g, '    ').split('\n');
  let index = lines.length - 1;
  while (index >= 0 && !lines[index].trim()) index--;
  for (; index >= 0; index--) {
    const line = lines[index];
    if (!line.trim()) {
      let previous = index;
      while (previous >= 0 && !lines[previous].trim()) previous--;
      if (previous < 0) return false;
      const priorLine = lines[previous];
      if (MD_LI.test(priorLine) || mdInd(priorLine) >= 2) {
        index = previous + 1;
        continue;
      }
      return false;
    }
    if (MD_LI.test(line) || mdInd(line) >= 2) return true;
    if (line.includes('```')) return false;
  }
  return false;
}

export function stableCut(source: string): number {
  let index = source.lastIndexOf('\n\n', source.length - 1);
  while (index >= 0) {
    const head = source.slice(0, index);
    if ((head.match(/```/g) || []).length % 2 === 0 && !afterList(head)) return index + 2;
    if (index === 0) break;
    index = source.lastIndexOf('\n\n', index - 1);
  }
  return 0;
}
