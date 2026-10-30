import { Component, createRef, render } from 'preact';
import { type Citation, srcDate, srcDomain } from '../../../lib/citations.js';
import type { prepareSources } from '../../../lib/sources.js';
import { ToolQueries } from './queries.js';
export type SourceModel = NonNullable<ReturnType<typeof prepareSources>>;
type Domain = SourceModel['domains'][number];
function Favicon({ domain }: { domain: Domain }) {
  const mono = (domain.name[0] || '?').toUpperCase();
  return domain.favicon ? (
    <span class="fav">
      <img src={domain.favicon} alt="" referrerPolicy="no-referrer" loading="lazy" data-mono={mono} />
    </span>
  ) : (
    <span class="fav mono">{mono}</span>
  );
}
function Chip({ domain, id }: { domain: Domain; id: string }) {
  return (
    <button type="button" class="sc" aria-expanded="false" aria-controls={id} aria-label={`출처 ${domain.name}`}>
      <span class="sc-in">
        <Favicon domain={domain} />
        <span class="sc-n">{domain.name}</span>
      </span>
    </button>
  );
}
function Item({ number, citation }: { number: number; citation: Citation }) {
  const domain = srcDomain(citation),
    title = citation.title || domain || citation.url;
  const date = srcDate(citation.published),
    subtitle = date ? `${domain} · ${date}` : domain;
  return (
    <li class="src-item" data-n={number}>
      <a
        href={citation.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${number}. ${title}, ${subtitle}, 새 창에서 열림`}
      >
        <span class="sn">{number}</span>
        <span class="st">{title}</span>
        <span class="sd">{subtitle}</span>
      </a>
    </li>
  );
}
function Items({ entries }: { entries: [number, Citation][] }) {
  return (
    // biome-ignore lint/a11y/noRedundantRoles: Preserve the explicit source-list ARIA contract.
    <ol role="list">
      {entries.map(([number, citation]) => (
        <Item number={number} citation={citation} />
      ))}
    </ol>
  );
}
type TemplateProps = { model: SourceModel; tools?: unknown };
class AllTemplate extends Component<TemplateProps> {
  private element = createRef<HTMLTemplateElement>();
  componentDidMount() {
    this.componentDidUpdate();
  }
  componentDidUpdate() {
    const root = this.element.current;
    if (!root) return;
    const { model, tools } = this.props;
    render(
      <>
        <ToolQueries tools={tools} />
        <Items entries={model.all} />
        <div class="src-chips">
          {model.domains.map((domain) => (
            <span class="src-chip">{domain.name}</span>
          ))}
        </div>
      </>,
      root.content,
    );
  }
  componentWillUnmount() {
    if (this.element.current) render(null, this.element.current.content);
  }
  render() {
    return <template class="src-all-tpl" ref={this.element} />;
  }
}
export function SourceSection({ model, id, tools }: { model: SourceModel; id: string; tools?: unknown }) {
  const many = model.all.length > 6;
  return (
    <section class="sources" aria-label="출처">
      <div class="src-row">
        {model.shown.map((domain) => (
          <Chip domain={domain} id={id} />
        ))}
        {!!model.rest && (
          <button
            type="button"
            class="sc sc-more"
            aria-expanded="false"
            aria-controls={id}
            aria-label={`출처 ${model.rest}개 더 보기`}
          >
            <span class="sc-in">+{model.rest}</span>
          </button>
        )}
      </div>
      <div class="src-list" id={id} hidden>
        <ToolQueries tools={tools} />
        <Items entries={many ? model.all.slice(0, 5) : model.all} />
        {many && (
          <button type="button" class="src-all">
            모두 보기 <span>{model.all.length}</span>
          </button>
        )}
      </div>
      <AllTemplate model={model} tools={tools} />
    </section>
  );
}
