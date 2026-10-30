#!/bin/bash
# Run every Python suite (tests/*.py) strictly one after the other against a local mock.py, then `node sw_push.js`.
# Exit code 1 if any suite fails. A failing suite is re-run once (headless-browser timing flakes); it only counts as passed if the re-run passes.
#   PYTHON=tests/v/bin/python bash tests/run_all.sh        (default PYTHON=python3)   EVE_PORT=<free port> (default 8899)
#   SHARD_INDEX=2 SHARD_COUNT=8 bash tests/run_all.sh      run only every 8th suite (suite k goes to shard k mod 8 + 1; sw_push.js runs in the LAST shard). CI runs the shards in parallel jobs.
#     Default SHARD_COUNT=1 = everything, as before. Each shard starts its own mock.py (own runner, so the same port is fine).
# Not suites (helpers / screenshot generators that write files): mock, *_common, gen_splash, header_shot, review_shots, shots*, *_shots.
cd "$(dirname "$0")" || exit 2
PY="${PYTHON:-python3}"; export EVE_PORT="${EVE_PORT:-8899}"
OUT="${RUN_ALL_OUT:-$(mktemp -d)}"; mkdir -p "$OUT"
"$PY" mock.py > "$OUT/mock.log" 2>&1 &
MOCK=$!                      # only this process is ever stopped
trap 'kill "$MOCK" 2>/dev/null; wait "$MOCK" 2>/dev/null' EXIT
for _ in $(seq 1 30); do (echo > "/dev/tcp/127.0.0.1/$EVE_PORT") 2>/dev/null && break; sleep 0.5; done
(echo > "/dev/tcp/127.0.0.1/$EVE_PORT") 2>/dev/null || { echo "mock.py did not start"; cat "$OUT/mock.log"; exit 2; }
FAILED=(); N=0; PASS=0; FAIL=0; K=0
SC="${SHARD_COUNT:-1}"; SI="${SHARD_INDEX:-1}"
case "$SC$SI" in *[!0-9]*|'') echo "SHARD_COUNT/SHARD_INDEX must be numbers"; exit 2;; esac
{ [ "$SI" -ge 1 ] && [ "$SI" -le "$SC" ]; } || { echo "SHARD_INDEX must be 1..SHARD_COUNT"; exit 2; }
for f in $(ls ./*.py | sed 's#^\./##' | grep -v -E '^(mock|[a-z0-9_]*_common|gen_splash|header_shot|review_shots|shots|shots_native|[a-z0-9_]*_shots)\.py$'); do
  K=$((K+1)); [ $(( (K - 1) % SC + 1 )) = "$SI" ] || continue
  N=$((N+1)); ok=0
  for try in 1 2; do
    timeout 900 "$PY" "$f" > "$OUT/$f.out" 2>&1; rc=$?
    nf=$(grep -c '^FAIL' "$OUT/$f.out"); [ "$rc" = 0 ] && [ "$nf" = 0 ] && { ok=1; break; }
    echo "::warning::$f failed (rc=$rc, FAIL lines=$nf) attempt $try"; grep -E '^FAIL|Error|Traceback' "$OUT/$f.out" | head -8
  done
  p=$(grep -c '^PASS' "$OUT/$f.out"); PASS=$((PASS+p))
  if [ "$ok" = 1 ]; then echo "ok   $f ($p passed)"; else echo "FAIL $f"; FAILED+=("$f"); tail -40 "$OUT/$f.out"; fi
done
if [ "$SI" = "$SC" ]; then
  timeout 300 node sw_push.js > "$OUT/sw_push.out" 2>&1; rc=$?
  if [ "$rc" = 0 ] && ! grep -q '^FAIL' "$OUT/sw_push.out"; then echo "ok   sw_push.js"; else echo "FAIL sw_push.js"; tail -30 "$OUT/sw_push.out"; FAILED+=("sw_push.js"); fi
fi
echo "shard $SI/$SC: suites: $N python$([ "$SI" = "$SC" ] && echo " + sw_push.js"); PASS lines: $PASS; failed: ${#FAILED[@]} ${FAILED[*]}"
[ "${#FAILED[@]}" = 0 ]
