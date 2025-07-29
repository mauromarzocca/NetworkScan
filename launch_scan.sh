#!/bin/bash

LOCKFILE="/tmp/networkscan.lock"
SCRIPT_PATH="/path/networkscan.py"
PYTHON="/path/venv/bin/python"
LOGFILE="/path/network_scan.log"

echo "[📅] $(date '+%Y-%m-%d %H:%M:%S') Avvio scansione" >> "$LOGFILE"

# Trova e kill-a eventuali istanze precedenti dello script
pids=$(pgrep -f "$SCRIPT_PATH")
if [ -n "$pids" ]; then
    echo "[⚠️ ] $(date '+%Y-%m-%d %H:%M:%S') Trovati processi attivi: $pids. Terminazione in corso..." >> "$LOGFILE"
    kill $pids
    sleep 2
    # Se ancora attivi, forza kill
    pids_still=$(pgrep -f "$SCRIPT_PATH")
    if [ -n "$pids_still" ]; then
        echo "[⛔] $(date '+%Y-%m-%d %H:%M:%S') Forzatura terminazione: $pids_still" >> "$LOGFILE"
        kill -9 $pids_still
    fi
fi

# Esecuzione protetta con flock (per sicurezza aggiuntiva)
flock -n "$LOCKFILE" $PYTHON "$SCRIPT_PATH" >> "$LOGFILE" 2>&1
