type Conversation = { id: string; fresh?: boolean; archived?: boolean };
type State<C> = { mode: 'server' | 'local'; convs: C[]; archivedList: C[]; currentId: string | null };
type Host<C> = {
  state: State<C>;
  abort: (id: string) => void;
  current: () => C | undefined;
  loadDraft: () => void;
  removeDraft: (id: string) => void;
  persist: () => void;
  renderAll: () => void;
  renderList: () => void;
  renderArchive: () => void;
  renderMessages: () => void;
  expand: (id: string) => void;
  buzz: (duration: number) => void;
  hideToast: () => void;
  showToast: (text: string, action: string, callback: (() => void) | null, ms: number) => void;
  write: (
    operation: string,
    key: string,
    payload: { id: string; patch?: { archived: boolean } },
    rollback: () => void,
    message: string,
  ) => unknown;
};
class Archive<C extends Conversation> {
  private pending: { conversation: C; index: number; timer: ReturnType<typeof setTimeout> } | null = null;
  constructor(private host: Host<C>) {}
  commit = () => {
    const pending = this.pending;
    if (!pending) return;
    this.pending = null;
    clearTimeout(pending.timer);
    const { state, write, persist, renderList } = this.host;
    const { conversation, index } = pending;
    if (state.mode === 'server' && !conversation.fresh)
      write(
        'archive',
        `archive:${conversation.id}`,
        { id: conversation.id },
        () => {
          state.convs.splice(Math.min(index, state.convs.length), 0, conversation);
          conversation.archived = false;
          persist();
          renderList();
        },
        '보관하지 못했어요',
      );
    else if (state.mode === 'local') {
      conversation.archived = true;
      if (!state.convs.includes(conversation)) state.convs.splice(Math.min(index, state.convs.length), 0, conversation);
      persist();
    }
  };
  archive = (conversation: C) => {
    if (this.pending) this.commit();
    const { state, abort, loadDraft, persist, renderAll, buzz, showToast, hideToast } = this.host;
    abort(conversation.id);
    const index = state.convs.indexOf(conversation);
    if (index < 0) return;
    state.convs.splice(index, 1);
    conversation.archived = true;
    if (state.currentId === conversation.id) {
      state.currentId = state.convs.find((item) => !item.archived)?.id || null;
      loadDraft();
    }
    persist();
    renderAll();
    buzz(15);
    this.pending = {
      conversation,
      index,
      timer: setTimeout(() => {
        hideToast();
        this.commit();
      }, 2800),
    };
    showToast('보관됨', '되돌리기', () => this.undo(conversation), 2800);
  };
  private undo(conversation: C) {
    const pending = this.pending;
    if (!pending || pending.conversation !== conversation) return;
    clearTimeout(pending.timer);
    this.pending = null;
    const { state, persist, renderList, expand } = this.host;
    conversation.archived = false;
    state.convs.splice(Math.min(pending.index, state.convs.length), 0, conversation);
    persist();
    renderList();
    expand(conversation.id);
  }
  delete = (conversation: C) => {
    const { state, abort, removeDraft, loadDraft, persist, renderAll, renderArchive, buzz } = this.host;
    abort(conversation.id);
    state.convs = state.convs.filter((item) => item.id !== conversation.id);
    state.archivedList = state.archivedList.filter((item) => item.id !== conversation.id);
    removeDraft(conversation.id);
    if (state.currentId === conversation.id) {
      state.currentId = state.convs[0]?.id || null;
      loadDraft();
    }
    persist();
    renderAll();
    renderArchive();
    buzz(15);
  };
  restore = (conversation: C) => {
    const { state, write, persist, renderList, renderArchive, renderAll, current, renderMessages, showToast } =
      this.host;
    state.archivedList = state.archivedList.filter((item) => item !== conversation);
    conversation.archived = false;
    if (state.mode === 'local') {
      if (!state.convs.includes(conversation)) state.convs.push(conversation);
    } else {
      state.convs.push(conversation);
      write(
        'patch',
        `patch:${conversation.id}`,
        { id: conversation.id, patch: { archived: false } },
        () => {
          state.convs = state.convs.filter((item) => item !== conversation);
          conversation.archived = true;
          state.archivedList.unshift(conversation);
          persist();
          renderAll();
          renderArchive();
        },
        '복원하지 못했어요',
      );
    }
    persist();
    renderList();
    renderArchive();
    if (conversation === current()) renderMessages();
    showToast('복원됨', '', null, 1600);
  };
}
export function createArchive<C extends Conversation>(host: Host<C>) {
  return new Archive(host);
}
