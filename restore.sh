#!/bin/bash

# =============== ⚙️ CONFIGURAZIONE ===============

# 📁 Cartella dei backup
BACKUP_DIR="/home/mauromarzocca/Project/Python/backup_networkscan"
EXTRACT_DIR="./restore_temp"

# 🗃️ MySQL
DB_NAME="DB"
DB_USER="user"
DB_PASS="password"

# =============== 📚 SELEZIONE ZIP ===============
echo "📦 Elenco backup disponibili:"
mapfile -t files < <(ls -1 "$BACKUP_DIR"/*.zip 2>/dev/null)

if [ ${#files[@]} -eq 0 ]; then
    echo "[❌] Nessun file .zip trovato nella cartella $BACKUP_DIR"
    exit 1
fi

for i in "${!files[@]}"; do
    echo "$((i+1))) $(basename "${files[$i]}")"
done

read -p "📥 Inserisci il numero del file da ripristinare: " choice

# Validazione
if ! [[ "$choice" =~ ^[0-9]+$ ]] || ((choice < 1 || choice > ${#files[@]})); then
    echo "[❌] Scelta non valida."
    exit 1
fi

ZIP_FILE="${files[$((choice-1))]}"
echo "[📂] Estrazione di $(basename "$ZIP_FILE")..."

mkdir -p "$EXTRACT_DIR"
unzip -o "$ZIP_FILE" -d "$EXTRACT_DIR"

SQL_FILE=$(find "$EXTRACT_DIR" -name "scan_backup_*.sql" | head -n 1)

if [[ -z "$SQL_FILE" ]]; then
    echo "[❌] Nessun file SQL trovato nello zip."
    exit 1
fi

# =============== 🔄 RIPRISTINO ===============
echo "[🛠️] Eliminazione della tabella 'scan'..."
mysql -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "DROP TABLE IF EXISTS scan;"

echo "[📥] Ripristino da $SQL_FILE..."
mysql -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < "$SQL_FILE"

if [ $? -eq 0 ]; then
    echo "[✅] Ripristino completato con successo."
else
    echo "[❌] Errore durante il ripristino."
    exit 1
fi

# =============== 🧹 PULIZIA ===============
rm -rf "$EXTRACT_DIR"