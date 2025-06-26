#!/bin/bash

# =============== ⚙️ CONFIGURAZIONE ===============

# 📂 Cartella da zippare
FOLDER="path/to/your/folder"  # Modifica con il percorso della tua cartella

# 📅 Data odierna
DATE=$(date +"%d-%m-%y")

# 🗃️ Parametri MySQL
DB_NAME="DB"
DB_USER="user"
DB_PASS="password"
TABLE_NAME="scan"

# 📁 Nome backup
ZIP_NAME="networkscan_${DATE}.zip"
SQL_FILE="scan_backup_${DATE}.sql"

# 🎯 Destinazione SCP
REMOTE_USER="user"
REMOTE_HOST="IP_ADDRESS"  # Modifica con l'indirizzo IP del server remoto
REMOTE_PATH="/home/utente/backup_networkscan/"

# =============== 🗃️ EXPORT DATABASE ===============
echo "[💾] Esportazione tabella '$TABLE_NAME' dal database '$DB_NAME'..."
mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" "$TABLE_NAME" > "$FOLDER/$SQL_FILE"

if [ $? -ne 0 ]; then
    echo "[❌] Errore durante l'esportazione del database."
    exit 1
fi

# =============== 🗜️ CREA ZIP ===============
echo "[📦] Compressione in corso..."
cd "$(dirname "$FOLDER")" || exit 1
zip -r "$ZIP_NAME" "$(basename "$FOLDER")/$SQL_FILE" "$(basename "$FOLDER")"

# =============== 🚀 INVIO TRAMITE SCP ===============
echo "[📤] Invio in corso a $REMOTE_USER@$REMOTE_HOST..."
scp "$ZIP_NAME" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"

if [ $? -eq 0 ]; then
    echo "[✅] Backup inviato con successo!"

    # 🔥 Rimuove file temporanei
    rm "$ZIP_NAME"
    rm "$FOLDER/$SQL_FILE"
else
    echo "[❌] Errore durante l'invio via SCP"
    exit 1
fi