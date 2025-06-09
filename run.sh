#!/bin/bash

pip install -r requirements.txt

# Kill any process using port 8085
pids=$(lsof -ti:8085)
if [ ! -z "$pids" ]; then
    echo "Killing processes on port 8085: $pids"
    kill -9 $pids 2>/dev/null
fi

# Run the Python script in background
cd /c/code/hwm && nohup python main.py > /dev/null 2>&1 &

echo "Hardware monitor daemon started on port 8085"