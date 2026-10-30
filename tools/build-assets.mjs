import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { posix } from 'node:path';

export const legacyPath = (name) => (existsSync(`src/legacy/${name}`) ? `src/legacy/${name}` : name);

export function filesIn(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const name = posix.join(dir, entry.name);
    return entry.isDirectory() ? filesIn(name) : [name];
  });
}

export function legacyAssets(version) {
  return {
    name: 'eve-legacy-assets',
    transform(code, id) {
      if (id.endsWith('/app.js'))
        return code.replace("const APP_VERSION = '__EVE_VERSION__'", `const APP_VERSION = '${version}'`);
    },
    generateBundle(_options, bundle) {
      const fixed = JSON.parse(readFileSync('tools/deploy-files.json', 'utf8'));
      for (const fileName of fixed.filter((name) => !['app.js', 'sw.js'].includes(name))) {
        let source = readFileSync(legacyPath(fileName));
        if (fileName.endsWith('.html'))
          source = source.toString().replace(/\?v=(?:__EVE_VERSION__|16)/g, `?v=${version}`);
        this.emitFile({ type: 'asset', fileName, source });
      }
      const names = [...new Set([...fixed, ...Object.keys(bundle)])].sort();
      const assets = names.filter((name) => /\.(js|css)$/.test(name) && name !== 'sw.js');
      const shell = names.filter((name) => !assets.includes(name) && name !== 'sw.js');
      const worker = readFileSync('sw.js', 'utf8')
        .replace(/const CACHE = .*;/, `const CACHE = 'llmchat-${version}';`)
        .replace(/const ASSETS = .*;/, `const ASSETS = ${JSON.stringify(assets)}.map(f => \`\${f}?v=\${VER}\`);`)
        .replace(/const SHELL = \[[\s\S]*?\];/, `const SHELL = [...ASSETS, ...${JSON.stringify(shell)}];`);
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: worker });
    },
  };
}
