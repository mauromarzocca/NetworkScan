#!/bin/bash

# Ottieni la directory dello script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCKFILE="/tmp/networkscan.lock"
SCRIPT_PATH="$SCRIPT_DIR/networkscan.py"
# Usa python3 direttamente se venv non è disponibile o non funziona come root
PYTHON="python3"

# Se esiste un venv locale, prova a usarlo (ma attenzione ai permessi sudo)
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
fi

LOGFILE="$SCRIPT_DIR/network_scan.log"

echo "[📅] $(date '+%Y-%m-%d %H:%M:%S') Avvio scansione" >> "$LOGFILE"

# Assicurarsi che il file di log sia scrivibile
touch "$LOGFILE"
chmod 666 "$LOGFILE" 2>/dev/null
# Assicurarsi che il lock file sia scrivibile da tutti (per evitare problemi tra root/user)
touch "$LOCKFILE"
chmod 666 "$LOCKFILE" 2>/dev/null

# Esecuzione protetta con flock
flock -n "$LOCKFILE" $PYTHON "$SCRIPT_PATH" >> "$LOGFILE" 2>&1
