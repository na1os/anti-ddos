import os
import time
import psutil
import platform
import subprocess
import sqlite3
import threading
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from colorama import init, Fore, Style

init(autoreset=True)
load_dotenv("config.env")

app = Flask(__name__)
DB_NAME = "guardian.db"

# Config
THRESHOLD = int(os.getenv("CONNECTION_THRESHOLD", 100))
FEED_THRESHOLD = int(os.getenv("LIVE_FEED_THRESHOLD", 15))
INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
BAN_DURATION = int(os.getenv("BAN_DURATION", 3600))
DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
WHITELIST = set(ip.strip() for ip in os.getenv("WHITELIST_IPS", "127.0.0.1").split(","))
MONITOR_PORTS = set(int(p.strip()) for p in os.getenv("MONITOR_PORTS", "").split(",") if p.strip())

# State
ban_list = {} # Format: {"192.168.1.5": timestamp_ban}
live_attacks = []

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS attacks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, connections INTEGER, country TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_geoip(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=country,city,isp", timeout=2).json()
        return f"{r.get('country', '?')} - {r.get('city', '?')}"
    except:
        return "Necunoscut"

def send_alerts(ip, count, country):
    msg_text = f"🚨 **Atac Oprit!**\nIP: `{ip}` ({country})\nConexiuni: `{count}`\nBanat pentru: {BAN_DURATION}s"
    if DISCORD_URL:
        try: requests.post(DISCORD_URL, json={"content": msg_text}, timeout=3)
        except: pass
    if TG_TOKEN and TG_CHAT:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        try: requests.post(url, data={"chat_id": TG_CHAT, "text": msg_text.replace('**','*'), "parse_mode": "Markdown"}, timeout=3)
        except: pass

def firewall_block(ip):
    try:
        if platform.system() == "Linux":
            subprocess.run(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"], check=False)
        else:
            subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name=Guardian_{ip}", "dir=in", "action=block", f"remoteip={ip}"], check=False)
    except: pass

def firewall_unblock(ip):
    try:
        if platform.system() == "Linux":
            subprocess.run(["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"], check=False)
        else:
            subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name=Guardian_{ip}"], check=False)
    except: pass

def ban_ip(ip, count):
    if ip in ban_list: return
    ban_list[ip] = time.time()
    country = get_geoip(ip)
    
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("INSERT INTO attacks (ip, connections, country) VALUES (?, ?, ?)", (ip, count, country))
    conn.commit()
    conn.close()
    
    send_alerts(ip, count, country)
    firewall_block(ip)
    print(f"{Fore.RED}[BAN] {ip} ({country}) blocat pentru {BAN_DURATION}s.{Style.RESET_ALL}")

def cleanup_bans():
    while True:
        time.sleep(10)
        now = time.time()
        to_unban = [ip for ip, t in ban_list.items() if now - t > BAN_DURATION]
        for ip in to_unban:
            firewall_unblock(ip)
            del ban_list[ip]
            print(f"{Fore.YELLOW}[UNBAN] {ip} a fost deblocat automat.{Style.RESET_ALL}")

def monitor_loop():
    global live_attacks
    while True:
        ip_counts = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == psutil.CONN_ESTABLISHED and conn.raddr:
                    ip = conn.raddr.ip
                    port = conn.laddr.port
                    
                    if ip in WHITELIST or ip in ban_list: continue
                    if MONITOR_PORTS and port not in MONITOR_PORTS: continue
                    
                    ip_counts[ip] = ip_counts.get(ip, 0) + 1
        except:
            pass
        
        current_attacks = []
        for ip, count in ip_counts.items():
            if count >= THRESHOLD:
                ban_ip(ip, count)
            elif count >= FEED_THRESHOLD:
                current_attacks.append({"ip": ip, "count": count, "percent": min(int((count/THRESHOLD)*100), 100)})
        
        current_attacks.sort(key=lambda x: x['count'], reverse=True)
        live_attacks = current_attacks[:20]
        time.sleep(INTERVAL)

# --- ROUTE-URI WEB ---
@app.route('/')
def dashboard():
    return render_template('dashboard.html', threshold=THRESHOLD, ban_duration=BAN_DURATION)

@app.route('/api/live')
def api_live():
    return jsonify({"active_ips": len(live_attacks), "blocked_total": len(ban_list), "attacks": live_attacks})

@app.route('/api/history/<period>')
def api_history(period):
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    if period == '1h': fmt = "%H:%M"; delta = timedelta(hours=1)
    elif period == '24h': fmt = "%H:00"; delta = timedelta(hours=24)
    elif period == '7d': fmt = "%m-%d"; delta = timedelta(days=7)
    else: fmt = "%m-%d"; delta = timedelta(days=31)
    
    start = (datetime.now() - delta).strftime('%Y-%m-%d %H:%M:%S')
    c.execute(f"SELECT strftime('{fmt}', timestamp) as t, COUNT(*) FROM attacks WHERE timestamp >= ? GROUP BY t ORDER BY t ASC", (start,))
    data = c.fetchall()
    conn.close()
    return jsonify([{"time": row[0], "attacks": row[1]} for row in data])

@app.route('/api/all_attacks')
def api_all_attacks():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT ip, connections, country, timestamp FROM attacks ORDER BY timestamp DESC LIMIT 50")
    data = c.fetchall()
    conn.close()
    return jsonify([{"ip": r[0], "connections": r[1], "country": r[2], "time": r[3]} for r in data])

# NOU: Deblocare manuală din Web
@app.route('/api/unban/<ip>')
def api_unban(ip):
    if ip in ban_list:
        firewall_unblock(ip)
        del ban_list[ip]
        return jsonify({"status": "success", "message": f"{ip} deblocat manual!"})
    return jsonify({"status": "error", "message": "IP-ul nu este în lista de ban."})

if __name__ == '__main__':
    init_db()
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=cleanup_bans, daemon=True).start()
    print(f"{Fore.CYAN}[*] Server Web pornit pe http://localhost:5000{Style.RESET_ALL}")
    app.run(host='0.0.0.0', port=5000, debug=False)