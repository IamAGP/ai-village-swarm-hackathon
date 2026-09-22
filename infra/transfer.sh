#!/bin/bash
# Mirror a Hugging Face dataset revision into S3, one file at a time.
# Runs as EC2 user data. Resumable: skips keys already in S3 with the right size.
set -uo pipefail

REPO="aidigestorg/ai-village"
REV="838b4150303ca8228e8edb432d8b8ccae353d258"
BUCKET="ai-village-459653581741"
PREFIX="hf/ai-village"
REGION="ap-south-1"
PARAM="/ai-village/hf-token"
WORKERS="${WORKERS:-4}"
IDLE_MIN=20
HARD_CAP_MIN=240

export AWS_DEFAULT_REGION="$REGION"
LOG=/var/log/hfcopy.log
WORK=/data/work
mkdir -p "$WORK"
exec >>"$LOG" 2>&1
log() { echo "$(date -u +%FT%TZ) $*"; }
ship_log() { aws s3 cp --quiet "$LOG" "s3://$BUCKET/_transfer/hfcopy.log" || true; }

shutdown -h +"$HARD_CAP_MIN"   # hard cap; instance shutdown behaviour = terminate
log "BOOT instance=$(cat /var/lib/cloud/data/instance-id 2>/dev/null) rev=$REV workers=$WORKERS"

HF_TOKEN=$(aws ssm get-parameter --name "$PARAM" --with-decryption --query Parameter.Value --output text) \
  || { log "FATAL cannot read token"; ship_log; shutdown -h now; exit 1; }
export HF_TOKEN REPO REV BUCKET PREFIX WORK LOG
export HOME=/root HF_HOME=/data/hfhome HF_HUB_DISABLE_PROGRESS_BARS=1
dnf install -y -q python3-pip >/dev/null 2>&1
python3 -m pip install -q -U huggingface_hub >/dev/null 2>&1 \
  || { log "FATAL pip install huggingface_hub"; ship_log; shutdown -h now; exit 1; }
log "HFHUB $(python3 -c 'import huggingface_hub, hf_xet; print(huggingface_hub.__version__, "hf_xet ok")')"

# File list (path<TAB>size) from the HF API at the pinned revision.
python3 - <<'PY' > /data/filelist.tsv || { log "FATAL file list"; ship_log; shutdown -h now; exit 1; }
import json, os, urllib.request
req = urllib.request.Request(
    f"https://huggingface.co/api/datasets/{os.environ['REPO']}/revision/{os.environ['REV']}?blobs=true",
    headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"})
for s in json.load(urllib.request.urlopen(req))["siblings"]:
    print(f"{s['rfilename']}\t{s['size']}")
PY
TOTAL_FILES=$(wc -l < /data/filelist.tsv)
TOTAL_BYTES=$(awk -F'\t' '{s+=$2} END {printf "%d", s}' /data/filelist.tsv)
log "FILELIST files=$TOTAL_FILES bytes=$TOTAL_BYTES"
aws s3 cp --quiet /data/filelist.tsv "s3://$BUCKET/_transfer/filelist.tsv"

aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX/" \
  --query 'Contents[].[Key,Size]' --output text > /data/existing.tsv 2>/dev/null || : > /data/existing.tsv
export EXISTING=/data/existing.tsv

copy_one() {
  local path="$1" size="$2" key="$PREFIX/$1" dest file t0 got attempt
  if grep -qxF "$key	$size" "$EXISTING"; then echo "$(date -u +%FT%TZ) SKIP $path $size"; return 0; fi
  dest="$WORK/w$$"; file="$dest/$path"
  for attempt in 1 2 3 4 5 6; do
    t0=$(date +%s)
    echo "$(date -u +%FT%TZ) START $path $size try=$attempt"
    # hf_xet (via huggingface_hub) fetches Xet chunks in parallel; ~10x the curl /resolve/ rate here.
    if hf download "$REPO" "$path" --repo-type dataset --revision "$REV" --local-dir "$dest" \
         >/dev/null 2>>"$WORK/hf.err"; then
      got=$(stat -c %s "$file" 2>/dev/null || echo 0)
      if [ "$got" = "$size" ] && aws s3 cp --quiet "$file" "s3://$BUCKET/$key"; then
        rm -rf "$dest"
        echo "$(date -u +%FT%TZ) DONE $path $size secs=$(( $(date +%s) - t0 ))"
        return 0
      fi
      echo "$(date -u +%FT%TZ) RETRY $path got=$got want=$size"
    else
      echo "$(date -u +%FT%TZ) HFERR $path $(tail -1 "$WORK/hf.err" | cut -c1-200)"
    fi
    rm -rf "$dest"; sleep $(( attempt * 15 ))
  done
  echo "$(date -u +%FT%TZ) FAIL $path $size"
  return 1
}
export -f copy_one

# Heartbeat + log shipping + idle watchdog.
(
  while sleep 60; do
    done_n=$(grep -cE ' (DONE|SKIP) ' "$LOG")
    done_b=$(grep -E ' (DONE|SKIP) ' "$LOG" | awk '{s+=$4} END {printf "%d", s}')
    log "HEARTBEAT files=$done_n/$TOTAL_FILES bytes=$done_b/$TOTAL_BYTES disk_free=$(df --output=avail -h /data | tail -1 | tr -d ' ')"
    ship_log
  done
) &
HB=$!
(
  while sleep 120; do
    idle=$(( ( $(date +%s) - $(stat -c %Y /data/progress.stamp 2>/dev/null || date +%s) ) / 60 ))
    if [ "$idle" -ge "$IDLE_MIN" ]; then log "WATCHDOG no progress for ${idle}m, powering off"; ship_log; shutdown -h now; fi
  done
) &
WD=$!
touch /data/progress.stamp

# Workers; each finished file touches the progress stamp the watchdog reads.
tr '\t' '\n' < /data/filelist.tsv | \
  xargs -d '\n' -n 2 -P "$WORKERS" bash -c 'copy_one "$0" "$1"; touch /data/progress.stamp'

# Verify S3 against the HF list.
aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX/" \
  --query 'Contents[].[Key,Size]' --output text > /data/final.tsv
missing=$(awk -F'\t' -v P="$PREFIX/" 'NR==FNR {have[$1"\t"$2]=1; next} !((P $1"\t"$2) in have) {print $1}' /data/final.tsv /data/filelist.tsv)
s3_files=$(wc -l < /data/final.tsv)
s3_bytes=$(awk '{s+=$2} END {printf "%d", s}' /data/final.tsv)
if [ -z "$missing" ]; then
  log "VERIFY OK s3_files=$s3_files s3_bytes=$s3_bytes hf_files=$TOTAL_FILES hf_bytes=$TOTAL_BYTES"
else
  log "VERIFY MISSING $(echo "$missing" | wc -l) files: $(echo "$missing" | head -20 | tr '\n' ' ')"
fi
kill "$HB" "$WD" 2>/dev/null
log "EXIT powering off"
ship_log
shutdown -h now
