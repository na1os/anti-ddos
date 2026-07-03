import os
import time
import psutil
import requests
import platform
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

init(autoreset=True)

class AntiDDoS:
    def __init__(self):
        load_dotenv("config.env")
        
        self.threshold = int(os.getenv("CONNECTION_THRESHOLD", 100))
        self.feed_threshold = int(os.getenv("LIVE_FEED_THRESHOLD", 15))
        self.interval = int(os.getenv("CHECK_INTERVAL", 2))
        
        self.discord_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        
        whitelist_str = os.getenv("WHITELIST_IPS", "")
        self.whitelist = set(ip.strip() for ip in whitelist_str.split(",") if ip.strip())
        
        self.blocked_ips = set()
        self.alerted_ips = set()
        self.total_attacks_blocked = 0

    def clear_screen(self):
        os.system('cls' if platform.system() == "Windows" else 'clear')

    def send_alerts(self, ip, count):
        if ip in self.alerted_ips:
            return
        self.alerted_ips.add(ip)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if self.discord_url:
            msg = {"content": f"🚨 **THREAT NEUTRALIZED**\n```http\nIP: {ip}\nPayload: {count} conns\nTime: {timestamp}\nAction: FIREWALL + QUARANTINE```"}
            try: requests.post(self.discord_url, json=msg, timeout=3)
            except: pass

        if self.tg_token and self.tg_chat:
            msg = f"🚨 *Atac Oprit!*\n*IP:* `{ip}`\n*Conexiuni:* `{count}`"
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            try: requests.post(url, data={"chat_id": self.tg_chat, "text": msg, "parse_mode": "Markdown"}, timeout=3)
            except: pass

    def block_ip_system(self, ip):
        # 1. Propriul sistem (Carantină Internă)
        self.blocked_ips.add(ip)
        self.total_attacks_blocked += 1
        
        # 2. Sistemul de Firewall (OS Level)
        try:
            if platform.system() == "Linux":
                subprocess.run(["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"], check=True)
            else:
                subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name=Block_{ip}", "dir=in", "action=block", f"remoteip={ip}"], check=True)
            return True
        except:
            return False

    def get_connections(self):
        ip_counts = {}
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == psutil.CONN_ESTABLISHED and conn.raddr:
                    ip = conn.raddr.ip
                    if ip not in self.whitelist:
                        ip_counts[ip] = ip_counts.get(ip, 0) + 1
        except psutil.AccessDenied:
            print(f"{Fore.RED}[EROARE FATALĂ] Trebuie să rulezi ca Administrator/Root!")
            exit(1)
        return ip_counts

    def draw_progress_bar(self, count):
        # Calculează procentajul față de pragul de blocare
        percent = min(count / self.threshold, 1.0)
        bar_length = 20
        filled = int(bar_length * percent)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        if percent < 0.5:
            return f"{Fore.GREEN}[{bar}]"
        elif percent < 0.9:
            return f"{Fore.YELLOW}[{bar}]"
        else:
            return f"{Fore.RED}{Style.BRIGHT}[{bar}]"

    def draw_dashboard(self, ip_counts):
        self.clear_screen()
        current_time = datetime.now().strftime('%H:%M:%S')
        
        print(f"{Fore.CYAN}╔══════════════════════════════════════════════════════════╗")
        print(f"{Fore.CYAN}║{Fore.YELLOW}      ADVANCED NETWORK GUARDIAN & DDoS MITIGATION       {Fore.CYAN}║")
        print(f"{Fore.CYAN}╠══════════════════════════════════════════════════════════╣")
        print(f"{Fore.CYAN}║{Fore.WHITE} Time: {current_time}  | Prag: {self.threshold} | Interval: {self.interval}s      {Fore.CYAN}║")
        print(f"{Fore.CYAN}║{Fore.LIGHTGREEN_EX} Status: PROTECTED   {Fore.WHITE}Atacuri Oprite: {Fore.RED}{self.total_attacks_blocked:<4}          {Fore.CYAN}║")
        print(f"{Fore.CYAN}╚══════════════════════════════════════════════════════════╝")
        
        active_threats = False
        
        sorted_ips = sorted(ip_counts.items(), key=lambda item: item[1], reverse=True)
        
        for ip, count in sorted_ips:
            if ip in self.blocked_ips:
                continue # Sistemul propriu: ignorăm IP-urile blocate (Carantină)
                
            if count < self.feed_threshold:
                continue
                
            active_threats = True
            bar = self.draw_progress_bar(count)
            
            if count >= self.threshold:
                print(f"  {Fore.RED}{Style.BRIGHT}[!! THREAT DETECTED !!]{Style.RESET_ALL} {ip:<15} {bar} {count} conns")
                print(f"  {Fore.LIGHTRED_EX}--> Inițiere Blocare Firewall & Carantină Internă...")
                if self.block_ip_system(ip):
                    print(f"  {Fore.GREEN}--> [SUCCESS] {ip} a fost ELIMINAT.")
                    self.send_alerts(ip, count)
                time.sleep(1) # Pauză scurtă pentru efect vizual
            else:
                status = f"{Fore.YELLOW}Suspicios" if count > self.threshold * 0.6 else f"{Fore.GREEN}Monitorizat"
                print(f"  {Fore.CYAN}IP:{Style.RESET_ALL} {ip:<15} {bar} {count} conns | {status}")

        if not active_threats:
            print(f"\n  {Fore.LIGHTBLACK_EX} Sistemul funcționează normal. Niciun atac detectat.")

        print(f"\n{Fore.LIGHTBLACK_EX} [Ctrl+C pentru oprire]")

    def run(self):
        try:
            while True:
                ip_counts = self.get_connections()
                self.draw_dashboard(ip_counts)
                time.sleep(self.interval)
        except KeyboardInterrupt:
            print(f"\n\n{Fore.YELLOW}[*] Sistem oprit. Total atacuri blocate: {self.total_attacks_blocked}")

if __name__ == "__main__":
    app = AntiDDoS()
    app.run()