import os
import time
import psutil
import requests
import platform
import subprocess
import ipaddress
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Inițializare colorama pentru culori în consolă (funcționează pe Win/Linux)
init(autoreset=True)

# Încărcare configurație din .env
load_dotenv("config.env")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
THRESHOLD = int(os.getenv("CONNECTION_THRESHOLD", 100))
LIVE_FEED_THRESHOLD = int(os.getenv("LIVE_FEED_THRESHOLD", 15))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))

# Procesare Whitelist
whitelist_str = os.getenv("WHITELIST_IPS", "")
WHITELIST = [ip.strip() for ip in whitelist_str.split(",") if ip.strip()]

blocked_ips = set()

def print_banner():
    print(Fore.CYAN + "="*60)
    print(Fore.YELLOW + "      SISTEM AVANSAT DE MONITORIZARE ȘI PROTECȚIE")
    print(Fore.CYAN + "="*60)
    print(f"{Fore.GREEN}[*] Prag blocare:{Style.RESET_ALL} {THRESHOLD} conexiuni/IP")
    print(f"{Fore.GREEN}[*] Prag afișare live:{Style.RESET_ALL} {LIVE_FEED_THRESHOLD} conexiuni/IP")
    print(f"{Fore.GREEN}[*] Whitelist:{Style.RESET_ALL} {', '.join(WHITELIST) if WHITELIST else 'Niciunul'}")
    print(f"{Fore.GREEN}[*] Discord Webhook:{Style.RESET_ALL} {'Configurat' if DISCORD_WEBHOOK_URL else 'Lipsă'}")
    print(f"{Fore.GREEN}[*] Telegram Alert:{Style.RESET_ALL} {'Configurat' if TELEGRAM_BOT_TOKEN else 'Lipsă'}")
    print(Fore.CYAN + "-"*60)
    print(Fore.MAGENTA + "[*] Pornire monitorizare... (Apasă Ctrl+C pentru oprire)\n")

def send_discord_alert(ip, count):
    if not DISCORD_WEBHOOK_URL: return
    message = {
        "content": f"🚨 **Alertă de Securitate: Posibil Atac DDoS!**\n"
                   f"```http\nIP Atacator: {ip}\nConexiuni Deschise: {count}\nTimp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nAcțiune: BLOCAT în Firewall```"
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=5)
    except Exception as e:
        print(Fore.RED + f"[EROARE Discord] {e}")

def send_telegram_alert(ip, count):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    message = (f"🚨 *Alertă: Posibil Atac DDoS!*\n"
               f"*IP Atacator:* `{ip}`\n"
               f"*Conexiuni:* `{count}`\n"
               f"*Acțiune:* `Blocat în Firewall`")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(Fore.RED + f"[EROARE Telegram] {e}")

def block_ip(ip):
    """Blochează IP-ul folosind comenzi native de sistem."""
    try:
        if platform.system() == "Linux":
            subprocess.run(["sudo", "iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"], check=True)
        elif platform.system() == "Windows":
            subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name=Block_{ip}", "dir=in", "action=block", f"remoteip={ip}"], check=True)
        return True
    except Exception as e:
        print(Fore.RED + f"[EROARE BLOCARE] {ip}: {e}")
        return False

def get_active_connections():
    """Numără conexiunile active (ESTABLISHED) per IP extern."""
    ip_counts = {}
    try:
        connections = psutil.net_connections(kind='inet')
        for conn in connections:
            if conn.status == psutil.CONN_ESTABLISHED and conn.raddr:
                ip = conn.raddr.ip
                # Ignoră IP-urile din whitelist
                if ip not in WHITELIST:
                    ip_counts[ip] = ip_counts.get(ip, 0) + 1
    except psutil.AccessDenied:
        print(Fore.RED + "[EROARE] Acces refuzat. Rulați ca Administrator/Root!")
        exit(1)
    except Exception as e:
        print(Fore.RED + f"[EROARE Conexiuni] {e}")
    return ip_counts

def main():
    print_banner()
    
    try:
        while True:
            ip_counts = get_active_connections()
            current_time = datetime.now().strftime('%H:%M:%S')
            
            # Sortăm conexiunile descrescător după număr
            for ip, count in sorted(ip_counts.items(), key=lambda item: item[1], reverse=True):
                if count >= LIVE_FEED_THRESHOLD:
                    # Determinăm statusul și culoarea
                    if count >= THRESHOLD:
                        status = f"{Fore.RED}{Style.BRIGHT}*** ATAC DETECTAT ***"
                        
                        # Dacă depășește pragul și nu a fost deja blocat
                        if ip not in blocked_ips:
                            print(f"{Fore.RED}[{current_time}] [ALERTĂ CRITICĂ] {ip:<15} | Conexiuni: {count:<5} | Trimitere notificări...")
                            send_discord_alert(ip, count)
                            send_telegram_alert(ip, count)
                            
                            if block_ip(ip):
                                blocked_ips.add(ip)
                                print(f"{Fore.RED}[{current_time}] [FIREWALL] IP-ul {ip} a fost BLOCAT cu succes.")
                    else:
                        status = f"{Fore.YELLOW}Suspicios"
                        
                    # Afișare live feed
                    print(f"{Fore.CYAN}[{current_time}] {Style.RESET_ALL}IP: {ip:<15} | Conexiuni: {count:<5} | Status: {status}")
            
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[*] Oprire sistem. IP-uri blocate în această sesiune: {len(blocked_ips)}")
        print(Fore.CYAN + "La revedere!")

if __name__ == "__main__":
    main()