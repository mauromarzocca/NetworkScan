import subprocess
import socket
import mysql.connector
from datetime import datetime, timedelta
import re
import netifaces
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor
import signal
import sys
import threading
import fcntl
from scapy.all import sniff, UDP, Ether, IP

# ========================
# ⚙️ CONFIGURAZIONE
# ========================
RETI = {
    "Network": "192.168.1.",
}

INTERVALLO = range(1, 255)
INTERFACCE_CONSIDERATE = ["eth0", "wlan0"]
SCAN_PORTS = [80, 443, 8080, 6666, 8888]  # Include porte Tuya/SmartLife
# Extended port list for perform_port_scan
EXTENDED_PORTS = [
    21, 22, 23, 25, 53, 80, 110, 139, 143, 443, 445, 
    993, 995, 3306, 3389, 5900, 6666, 8080, 8888
]
ARP_TIMEOUT = 2
db_lock = threading.Lock()

DB_CONFIG = {
    'user': 'root',
    'password': 'password',
    'host': 'localhost',
    'database': 'NetworkAllarm',
}

VERSION = "3.2"

# ========================
# 🔧 FUNZIONI DI SUPPORTO
# ========================

def get_mac(ip):
    try:
        subprocess.run(["arp", "-d", ip], stderr=subprocess.DEVNULL)
        subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL)
        time.sleep(0.5)
        output = subprocess.check_output(["arp", "-n", ip], text=True, timeout=ARP_TIMEOUT)
        mac = re.search(r"([0-9a-f]{2}[:\-]){5}[0-9a-f]{2}", output, re.I)
        return mac.group(0).upper() if mac else None
    except Exception:
        return None

def scan_port(ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((ip, port))
            return True
    except:
        return False

def perform_port_scan(ip):
    """Esegue una scansione più approfondita delle porte su un IP attivo."""
    open_ports = []
    # Scansiona un range esteso di porte comuni
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_port = {executor.submit(scan_port, ip, port): port for port in EXTENDED_PORTS}
        for future in future_to_port:
            port = future_to_port[future]
            if future.result():
                open_ports.append(port)
    return sorted(open_ports)

def is_device_active(ip):
    ping_result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ping_result.returncode == 0:
        return True
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda p: scan_port(ip, p), SCAN_PORTS))
        if any(results):
            return True
    mac = get_mac(ip)
    if mac and mac != "00:00:00:00:00:00":
        return True
    return False

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.timeout):
        return "Sconosciuto"

def get_selected_local_interfaces():
    interfaces = []
    for iface in netifaces.interfaces():
        if iface not in INTERFACCE_CONSIDERATE:
            continue
        if_addresses = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in if_addresses and netifaces.AF_LINK in if_addresses:
            ip_info = if_addresses[netifaces.AF_INET][0]
            mac_info = if_addresses[netifaces.AF_LINK][0]
            ip = ip_info.get('addr')
            mac = mac_info.get('addr')
            if ip and mac and not ip.startswith("127."):
                interfaces.append((iface, ip, mac))
    return interfaces

def get_rete_da_ip(ip):
    for nome, prefix in RETI.items():
        if ip.startswith(prefix):
            return nome
    return "Sconosciuta"

def init_db():
    try:
        # Separate database name from config to connect to server first
        db_name = DB_CONFIG.pop('database', 'NetworkAllarm')
        
        # Connect to MySQL server
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        
        # Select the database
        cursor.execute(f"USE {db_name}")
        
        # Create table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan (
                Nome VARCHAR(255),
                IP VARCHAR(15),
                MAC_ADDRESS VARCHAR(17) PRIMARY KEY,
                Last_Online DATETIME,
                Proprietario VARCHAR(255),
                Rete VARCHAR(50),
                VPN BOOLEAN DEFAULT FALSE,
                Open_Ports TEXT,
                INDEX idx_ip (IP)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        
        # Check if Open_Ports column exists, if not add it
        cursor.execute("""
            SELECT count(*) 
            FROM information_schema.columns 
            WHERE table_schema = %s 
            AND table_name = 'scan' 
            AND column_name = 'Open_Ports'
        """, (db_name,))
        
        if cursor.fetchone()[0] == 0:
            print("[i] Aggiunta colonna Open_Ports alla tabella scan...")
            cursor.execute("ALTER TABLE scan ADD COLUMN Open_Ports TEXT")
            
        conn.commit()
        
        # Restore DB_CONFIG for future use if needed
        DB_CONFIG['database'] = db_name
        
        return conn, cursor
    except mysql.connector.Error as err:
        print(f"[❌] Errore DB Init: {err}")
        return None, None

