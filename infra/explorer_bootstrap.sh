#!/bin/bash
# Bootstrap the AI Village explorer box (EC2 user data, first boot only).
# Installs Python tooling, syncs the dataset tables from S3 (screenshots stay in S3, fetched on demand),
# and installs an idle watchdog that stops (not terminates) the instance.
set -uo pipefail

BUCKET="ai-village-459653581741"
PREFIX="hf/ai-village"
REGION="ap-south-1"
export AWS_DEFAULT_REGION="$REGION" HOME=/root

LOG=/var/log/explorer-bootstrap.log
exec >>"$LOG" 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
ship_log() { aws s3 cp --quiet "$LOG" "s3://$BUCKET/_explorer/bootstrap.log" || true; }
trap ship_log EXIT

log "BOOT instance=$(cat /var/lib/cloud/data/instance-id 2>/dev/null)"

# --- idle watchdog first, so a broken bootstrap still stops the box -------------------------
cat > /usr/local/bin/explorer-idle.sh <<'EOF'
#!/bin/bash
# Stop the instance after IDLE_MIN minutes with no dashboard connection, low load and no profiler,
# or after HARD_CAP_H hours of uptime. Instance shutdown behaviour is "stop".
IDLE_MIN=60; HARD_CAP_H=12; STAMP=/var/lib/explorer/active.stamp
mkdir -p /var/lib/explorer; [ -f "$STAMP" ] || touch "$STAMP"
# Idle time never counts from before this boot: a stamp from a previous run would stop the box
# minutes after every restart (seen 2026-09-25: idle_min=4330 at uptime 0).
boot_epoch=$(( $(date +%s) - $(cut -d. -f1 /proc/uptime) ))
[ "$(stat -c %Y "$STAMP")" -lt "$boot_epoch" ] && touch "$STAMP"
busy=""
[ -n "$(ss -Htn state established '( sport = :8501 )' 2>/dev/null)" ] && busy="dashboard"
awk '{exit !($1 > 0.5)}' /proc/loadavg && busy="${busy} load"
pgrep -f 'explorer/(profile|build|feasibility|trace)' >/dev/null && busy="${busy} job"
[ -n "$busy" ] && touch "$STAMP"
idle=$(( ( $(date +%s) - $(stat -c %Y "$STAMP") ) / 60 ))
up_h=$(( $(cut -d. -f1 /proc/uptime) / 3600 ))
echo "$(date -u +%FT%TZ) WATCHDOG busy=[${busy# }] idle_min=$idle uptime_h=$up_h" >> /var/log/explorer-idle.log
if [ "$idle" -ge "$IDLE_MIN" ] || [ "$up_h" -ge "$HARD_CAP_H" ]; then
  echo "$(date -u +%FT%TZ) WATCHDOG stopping (idle_min=$idle uptime_h=$up_h)" >> /var/log/explorer-idle.log
  aws s3 cp --quiet /var/log/explorer-idle.log "s3://ai-village-459653581741/_explorer/idle.log" --region ap-south-1 || true
  shutdown -h now
fi
EOF
chmod +x /usr/local/bin/explorer-idle.sh
cat > /etc/systemd/system/explorer-idle.service <<'EOF'
[Unit]
Description=AI Village explorer idle watchdog
[Service]
Type=oneshot
ExecStart=/usr/local/bin/explorer-idle.sh
EOF
cat > /etc/systemd/system/explorer-idle.timer <<'EOF'
[Unit]
Description=Run explorer idle watchdog every 5 minutes
[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload && systemctl enable --now explorer-idle.timer
log "WATCHDOG installed (60 min idle / 12 h cap → stop)"

# --- Python tooling ------------------------------------------------------------------------
dnf install -y -q python3.11 python3.11-pip >/dev/null 2>&1 && PY=python3.11 || PY=python3
log "PYTHON $($PY --version 2>&1)"
$PY -m venv /opt/explorer/venv
/opt/explorer/venv/bin/pip install -q -U pip >/dev/null
/opt/explorer/venv/bin/pip install -q duckdb pyarrow pandas streamlit plotly >/dev/null \
  || { log "FATAL pip install"; exit 1; }
log "PIP $(/opt/explorer/venv/bin/python -c 'import duckdb,pyarrow,pandas,streamlit as s;print("duckdb",duckdb.__version__,"pyarrow",pyarrow.__version__,"streamlit",s.__version__)')"

# --- dataset tables (not screenshots) --------------------------------------------------------
mkdir -p /data/raw /data/profile /data/parquet /data/tmp
for f in $(aws s3 ls "s3://$BUCKET/$PREFIX/" | awk '$NF !~ /\/$/ {print $NF}'); do
  t0=$(date +%s)
  aws s3 cp --quiet "s3://$BUCKET/$PREFIX/$f" "/data/raw/$f" && \
    log "SYNC $f $(stat -c %s /data/raw/$f) secs=$(( $(date +%s) - t0 ))"
done
aws s3 cp --quiet "s3://$BUCKET/$PREFIX/images/computer-use-turns/index.json" /data/raw/images_index.json \
  && log "SYNC images_index.json"
log "DISK $(df -h --output=used,avail /data | tail -1)"
log "READY"
