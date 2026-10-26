#!/bin/bash
cd "$(dirname "$0")"; pkill -f mock.py; sleep 0.5; (nohup v/bin/python mock.py >mock.log 2>&1 &); sleep 1
timeout 400 v/bin/python ${1:-e2e.py}
