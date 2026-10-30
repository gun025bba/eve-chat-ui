import { render } from 'preact';
import { Connection, ConversationOptions, Header } from './basic.js';
import { Footer } from './footer.js';
import { MemorySettings } from './memory-frame.js';
import { ProactiveOptions } from './proactive.js';

function SettingsDialog() {
  return (
    <dialog id="settings">
      <form id="settingsForm" method="dialog" autoComplete="off" data-form-type="other">
        <Header />
        <Connection />
        <ConversationOptions />
        <ProactiveOptions />
        <MemorySettings />
        <Footer />
      </form>
    </dialog>
  );
}
export function mountSettings(root: Element) {
  render(<SettingsDialog />, root);
}
