import subprocess
import socket
import mysql.connector
from datetime import datetime
import re
import netifaces
import csv
import os
import time
from concurrent.futures import ThreadPoolExecutor
from scapy.all import ARP, Ether, srp, conf

# ========================
# ⚙️ CONFIGURAZIONE
# ========================
RETI = {
    "Newtork": "192.168.1.",
}

INTERVALLO = range(1, 255)
INTERFACCE_CONSIDERATE = ["eth0", "wlan0"]
SCAN_PORTS = [80, 443, 8080]
ARP_TIMEOUT = 2

DB_CONFIG = {
    'user': 'user',
    'password': 'password',
    'host': 'localhost',
    'database': 'DB'
}

RETE_INTERFACE_MAP = {
    "192.168.1.": "eth0",
}

# ========================
# 🔧 FUNZIONI DI SUPPORTO
# ========================

def get_mac_scapy(ip, iface):
    conf.verb = 0
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip)
    try:
        ans, _ = srp(pkt, iface=iface, timeout=2, retry=2, verbose=0)
        for _, received in ans:
            return received.hwsrc.upper()
    except Exception as e:
        print(f"[!] Errore scapy ARP per {ip} su {iface}: {e}")
    return None

def get_mac_fallback(ip):
    try:
        subprocess.run(["arp", "-d", ip], stderr=subprocess.DEVNULL)
        subprocess.run(["ping", "-c", "1", "-W", "1", ip], stdout=subprocess.DEVNULL)
        time.sleep(0.5)
        output = subprocess.check_output(["arp", "-n", ip], text=True, timeout=ARP_TIMEOUT)
        mac = re.search(r"([0-9a-f]{2}[:\-]){5}[0-9a-f]{2}", output, re.I)
        return mac.group(0).upper() if mac else None
    except Exception:
        return None

def get_mac(ip):
    iface = None
    for prefix, inter in RETE_INTERFACE_MAP.items():
        if ip.startswith(prefix):
            iface = inter
            break
    if not iface:
        iface = INTERFACCE_CONSIDERATE[0]
    mac = get_mac_scapy(ip, iface)
    return mac if mac else get_mac_fallback(ip)

def scan_port(ip, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.connect((ip, port))
            return True
    except:
        return False

def is_device_active(ip):
    ping_result = subprocess.run(['ping', '-c', '1', '-W', '1', ip],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
    if ping_result.returncode == 0:
        return True
    with ThreadPoolExecutor(max_workers=5) as executor:
        if any(executor.map(lambda p: scan_port(ip, p), SCAN_PORTS)):
            return True
    mac = get_mac(ip)
    return mac and mac != "00:00:00:00:00:00"

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.timeout):
        try:
            nbns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            nbns.settimeout(1)
            nbns.sendto(b'\x00', (ip, 137))
            data, _ = nbns.recvfrom(1024)
            if data:
                return data[57:].split(b'\x00')[0].decode('ascii', errors='ignore')
        except:
            return "Sconosciuto"
    return "Sconosciuto"

def get_selected_local_interfaces():
    interfaces = []
    for iface in netifaces.interfaces():
        if iface not in INTERFACCE_CONSIDERATE:
            continue
        if_addresses = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in if_addresses and netifaces.AF_LINK in if_addresses:
            ip = if_addresses[netifaces.AF_INET][0].get('addr')
            mac = if_addresses[netifaces.AF_LINK][0].get('addr')
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
    cursor.execute("SELECT COUNT(*) FROM scan WHERE MAC_ADDRESS = %s", (mac,))
    return cursor.fetchone()[0] > 0

def insert_or_update(conn, cursor, nome, ip, mac, rete):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if record_exists(cursor, mac):
        cursor.execute("""
            UPDATE scan 
            SET IP = %s, Last_Online = %s, Rete = %s 
            WHERE MAC_ADDRESS = %s
        """, (ip, now, rete, mac))
    else:
        cursor.execute("""
            INSERT INTO scan (Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN)
            VALUES (%s, %s, %s, %s, NULL, %s, FALSE)
        """, (nome, ip, mac, now, rete))
    conn.commit()

def insert_self_device(conn, cursor):
    interfaces = get_selected_local_interfaces()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    base_hostname = socket.gethostname()
    for iface, ip, mac in interfaces:
        nome = f"{base_hostname} ({iface})"
        rete = get_rete_da_ip(ip)
        if record_exists(cursor, mac):
            cursor.execute("""
                UPDATE scan 
                SET IP = %s, Last_Online = %s, Rete = %s 
                WHERE MAC_ADDRESS = %s
            """, (ip, now, rete, mac))
        else:
            cursor.execute("""
                INSERT INTO scan (Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN)
                VALUES (%s, %s, %s, %s, NULL, %s, FALSE)
            """, (nome, ip, mac, now, rete))
        conn.commit()
        print(f"[✓] Interfaccia registrata: {nome} - {ip} - {mac} in {rete}")

def export_to_csv(conn):
    today = datetime.now().strftime("%d-%m-%y")
    os.makedirs("report", exist_ok=True)
    filename = f"report/networkscan_{today}.csv"
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Nome, IP, MAC_ADDRESS, Last_Online, Proprietario, Rete, VPN 
        FROM scan 
        ORDER BY INET_ATON(IP)
    """)
    results = cursor.fetchall()
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Nome', 'IP', 'MAC_ADDRESS', 'Last_Online', 'Proprietario', 'Rete', 'VPN'])
        writer.writerows(results)
    print(f"[✓] Esportazione CSV completata: {filename}")

def process_ip(ip, rete_nome, conn, cursor):
    if is_device_active(ip):
        mac = get_mac(ip)
        if mac:
            nome = get_hostname(ip)
            insert_or_update(conn, cursor, nome, ip, mac, rete_nome)
            print(f"[+] Trovato: {ip} ({mac}) - {nome}")
        else:
            print(f"[!] Dispositivo attivo ma MAC non rilevato: {ip}")

def scan_network():
    conn, cursor = init_db()
    insert_self_device(conn, cursor)
    for rete_nome, rete_prefix in RETI.items():
        print(f"\n[🔍] Scansione di {rete_nome} ({rete_prefix}0/24)")
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(process_ip, f"{rete_prefix}{i}", rete_nome, conn, cursor)
                for i in INTERVALLO
            ]
            for future in futures:
                future.result()
    conn.commit()
    export_to_csv(conn)
    cursor.close()
    conn.close()
    print("\n[✅] Scansione completata con successo!")

if __name__ == "__main__":
    print("""
    ###################
    # Scanner di Rete #
    ###################
    """)
    if os.geteuid() != 0:
        print("[!] Attenzione: Lo script richiede privilegi root per funzionare correttamente.")
        print("[!] Per favore esegui con sudo.")
        exit(1)
    scan_network()