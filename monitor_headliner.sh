#!/bin/bash

SCRIPT_PATH="/Users/edmonds/Development/python/exif-headliner/exif-headliner.py"
DIRECTORY="$1"
LOG_FILE="/Users/edmonds/Development/python/exif-headliner/restart.log"
SCRIPT_LOG="/Users/edmonds/Development/python/exif-headliner/headliner_script.log"

while true; do
    # Check if Python script with directory is running by searching both parts separately
    if ! pgrep -fl "$SCRIPT_PATH" | grep -- "--directory $DIRECTORY" > /dev/null; then
        echo "$(date): Restarting exif-headliner.py for \"$DIRECTORY\"" >> "$LOG_FILE"
        nohup python3 "$SCRIPT_PATH" --directory "$DIRECTORY" >> "$SCRIPT_LOG" 2>&1 &
    fi
    sleep 60
done
