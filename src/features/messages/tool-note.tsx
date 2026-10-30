import { Component, createRef } from 'preact';
import { TOOL_FAIL } from '../../lib/tool-status.js';
import { MessageIcon } from './parts-view.js';
export type Note = { key: string; t?: number };
export class ToolNote extends Component<{ note: Note }, { shown: boolean }> {
  state = { shown: false };
  private frame = 0;
  private element = createRef<HTMLDivElement>();
  componentDidMount() {
    this.frame = requestAnimationFrame(() => {
      if (this.element.current?.isConnected && !this.element.current.firstChild) this.setState({ shown: true });
    });
  }
  componentWillUnmount() {
    cancelAnimationFrame(this.frame);
  }
  render() {
    const { note } = this.props;
    if (!Object.hasOwn(TOOL_FAIL, note.key)) return null;
    const [, title, subtitle] = TOOL_FAIL[note.key];
    return (
      <div ref={this.element} class="tnote" role="status" aria-live="polite" data-key={note.key} data-t={note.t || 0}>
        {this.state.shown && (
          <>
            <MessageIcon name="warning" />
            <div class="tb">
              <b>{title}</b>
              <span>{subtitle}</span>
            </div>
          </>
        )}
      </div>
    );
  }
}
