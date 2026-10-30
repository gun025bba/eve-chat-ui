import { existsSync, readFileSync } from 'node:fs';
import { dirname, posix, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import { filesIn } from './build-assets.mjs';

const ranks = { lib: 0, shared: 1, api: 2, features: 3, app: 4 };
export function missingNames(paths) {
  const roots = new Set(paths.map((name) => resolve(name)));
  const program = ts.createProgram(paths, {
    allowJs: true,
    checkJs: true,
    noEmit: true,
    types: [],
    skipLibCheck: true,
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
  });
  return (
    program
      .getSemanticDiagnostics()
      .filter((diagnostic) => diagnostic.code === 2304 && roots.has(resolve(diagnostic.file.fileName)))
      .map((diagnostic) => ts.flattenDiagnosticMessageText(diagnostic.messageText, ' '))
      // Existing classic global; R2 replaces this final ambient name with injected modules.
      .filter((message) => message !== "Cannot find name 'EvePim'.")
  );
}
export function checkImports(sources) {
  const errors = [];
  const graph = new Map();
  for (const [name, code] of Object.entries(sources)) {
    const source = ts.createSourceFile(name, code, ts.ScriptTarget.Latest, true);
    const from = name.split('/');
    const edges = [];
    const visit = (node) => {
      if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
        errors.push(`${name}: dynamic import is forbidden (old-tab safety)`);
      }
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'require') {
        errors.push(`${name}: use static ES imports`);
      }
      const specifier = (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier;
      if (specifier && ts.isStringLiteral(specifier) && specifier.text.startsWith('.')) {
        const target = posix.normalize(posix.join(dirname(name), specifier.text));
        const found = [target, target.replace(/\.js$/, '.ts'), `${target}.ts`, `${target}/index.ts`].find(
          (candidate) => candidate in sources || existsSync(candidate),
        );
        if (!found) errors.push(`${name}: unresolved ${target}`);
        const to = (found || target).split('/');
        if (from[1] in ranks && (to[0] !== 'src' || !(to[1] in ranks))) {
          errors.push(`${name}: dependency outside the architecture layers ${target}`);
        }
        if (ranks[to[1]] > ranks[from[1]]) errors.push(`${name}: upward dependency ${target}`);
        if (from[1] === 'features' && to[1] === 'features' && from[2] !== to[2]) {
          errors.push(`${name}: cross-feature dependency ${target}`);
        }
        edges.push(found || target);
      }
      if (
        from[1] === 'lib' &&
        ts.isIdentifier(node) &&
        /^(document|window|navigator|fetch|XMLHttpRequest|WebSocket)$/.test(node.text)
      ) {
        errors.push(`${name}: impure lib reference ${node.text}`);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
    graph.set(name, edges);
  }
  const done = new Set();
  const walk = (name, path = []) => {
    if (path.includes(name)) return errors.push(`Import cycle: ${[...path, name].join(' -> ')}`);
    if (done.has(name)) return;
    for (const edge of graph.get(name) || []) walk(edge, [...path, name]);
    done.add(name);
  };
  for (const name of graph.keys()) walk(name);
  return errors;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const sources = Object.fromEntries(filesIn('src').map((name) => [name, readFileSync(name, 'utf8')]));
  const errors = checkImports(sources);
  errors.push(...missingNames(filesIn('src').filter((name) => name.endsWith('.js'))));
  if (errors.length) throw new Error(errors.join('\n'));
  console.log(`Import gate: ${Object.keys(sources).length} sources, no cycles or boundary violations`);
}
