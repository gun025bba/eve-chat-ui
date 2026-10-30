export type SearchHit = {
  match?: string;
  thread_id: string;
  message_id?: string;
  thread_title?: string;
  snippet?: string;
  created_at?: string;
};
type Host = {
  query: () => string;
  server: () => boolean;
  render: () => void;
  progress: (visible: boolean) => void;
  search: (query: string) => Promise<{ data?: SearchHit[] }>;
};
export class ConversationSearch {
  hits: SearchHit[] | null = null;
  private timer: ReturnType<typeof setTimeout> | 0 = 0;
  private sequence = 0;
  constructor(private host: Host) {}
  get pending() {
    return !!this.timer;
  }
  change = () => {
    const { render, query, progress, server } = this.host;
    render();
    clearTimeout(this.timer);
    this.timer = 0;
    this.hits = null;
    const text = query();
    progress(false);
    if (!text || !server()) return render();
    this.timer = setTimeout(() => this.run(text), 250);
  };
  private async run(text: string) {
    const sequence = ++this.sequence;
    const { query, search, progress, render } = this.host;
    progress(true);
    try {
      const result = await search(text);
      if (sequence !== this.sequence || query() !== text) return;
      this.hits = result.data || [];
    } catch {
      if (sequence === this.sequence) this.hits = [];
    } finally {
      if (sequence === this.sequence) {
        this.timer = 0;
        progress(false);
        render();
      }
    }
  }
}
