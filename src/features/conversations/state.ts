type Load = <T>(key: string, fallback: T) => T;
type Keys = { mode: string; srv: string; convs: string; current: string };

export function createConversationState<T>({ load, keys }: { load: Load; keys: Keys }) {
  const mode = load<string>(keys.mode, 'local') === 'server' ? 'server' : 'local';
  return {
    mode,
    convs: mode === 'server' ? load<T[]>(keys.srv, []) : load<T[]>(keys.convs, []),
    archivedList: [] as T[],
    nextCursor: null as string | null,
    threadsLoading: false,
    persistOff: false,
    currentId: load<string | null>(keys.current, null),
  };
}
