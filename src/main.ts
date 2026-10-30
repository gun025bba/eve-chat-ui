// R0 keeps the legacy boot and its public hooks intact; R1 extracts typed helpers.
import legacy from './legacy/app.js';

// Existing browser tests call these classic-script helpers; R1 moves them to module tests.
Object.assign(globalThis, legacy);