def record_exists(cursor, mac):
    try:
        cursor.execute("SELECT IP FROM scan WHERE MAC_ADDRESS = %s", (mac,))
        result = cursor.fetchone()
        return result[0] if result else None
    except mysql.connector.Error as err:
        print(f"[⚠️] Errore lettura DB: {err}")
        return None

def insert_or_update(cursor, nome, ip, mac, rete, open_ports=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if not mac or mac == "00:00:00:00:00:00":
        print(f"[!] MAC non valido per {ip}, salto.")
        return

    ports_str = ",".join(map(str, open_ports)) if open_ports else None

    try:
        # Con il lock attivo, possiamo eseguire operazioni in sequenza
        old_ip = record_exists(cursor, mac)

        if old_ip and old_ip != ip:
            print(f"[⚠️] IP cambiato per {mac}: da {old_ip} a {ip}")
            # Verifica se il vecchio IP è ancora attivo (gestione duplicati/movimenti)
            # Qui potremmo voler forzare l'aggiornamento se siamo sicuri

        if old_ip:
            cursor.execute("SELECT Nome FROM scan WHERE MAC_ADDRESS = %s", (mac,))
            res = cursor.fetchone()
            existing_nome = res[0] if res else ""

            query = "UPDATE scan SET IP = %s, Last_Online = %s, Rete = %s"
            params = [ip, now, rete]
            
            if existing_nome.strip().lower() in ["", "sconosciuto"] and nome.lower() != "sconosciuto":
                query += ", Nome = %s"
                params.append(nome)
            
            if ports_str is not None:
                query += ", Open_Ports = %s"
                params.append(ports_str)
                
            query += " WHERE MAC_ADDRESS = %s"
            params.append(mac)
            
            cursor.execute(query, tuple(params))

        else:
            cursor.execute("""
                INSERT INTO scan (Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, Open_Ports)
                VALUES (%s, %s, %s, %s, NULL, %s, %s)
            """, (nome, ip, mac, now, rete, ports_str))

        # Commit immediato per ridurre lock time se autocommit non è attivo
        # cursor.execute("COMMIT") # Non necessario se commit viene fatto alla fine, ma sicuro in thread
    except mysql.connector.Error as err:
        print(f"[❌] Errore DB Insert/Update: {err}")

def insert_self_device(cursor):
    interfaces = get_selected_local_interfaces()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_hostname = socket.gethostname()
    for iface, ip, mac in interfaces:
        nome = f"{base_hostname} ({iface})"
        rete = get_rete_da_ip(ip)
        with db_lock:
            try:
                old_ip = record_exists(cursor, mac)
                if old_ip:
                    cursor.execute("""
                        UPDATE scan
                        SET IP = %s, Last_Online = %s, Rete = %s, Nome = %s
                        WHERE MAC_ADDRESS = %s
                    """, (ip, now, rete, nome, mac))
                else:
                    cursor.execute("""
                        INSERT INTO scan (Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete)
                        VALUES (%s, %s, %s, %s, NULL, %s)
                    """, (nome, ip, mac, now, rete))
                print(f"[✓] Interfaccia registrata: {nome} - {ip} - {mac} in {rete}")
            except mysql.connector.Error as err:
                print(f"[❌] Errore DB Self Device: {err}")

def export_to_csv(conn):
    today = datetime.now().strftime("%d-%m-%y")
    REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report")
    os.makedirs(REPORT_DIR, exist_ok=True)
    filename = os.path.join(REPORT_DIR, f"networkscan_{today}.csv")

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN, Open_Ports
            FROM scan
            ORDER BY INET_ATON(IP)
        """)
        results = cursor.fetchall()
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(['sep=;'])
            writer.writerow(['Nome', 'IP', 'MAC_ADDRESS', 'Last_Online', 'Proprietario', 'Rete', 'VPN', 'Open_Ports'])
            writer.writerows(results)
        print(f"[✓] Esportazione CSV completata: {filename}")
        cursor.close()
    except Exception as e:
        print(f"[❌] Errore Export CSV: {e}")

    now = time.time()
    for f in os.listdir(REPORT_DIR):
        path = os.path.join(REPORT_DIR, f)
        if os.path.isfile(path) and path.endswith(".csv") and now - os.path.getmtime(path) > 90 * 86400:
            try:
                os.remove(path)
                print(f"[🗑️] Rimosso CSV vecchio: {f}")
            except OSError as e:
                print(f"[⚠️] Errore rimozione {f}: {e}")

def passive_sniff_udp(timeout=10):
    print("[🛰️] Avvio sniffing passivo UDP...")

    interfaces = get_selected_local_interfaces()
    if not interfaces:
        print("[!] Nessuna interfaccia valida trovata per lo sniffing.")
        return {}

    # Use the first valid interface found
    iface_to_use = interfaces[0][0]
    print(f"[i] Utilizzo interfaccia: {iface_to_use}")

    seen = {}
    def packet_callback(pkt):
        if pkt.haslayer(UDP) and pkt.haslayer(IP) and pkt.haslayer(Ether):
            mac = pkt[Ether].src.upper()
            ip = pkt[IP].src
            if mac not in seen:
                seen[mac] = ip
    try:
        sniff(iface=iface_to_use, prn=packet_callback, store=False, timeout=timeout)
    except Exception as e:
        print(f"[!] Errore durante lo sniffing su {iface_to_use}: {e}")
    return seen

# ========================
# 🔍 FUNZIONE PRINCIPALE
# ========================

def scan_network():
    conn, cursor = init_db()
    if not conn:
        print("[❌] Impossibile connettersi al DB. Uscita.")
        return

    insert_self_device(cursor)

    for rete_nome, rete_prefix in RETI.items():
        print(f"\n[🔍] Scansione di {rete_nome} ({rete_prefix}0/24)")
        with ThreadPoolExecutor(max_workers=10) as executor: # Ridotto max_workers per stabilità
            futures = []
            for i in INTERVALLO:
                ip = rete_prefix + str(i)
                futures.append(executor.submit(process_ip, ip, rete_nome, cursor))
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    print(f"[⚠️] Errore in thread: {e}")

    # Sniff passivo per dispositivi silenziosi
    try:
        passive_devices = passive_sniff_udp(10)
        for mac, ip in passive_devices.items():
            with db_lock:
                if not record_exists(cursor, mac):
                    rete = get_rete_da_ip(ip)
                    insert_or_update(cursor, "Dispositivo Passivo", ip, mac, rete)
                    print(f"[📡] Dispositivo passivo rilevato: {ip} ({mac})")
    except Exception as e:
        print(f"[⚠️] Errore sniffing passivo: {e}")

    # Pulizia vecchi record
    try:
        cursor.execute("DELETE FROM scan WHERE Last_Online < %s", (datetime.now() - timedelta(days=90),))
        conn.commit()
    except mysql.connector.Error as e:
        print(f"[❌] Errore pulizia DB: {e}")

    export_to_csv(conn)

    try:
        cursor.close()
        conn.close()
    except:
        pass
    print("\n[✅] Scansione completata con successo!")

def process_ip(ip, rete_nome, cursor):
    try:
        if is_device_active(ip):
            mac = get_mac(ip)
            if mac:
                nome = get_hostname(ip)
                open_ports = perform_port_scan(ip)
                
                # LOCK QUI PER EVITARE CONFLITTI SUL CURSORE
                with db_lock:
                    # Verifica se la connessione è ancora attiva (rudimentale)
                    # In produzione meglio un pool, ma qui usiamo il lock
                    insert_or_update(cursor, nome, ip, mac, rete_nome, open_ports)
                
                ports_display = f" | Porte aperte: {open_ports}" if open_ports else ""
                print(f"[+] Trovato: {ip} ({mac}) - {nome}{ports_display}")
    except Exception as e:
        print(f"[⚠️] Errore processamento IP {ip}: {e}")

# ========================
# ▶️ AVVIO SCRIPT
# ========================

def handle_sigsegv(signum, frame):
    print("[❌] Segmentation fault rilevato. Uscita protetta.")
    sys.exit(1)

def check_single_instance():
    """Assicura che sia in esecuzione una sola istanza dello script."""
    lock_file = "/tmp/networkscan.lock"
    try:
        fp = open(lock_file, 'w')
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fp
    except IOError:
        print("[!] Un'altra istanza di NetworkScan è già in esecuzione. Uscita.")
        sys.exit(0)

if __name__ == "__main__":
    print(f"""
    ###################
    # Scanner di Rete #
    # Versione {VERSION}
    ###################
    """)

    signal.signal(signal.SIGSEGV, handle_sigsegv)

    if os.geteuid() != 0:
        print("[!] Lo script richiede privilegi root. Esegui con sudo.")
        exit(1)

    # Mantieni il file lock aperto finché lo script gira
    lock_handle = check_single_instance()

    try:
        scan_network()
    finally:
        # Rilascio opzionale (il sistema lo fa comunque alla chiusura)
        if lock_handle:
            fcntl.lockf(lock_handle, fcntl.LOCK_UN)
            lock_handle.close()
