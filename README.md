# NetworkScan

- Versione: 1.9.1

[![Made with Python](https://img.shields.io/badge/Made%20with-Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Python Version](https://img.shields.io/badge/Python-3.7%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
![Build Status](https://img.shields.io/badge/Build-Passing-brightgreen?style=for-the-badge&logo=github)

---

- [NetworkScan](#networkscan)
  - [🚀 Funzionalità principali](#-funzionalità-principali)
    - [Testing](#testing)
  - [Composizione Database](#composizione-database)
  - [🛠️ Requisiti](#️-requisiti)
    - [Dipendenza dei Pacchetti](#dipendenza-dei-pacchetti)
    - [📦 Dipendenze Python](#-dipendenze-python)
      - [Contenuto requirenments](#contenuto-requirenments)
  - [⚙️ Configurazione](#️-configurazione)
    - [Esempio crontab](#esempio-crontab)
      - [Script](#script)
  - [🧪 Esecuzione](#-esecuzione)
  - [📂 Output](#-output)
  - [🛡️ Sicurezza](#️-sicurezza)
  - [📌 Esempi utili](#-esempi-utili)
  - [Attenzione](#attenzione)
  - [Changelog](#changelog)
  - [🧑‍💻 Autore](#-autore)

---

![icon](icon.png)

NetworkScan è uno script Python avanzato che effettua una scansione periodica della rete locale, identifica i dispositivi connessi (inclusi quelli IoT silenziosi), e salva le informazioni in un database MySQL e in un file CSV.

## 🚀 Funzionalità principali

- Scansione di una o più reti locali specificate
- Rilevamento di dispositivi attivi tramite:
  - Ping
  - Scansione porte comuni (80, 443, 8080)
  - ARP (anche con `scapy` per precisione)
- Salvataggio dei dispositivi trovati in un database MySQL
- Generazione automatica di un file CSV giornaliero nella cartella `report/`
- Aggiornamento dinamico del database se il dispositivo cambia IP o rete
- Supporto multi-interfaccia (`eth0`, `wlan0`, ecc.)
- Aggiunta automatica del dispositivo locale allo scan
- Compatibile con Raspberry Pi, server Linux, Ubuntu

### Testing

NetworkScan è stato testato con Raspberry Pi 4 con Ubuntu Server.

## Composizione Database

La tabella 'Scan' è così composta:

- Nome : VARCHAR(255)
- IP : VARCHAR(15)
- MAC_ADDRESS : VARCHAR(17) PRIMARY KEY -> In quanto univoca per ogni dispositivo
- Last_Online : DATETIME
- Proprietario : VARCHAR(255)
- Rete : VARCHAR(50)
- VPN : Boolean -> Di default è false

## 🛠️ Requisiti

- Python 3.7+
- Permessi di root (necessari per `scapy`, `arp`, accesso raw socket)

### Dipendenza dei Pacchetti

Occorre installare i seguenti pacchetti:

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-mysqldb \
  net-tools \
  zip \
  unzip \
  mysql-client \
  iputils-ping \
  openssh-client
```

Se usi il virtualenv, puoi anche aggiungere:

```bash
pip install mysql-connector-python netifaces
```

### 📦 Dipendenze Python

Installa le dipendenze con:

```bash
pip install -r requirements.txt
```

#### Contenuto requirenments

mysql-connector-python
netifaces
scapy

## ⚙️ Configurazione

All’inizio dello script puoi configurare:

```bash
RETI = {
    "Network": "192.168.1.",
}

INTERFACCE_CONSIDERATE = ["eth0", "wlan0"]
DB_CONFIG = {
    'user': 'user',
    'password': 'password',
    'host': 'localhost',
    'database': 'DB'
}
```

### Esempio crontab

Per avviarlo ogni due ore occorre

- Eseguire il crontab da sudo

```bash
sudo crontab -e
```

- Incollare la seguente riga:

```bash
0 */2 * * * /bin/bash -c 'echo "[📅] $(date "+%Y-%m-%d %H:%M:%S") Avvio scansione" >> /path/network_scan.log && /venv/bin/python /path/networkscan.py >> /path/network_scan.log 2>&1'
```

Questa permette di essere eseguito ogni due ore a partire da mezzanotte.

#### Script

É presente uno script dove occorre modificare solo il path.
Occorre renderlo eseguibile tramite il comando:

```bash
chmod +x /home/mauromarzocca/Project/Python/Scan/launch_scan.sh
```

Inserire nel crontab

```bash
sudo crontab -e
```

La seguente riga:

```bash
0 */2 * * * /home/mauromarzocca/Project/Python/Scan/launch_scan.sh
```

## 🧪 Esecuzione

Lo script deve essere eseguito come root:

```bash
sudo python3 network_scanner.py
```

Oppure se sei in un ambiente virtuale:

```bash
sudo /path/to/venv/bin/python network_scanner.py
```

## 📂 Output

- 🗃️ Database: tabella scan nel database NetworkScan, con:
- Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN (boolean)
- 📄 CSV: file generato in report/networkscan_<GG-MM-AA>.csv, sovrascritto ogni giorno.

## 🛡️ Sicurezza

- Lo script usa scapy per scansioni ARP precise. Alcuni dispositivi silenziosi (es. prese smart) vengono rilevati solo così.
- l campo VPN è booleano ed è inizialmente FALSE. Puoi aggiornarlo manualmente nel DB.

## 📌 Esempi utili

- Aggiornare un nome e proprietario in MySQL:

```bash
UPDATE scan
SET Nome = 'Echo Dot Soggiorno',
    Proprietario = 'Utente'
WHERE IP = '192.168.1.X';
```

- Cancellare un dispositivo

```bash
DELETE FROM scan WHERE IP = '192.168.1.X';
```

## Attenzione

Si consiglia di non lanciare lo script più volte consecutivamente, poichè potrebbe verificarsi il seguente errore:

```bash
328081 Segmentation fault      (core dumped)
```

Poichè un output imprevisto da comandi di sistema (es. arp, ping) può non essere gestito bene da re.search() o da subprocess.check_output(), soprattutto se si lavora in più thread.

## Changelog

- Versione 1.0 : Build Iniziale
- Versione 1.1 : Introdotta pulizia dei file CSV più vecchi di 90 giorni
- Versione 1.2 : Introdotta pulizia dal DB dei dispositivi più vecchi di 90 giorni
- Versione 1.3 : Introdotto script di Backup
- Versione 1.4 : Introdotto script di Restore
- Versione 1.5 : Miglioramenti Generali
- Versione 1.6 : Ottimizzazione del Codice
- Versione 1.7 : Migliorato il riconoscimento dei dispositivi IoT
- Versione 1.8 : Migliorato CSV
- Versione 1.8.1 : Migliorata Documentazione
- Versione 1.8.2 : Creazione dell'icona
- Versione 1.9 : Creazione di uno script per automatizzare lo scan.
- Versione 1.9.1 : Miglioramenti Generali

## 🧑‍💻 Autore

Mauro Marzocca

⸻

Per dubbi, problemi o suggerimenti, apri una issue o contattami!
