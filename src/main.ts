import './app/shell.js';
import memoryAPI from './api/memory.js';
import createProactiveAPI from './api/proactive.js';
import briefing from './features/briefing/index.js';
import createMemory from './features/memory/index.js';
import pim from './features/pim/index.js';
import createProactive from './features/proactive/index.js';
import { mountToast } from './features/toast/index.js';
import today from './features/today/index.js';
import { boot, browserHelpers } from './legacy/app.js';

const proactiveAPI = createProactiveAPI({ cleanBriefing: pim.cleanBriefing });
const proactive = createProactive({ proactiveAPI, pim, briefing });
const memory = createMemory({ memoryAPI });

// Preserve existing browser test contracts; production modules use imports or injected dependencies.
Object.assign(globalThis, browserHelpers, { EvePim: pim, EveProactiveAPI: proactiveAPI });
const toastRoot = document.getElementById('toastRoot');
if (!toastRoot) throw new Error('Missing toast mount');
const toast = mountToast(toastRoot);
boot({ Toast: toast, ProactiveAPI: proactiveAPI, Proactive: proactive, Pim: pim, Memory: memory, Today: today });
