# NetworkScan

NetworkAllarm è uno script Python avanzato che effettua una scansione periodica della rete locale, identifica i dispositivi connessi (inclusi quelli IoT silenziosi), e salva le informazioni in un database MySQL e in un file CSV.

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

## 🛠️ Requisiti

- Python 3.7+
- Permessi di root (necessari per `scapy`, `arp`, accesso raw socket)

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

- 🗃️ Database: tabella scan nel database NetworkAllarm, con:
- Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN (boolean)
- 📄 CSV: file generato in report/networkscan_<GG-MM-AA>.csv, sovrascritto ogni giorno.

## 🛡️ Sicurezza

- Lo script usa scapy per scansioni ARP precise. Alcuni dispositivi silenziosi (es. prese smart) vengono rilevati solo così.
- l campo VPN è booleano ed è inizialmente FALSE. Puoi aggiornarlo manualmente nel DB.

## 📌 Esempi utili

Aggiornare un nome e proprietario in MySQL:

```bash
UPDATE scan
SET Nome = 'Echo Dot Soggiorno',
    Proprietario = 'Utente'
WHERE IP = '192.168.1.X';
```

## 🧑‍💻 Autore

Mauro Marzocca

⸻

Per dubbi, problemi o suggerimenti, apri una issue o contattami!
