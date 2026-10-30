import { readdirSync, readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';

export function measure(name, text) {
  const lines = text.trimEnd().split('\n');
  let functions = 0;
  let innerHTML = 0;
  if (/\.[cm]?[jt]sx?$/.test(name)) {
    const source = ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true);
    const visit = (node) => {
      if (
        ts.isBinaryExpression(node) &&
        node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment &&
        node.operatorToken.kind <= ts.SyntaxKind.LastAssignment
      ) {
        const left = node.left;
        if (
          (ts.isPropertyAccessExpression(left) && left.name.text === 'innerHTML') ||
          (ts.isElementAccessExpression(left) && left.argumentExpression?.text === 'innerHTML')
        )
          innerHTML++;
      }
      if (ts.isFunctionLike(node) && node.body) {
        const start = source.getLineAndCharacterOfPosition(node.getStart(source)).line;
        const end = source.getLineAndCharacterOfPosition(node.end).line;
        functions += Math.max(0, end - start + 1 - 60);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
  return {
    lines: Math.max(0, lines.length - 300),
    longLines: lines.filter((line) => line.length > 120).length,
    functions,
    innerHTML,
    important: name.endsWith('.css') ? (text.match(/!important\b/g) || []).length : 0,
  };
}

export function scan(dir = '.') {
  const metrics = {};
  const walk = (folder) => {
    const entries = readdirSync(folder, { withFileTypes: true }).filter((entry) => !entry.name.startsWith('.'));
    const files = entries.filter((entry) => entry.isFile());
    metrics[`${folder}/`] = { files: Math.max(0, files.length - 12) };
    for (const entry of entries) {
      const path = folder === '.' ? entry.name : `${folder}/${entry.name}`;
      if (entry.isDirectory() && ['src', 'styles', 'tools'].includes(path.split('/')[0])) walk(path);
      if (entry.isFile() && /\.(?:[cm]?[jt]sx?|css|html)$/.test(path)) {
        metrics[path] = measure(path, readFileSync(path, 'utf8'));
      }
    }
  };
  walk(dir);
  return Object.fromEntries(Object.entries(metrics).filter(([, values]) => Object.values(values).some(Boolean)));
}

export function violations(current, baseline) {
  return Object.entries(current).flatMap(([name, values]) =>
    Object.entries(values)
      .filter(([metric, value]) => value > (baseline[name]?.[metric] || 0))
      .map(([metric, value]) => `${name}: ${metric} ${value} > ${baseline[name]?.[metric] || 0}`),
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const baseline = JSON.parse(readFileSync('tools/size-allowlist.json', 'utf8'));
  const current = scan();
  const errors = violations(current, baseline);
  console.log(`Ratchet: ${JSON.stringify(current)}`);
  if (errors.length) throw new Error(errors.join('\n'));
}
