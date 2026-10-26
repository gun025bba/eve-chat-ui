#!/bin/bash
cd "$(dirname "$0")"; [ -z "$EVE_PORT" ] && pkill -f mock.py; sleep 0.5; (nohup v/bin/python mock.py >mock.log 2>&1 &); sleep 1   # EVE_PORT set: leave other mocks alone
timeout 400 v/bin/python ${1:-e2e.py}
