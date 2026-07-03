#!/bin/bash
# Mutăm scriptul în directorul lui
cd "$(dirname "$0")"

# Verificăm dacă suntem root
if [ "$EUID" -ne 0 ]; then
    echo -e "\033[33m[*] Acest script necesită drepturi de Root pentru a modifica Firewall-ul (iptables).\033[0m"
    echo -e "\033[33m[*] Se solicită drepturi de Root...\033[0m"
    # Folosim exec pentru a înlocui procesul curent cu cel de root, evitând închiderea brutală
    exec sudo "$0" "$@"
    exit 1
fi

# Verificăm dacă venv există
if [ ! -d "venv" ]; then
    echo -e "\033[31m[EROARE] Lipsește venv. Rulează mai întâi install_linux.sh\033[0m"
    exit 1
fi

echo -e "\033[36m==========================================================\033[0m"
echo -e "\033[36m 🛡️  NETWORK GUARDIAN RULEAZĂ (Linux) 🛡️\033[0m"
echo -e "\033[36m ==========================================================\033[0m"
echo -e "\033[32m[*] Dashboard Web disponibil la: http://localhost:5000\033[0m"
echo -e "\033[32m[*] Apasă CTRL+C pentru a opri sistemul.\033[0m\n"

# Rulăm aplicația direct (logurile vor apărea aici)
./venv/bin/python3 web_guardian.py