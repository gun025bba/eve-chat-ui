import './app/shell.js';
import memoryAPI from './api/memory.js';
import createProactiveAPI from './api/proactive.js';
import { mountAuth } from './features/auth/index.js';
import briefing from './features/briefing/index.js';
import { mountRename } from './features/conversations/rename.js';
import { mountInstall } from './features/install/index.js';
import createMemory from './features/memory/index.js';
import { mountMigration } from './features/migration/index.js';
import pim from './features/pim/index.js';
import createProactive from './features/proactive/index.js';
import { mountSettings } from './features/settings/index.js';
import { mountToast } from './features/toast/index.js';
import today from './features/today/index.js';
import { boot, browserHelpers } from './legacy/app.js';
import { createMiniSheets } from './shared/mini-sheets.js';

const proactiveAPI = createProactiveAPI({ cleanBriefing: pim.cleanBriefing });
const proactive = createProactive({ proactiveAPI, pim, briefing });
const memory = createMemory({ memoryAPI });

// Preserve existing browser test contracts; production modules use imports or injected dependencies.
Object.assign(globalThis, browserHelpers, { EvePim: pim, EveProactiveAPI: proactiveAPI });
const settingsRoot = document.getElementById('settingsRoot');
if (!settingsRoot) throw new Error('Missing settings mount');
mountSettings(settingsRoot);
const toastRoot = document.getElementById('toastRoot');
if (!toastRoot) throw new Error('Missing toast mount');
const toast = mountToast(toastRoot);
const renameRoot = document.getElementById('renameRoot');
if (!renameRoot) throw new Error('Missing rename mount');
const sheets = createMiniSheets();
const rename = mountRename(renameRoot, sheets);
const installRoot = document.getElementById('installRoot');
if (!installRoot) throw new Error('Missing install mount');
const install = mountInstall(installRoot);
const authRoot = document.getElementById('authRoot');
if (!authRoot) throw new Error('Missing auth mount');
const auth = mountAuth(authRoot);
const migrationRoot = document.getElementById('migrateSheet');
if (!migrationRoot) throw new Error('Missing migration mount');
const migration = mountMigration(migrationRoot, sheets);
boot({
  Migration: migration,
  Auth: auth,
  Install: install,
  Sheets: sheets,
  Rename: rename,
  Toast: toast,
  ProactiveAPI: proactiveAPI,
  Proactive: proactive,
  Pim: pim,
  Memory: memory,
  Today: today,
});
