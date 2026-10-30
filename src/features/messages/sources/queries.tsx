type Query = { q: string; by?: unknown };
export function ToolQueries({ tools }: { tools?: unknown }) {
  const queries = (Array.isArray(tools) ? (tools as unknown[]) : [])
    .filter(
      (item): item is Query =>
        !!item && typeof item === 'object' && 'q' in item && typeof item.q === 'string' && !!item.q.trim(),
    )
    .slice(0, 3);
  const why = queries.some((query) => query.by === 'model') ? 'Eve가 필요하다고 판단해 검색했어요' : '';
  return (
    <>
      {queries.map((query, index) => (
        <div class="tq">
          <span>
            검색어 <q>{query.q}</q>
            {index === 0 && why ? ` · ${why}` : ''}
          </span>
        </div>
      ))}
    </>
  );
}
