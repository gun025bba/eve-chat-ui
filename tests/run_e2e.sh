#!/bin/bash
cd "$(dirname "$0")/.." || exit 2
npm run check || exit 2
npm run build || exit 2
export EVE_UI_DIR="$PWD/dist"
cd tests; [ -z "$EVE_PORT" ] && pkill -f mock.py; sleep 0.5; (nohup v/bin/python mock.py >mock.log 2>&1 &); sleep 1   # EVE_PORT set: leave other mocks alone
timeout 400 v/bin/python ${1:-e2e.py}
