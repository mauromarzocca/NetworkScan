#!/bin/bash

# =============== ⚙️ CONFIGURAZIONE ===============

# 📂 Cartella del progetto da zippare (Rilevamento automatico della directory dello script)
FOLDER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$(dirname "$FOLDER")/backup_networkscan"

# 📅 Data odierna
DATE=$(date +"%d-%m-%y")
ZIP_NAME="networkscan_${DATE}.zip"
SQL_FILE="scan_backup_${DATE}.sql"

# 🗃️ MySQL
DB_NAME="NetworkAllarm"
DB_USER="root"
DB_PASS="password"
TABLE_NAME="scan"

# 🎯 Server remoto
REMOTE_USER="user"
REMOTE_HOST="IP_ADDRESS"
REMOTE_PATH="remote/path/to/backup"

# =============== 🗃️ EXPORT DATABASE ===============
echo "[💾] Esportazione tabella '$TABLE_NAME'..."
# Usa --defaults-extra-file se possibile per evitare password in chiaro nei log
mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" "$TABLE_NAME" > "$FOLDER/$SQL_FILE" || {
    echo "[❌] Errore durante l'esportazione del database."
    # Non usciamo subito per permettere la pulizia dei vecchi file se possibile
}

# =============== 🗜️ CREA ZIP ===============
echo "[📦] Creazione dello zip..."
mkdir -p "$BACKUP_DIR"
if [ -f "$FOLDER/$SQL_FILE" ]; then
    cd "$(dirname "$FOLDER")" || exit 1
    # Zippa la cartella del progetto includendo il dump SQL appena creato al suo interno
    zip -r "$BACKUP_DIR/$ZIP_NAME" "$(basename "$FOLDER")" -x "*.git*" "*/venv/*" "*/__pycache__/*" || {
        echo "[⚠️] Errore durante la creazione dello zip."
    }
else
    echo "[⚠️] File SQL non trovato, skip creazione zip."
fi


# =============== 🚀 INVIO TRAMITE SCP ===============
# Scommenta se hai configurato SCP
# echo "[📤] Invio a $REMOTE_USER@$REMOTE_HOST..."
# scp "$BACKUP_DIR/$ZIP_NAME" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"

# if [ $? -eq 0 ]; then
#     echo "[✅] Backup inviato con successo!"
#     # rm "$FOLDER/$SQL_FILE" # Rimuovi SQL solo se inviato con successo? O rimuovi sempre?
# else
#     echo "[❌] Errore durante l'invio via SCP"
#     # exit 1
# fi

# Rimuovi il file SQL temporaneo dopo lo zip (opzionale, o lo lasciamo per history locale come da richiesta utente)
# rm "$FOLDER/$SQL_FILE"

# 🧹 Rimuovi tutti i file .sql più vecchi di 7 giorni dalla cartella del progetto
# L'utente chiedeva perché non vengono rimossi dopo 7 giorni. Lo script originale diceva "1 giorno" nei commenti ma usava +0
echo "[🧹] Pulizia vecchi file SQL..."
find "$FOLDER" -maxdepth 1 -type f -name "scan_backup_*.sql" -mtime +7 -exec rm -v {} \;

# 🧹 Cancella i backup ZIP più vecchi di 30 giorni (aumentato prudenzialmente)
echo "[🧹] Pulizia vecchi file ZIP..."
find "$BACKUP_DIR" -type f -name "*.zip" -mtime +30 -exec rm -v {} \;
