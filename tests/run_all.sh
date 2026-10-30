#!/bin/bash
# Run every Python suite (tests/*.py) strictly one after the other against a local mock.py, then `node sw_push.js`.
# Exit code 1 if any suite fails. A failing suite is re-run once (headless-browser timing flakes); it only counts as passed if the re-run passes.
#   PYTHON=tests/v/bin/python bash tests/run_all.sh        (default PYTHON=python3)   EVE_PORT=<free port> (default 8899)
# Not suites (helpers / screenshot generators that write files): mock, *_common, gen_splash, header_shot, review_shots, shots*, *_shots.
cd "$(dirname "$0")/.." || exit 2
npm ci --ignore-scripts || exit 2
npm run check || exit 2
npm run build || exit 2
export EVE_UI_DIR="$PWD/dist"
cd tests || exit 2
PY="${PYTHON:-python3}"; export EVE_PORT="${EVE_PORT:-8899}"
OUT="${RUN_ALL_OUT:-$(mktemp -d)}"; mkdir -p "$OUT"
"$PY" mock.py > "$OUT/mock.log" 2>&1 &
MOCK=$!                      # only this process is ever stopped
trap 'kill "$MOCK" 2>/dev/null; wait "$MOCK" 2>/dev/null' EXIT
for _ in $(seq 1 30); do (echo > "/dev/tcp/127.0.0.1/$EVE_PORT") 2>/dev/null && break; sleep 0.5; done
(echo > "/dev/tcp/127.0.0.1/$EVE_PORT") 2>/dev/null || { echo "mock.py did not start"; cat "$OUT/mock.log"; exit 2; }
FAILED=(); N=0; PASS=0; FAIL=0
for f in $(ls ./*.py | sed 's#^\./##' | grep -v -E '^(mock|[a-z0-9_]*_common|gen_splash|header_shot|review_shots|shots|shots_native|[a-z0-9_]*_shots)\.py$'); do
  N=$((N+1)); ok=0
  for try in 1 2; do
    timeout 900 "$PY" "$f" > "$OUT/$f.out" 2>&1; rc=$?
    nf=$(grep -c '^FAIL' "$OUT/$f.out"); [ "$rc" = 0 ] && [ "$nf" = 0 ] && { ok=1; break; }
    echo "::warning::$f failed (rc=$rc, FAIL lines=$nf) attempt $try"; grep -E '^FAIL|Error|Traceback' "$OUT/$f.out" | head -8
  done
  p=$(grep -c '^PASS' "$OUT/$f.out"); PASS=$((PASS+p))
  if [ "$ok" = 1 ]; then echo "ok   $f ($p passed)"; else echo "FAIL $f"; FAILED+=("$f"); tail -40 "$OUT/$f.out"; fi
done
timeout 300 node sw_push.js > "$OUT/sw_push.out" 2>&1; rc=$?
if [ "$rc" = 0 ] && ! grep -q '^FAIL' "$OUT/sw_push.out"; then echo "ok   sw_push.js"; else echo "FAIL sw_push.js"; tail -30 "$OUT/sw_push.out"; FAILED+=("sw_push.js"); fi
echo "suites: $N python + sw_push.js; PASS lines: $PASS; failed: ${#FAILED[@]} ${FAILED[*]}"
[ "${#FAILED[@]}" = 0 ]
