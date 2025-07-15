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
ARP_TIMEOUT = 2

DB_CONFIG = {
    'user': 'username',
    'password': 'password',
    'host': 'localhost',
    'database': 'DB_NAME',
}

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
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scan (
            Nome VARCHAR(255),
            IP VARCHAR(15),
            MAC_ADDRESS VARCHAR(17) PRIMARY KEY,
            Last_Online DATETIME,
            Proprietario VARCHAR(255),
            Rete VARCHAR(50),
            VPN BOOLEAN DEFAULT FALSE,
            INDEX idx_ip (IP)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    conn.commit()
    return conn, cursor

def record_exists(cursor, mac):
    cursor.execute("SELECT IP FROM scan WHERE MAC_ADDRESS = %s", (mac,))
    result = cursor.fetchone()
    return result[0] if result else None

def insert_or_update(cursor, nome, ip, mac, rete):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if not mac or mac == "00:00:00:00:00:00":
        print(f"[!] MAC non valido per {ip}, salto.")
        return
    old_ip = record_exists(cursor, mac)
    if old_ip and old_ip != ip:
        print(f"[⚠️] IP cambiato per {mac}: da {old_ip} a {ip}")
        if is_device_active(old_ip):
            ip = old_ip
    if old_ip:
        cursor.execute("SELECT Nome FROM scan WHERE MAC_ADDRESS = %s", (mac,))
        existing_nome = cursor.fetchone()[0] or ""
        if existing_nome.strip().lower() in ["", "sconosciuto"] and nome.lower() != "sconosciuto":
            cursor.execute("""
                UPDATE scan 
                SET IP = %s, Last_Online = %s, Rete = %s, Nome = %s
                WHERE MAC_ADDRESS = %s
            """, (ip, now, rete, nome, mac))
        else:
            cursor.execute("""
                UPDATE scan 
                SET IP = %s, Last_Online = %s, Rete = %s
                WHERE MAC_ADDRESS = %s
            """, (ip, now, rete, mac))
    else:
        cursor.execute("""
            INSERT INTO scan (Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete)
            VALUES (%s, %s, %s, %s, NULL, %s)
        """, (nome, ip, mac, now, rete))

def insert_self_device(cursor):
    interfaces = get_selected_local_interfaces()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_hostname = socket.gethostname()
    for iface, ip, mac in interfaces:
        nome = f"{base_hostname} ({iface})"
        rete = get_rete_da_ip(ip)
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

def export_to_csv(conn):
    today = datetime.now().strftime("%d-%m-%y")
    REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report")
    os.makedirs(REPORT_DIR, exist_ok=True)
    filename = os.path.join(REPORT_DIR, f"networkscan_{today}.csv")

    cursor = conn.cursor()
    cursor.execute("""
        SELECT Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN 
        FROM scan 
        ORDER BY INET_ATON(IP)
    """)
    results = cursor.fetchall()
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(['sep=;'])
        writer.writerow(['Nome', 'IP', 'MAC_ADDRESS', 'Last_Online', 'Proprietario', 'Rete', 'VPN'])
        writer.writerows(results)
    print(f"[✓] Esportazione CSV completata: {filename}")
    now = time.time()
    for f in os.listdir("report"):
        path = os.path.join("report", f)
        if os.path.isfile(path) and path.endswith(".csv") and now - os.path.getmtime(path) > 90 * 86400:
            os.remove(path)
            print(f"[🗑️] Rimosso CSV vecchio: {f}")

def passive_sniff_udp(timeout=10):
    print("[🛰️] Avvio sniffing passivo UDP...")
    seen = {}
    def packet_callback(pkt):
        if pkt.haslayer(UDP) and pkt.haslayer(IP) and pkt.haslayer(Ether):
            mac = pkt[Ether].src.upper()
            ip = pkt[IP].src
            if mac not in seen:
                seen[mac] = ip
    sniff(iface="wlan0", prn=packet_callback, store=False, timeout=timeout)
    return seen

# ========================
# 🔍 FUNZIONE PRINCIPALE
# ========================

def scan_network():
    conn, cursor = init_db()
    insert_self_device(cursor)
    for rete_nome, rete_prefix in RETI.items():
        print(f"\n[🔍] Scansione di {rete_nome} ({rete_prefix}0/24)")
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for i in INTERVALLO:
                ip = rete_prefix + str(i)
                futures.append(executor.submit(process_ip, ip, rete_nome, cursor))
            for future in futures:
                future.result()
    # Sniff passivo per dispositivi silenziosi
    passive_devices = passive_sniff_udp(10)
    for mac, ip in passive_devices.items():
        if not record_exists(cursor, mac):
            rete = get_rete_da_ip(ip)
            insert_or_update(cursor, "Dispositivo Passivo", ip, mac, rete)
            print(f"[📡] Dispositivo passivo rilevato: {ip} ({mac})")
    cursor.execute("DELETE FROM scan WHERE Last_Online < %s", (datetime.now() - timedelta(days=90),))
    conn.commit()
    export_to_csv(conn)
    cursor.close()
    conn.close()
    print("\n[✅] Scansione completata con successo!")

def process_ip(ip, rete_nome, cursor):
    if is_device_active(ip):
        mac = get_mac(ip)
        if mac:
            nome = get_hostname(ip)
            insert_or_update(cursor, nome, ip, mac, rete_nome)
            print(f"[+] Trovato: {ip} ({mac}) - {nome}")

# ========================
# ▶️ AVVIO SCRIPT
# ========================

def handle_sigsegv(signum, frame):
    print("[❌] Segmentation fault rilevato. Uscita protetta.")
    sys.exit(1)

if __name__ == "__main__":
    print("""
    ###################
    # Scanner di Rete #
    ###################
    """)
    signal.signal(signal.SIGSEGV, handle_sigsegv)
    if os.geteuid() != 0:
        print("[!] Lo script richiede privilegi root. Esegui con sudo.")
        exit(1)
    scan_network()
