#!/bin/bash
echo "[📅] $(date '+%Y-%m-%d %H:%M:%S') Avvio scansione" >> /path/network_scan.log
/path/venv/bin/python /path/networkscan.py >> /path/network_scan.log 2>&1