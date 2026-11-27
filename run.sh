#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

if [ ! -d ".venv" ]; then
  python -m venv .venv
fi
source .venv/bin/activate

python -c "import django" 2>/dev/null || pip install -r requirements.txt
python -c "import tzdata" 2>/dev/null || pip install tzdata

python manage.py migrate
command -v termux-wake-lock >/dev/null && termux-wake-lock || true

IP=$(ip route get 1 2>/dev/null | awk '{print $7; exit}')
echo ""
echo "============================================"
echo " On this phone : http://127.0.0.1:8082"
[ -n "$IP" ] && echo " On your laptop: http://$IP:8082   (same Wi-Fi)"
echo "============================================"

python manage.py runserver 0.0.0.0:8082
