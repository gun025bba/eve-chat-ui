export const PAIRED = 'eve.paired';
export const PLOCK = 'eve.pairLock';
export const MAXF = 5;
export const LOCK_MS = 10 * 60e3;
export const normCode = (value: unknown) =>
  String(value || '')
    .toUpperCase()
    .replace(/[^0-9A-Z]/g, '')
    .replace(/O/g, '0')
    .replace(/[IL]/g, '1')
    .replace(/U/g, 'V')
    .slice(0, 8);
export const fmtCode = (code: string) => (code.length > 4 ? `${code.slice(0, 4)}-${code.slice(4)}` : code);
export function notice(code: string | undefined, paired: boolean) {
  const denied = code === 'identity_not_allowed',
    pair = !denied;
  const repair = pair && (code === 'invalid_session' || paired);
  return {
    pair,
    title: denied ? '이 계정은 쓸 수 없어요' : repair ? '다시 연결해 주세요' : '이 기기를 연결해 주세요',
    body: denied
      ? '허용된 Tailscale 계정으로 로그인한 뒤 다시 시도해 주세요.'
      : repair
        ? '연결이 만료됐거나 해제됐어요. Eve 서버에서 새 연결 코드를 받아 입력해 주세요.'
        : 'Eve 서버에서 받은 8자리 연결 코드를 입력해 주세요.',
  };
}
