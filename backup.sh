#!/bin/bash

# =============== ⚙️ CONFIGURAZIONE ===============

# 📂 Cartella del progetto da zippare
FOLDER="path/to/your/project"
BACKUP_DIR="$(dirname "$FOLDER")/backup"

# 📅 Data odierna
DATE=$(date +"%d-%m-%y")
ZIP_NAME="networkscan_${DATE}.zip"
SQL_FILE="scan_backup_${DATE}.sql"

# 🗃️ MySQL
DB_NAME="DB"
DB_USER="user"
DB_PASS="passeword"
TABLE_NAME="scan"

# 🎯 Server remoto
REMOTE_USER="user"
REMOTE_HOST="IP_ADDRESS"
REMOTE_PATH="remote/path/to/backup"

# =============== 🗃️ EXPORT DATABASE ===============
echo "[💾] Esportazione tabella '$TABLE_NAME'..."
mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" "$TABLE_NAME" > "$FOLDER/$SQL_FILE" || {
    echo "[❌] Errore durante l'esportazione del database."
    exit 1
}

# =============== 🗜️ CREA ZIP ===============
echo "[📦] Creazione dello zip..."
mkdir -p "$BACKUP_DIR"
cd "$(dirname "$FOLDER")" || exit 1
zip -r "$BACKUP_DIR/$ZIP_NAME" "$(basename "$FOLDER")/$SQL_FILE" "$(basename "$FOLDER")"

# =============== 🚀 INVIO TRAMITE SCP ===============
echo "[📤] Invio a $REMOTE_USER@$REMOTE_HOST..."
scp "$BACKUP_DIR/$ZIP_NAME" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"

if [ $? -eq 0 ]; then
    echo "[✅] Backup inviato con successo!"
    rm "$FOLDER/$SQL_FILE"
else
    echo "[❌] Errore durante l'invio via SCP"
    exit 1
fi