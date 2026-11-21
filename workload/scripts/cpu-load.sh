#!/usr/bin/env bash
set -euo pipefail

EXPECTED_HOST="${CPU_LOAD_HOST:-workload-vm2}"
MAX_SECONDS=900
LOG_FILE="${CPU_LOAD_LOG:-$HOME/cpu-load.log}"

usage() {
  echo "Cách dùng: $0 [-w số_worker] [-d số_giây]"
  echo "  -w  số tiến trình tải, 1..$(nproc) (mặc định: bằng nproc)"
  echo "  -d  thời lượng, 10..$MAX_SECONDS giây (mặc định: 420)"
}

log() {
  local line
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
  echo "$line"
  echo "$line" >> "$LOG_FILE"
}

workers="$(nproc)"
seconds=420
while getopts "w:d:h" opt; do
  case "$opt" in
    w) workers="$OPTARG" ;;
    d) seconds="$OPTARG" ;;
    h) usage; exit 0 ;;
    *) usage; exit 2 ;;
  esac
done

if [[ "$(hostname)" != "$EXPECTED_HOST" ]]; then
  echo "Từ chối: máy này là $(hostname), chỉ chạy trên $EXPECTED_HOST." >&2
  exit 1
fi
if ! [[ "$workers" =~ ^[0-9]+$ ]] || (( workers < 1 || workers > $(nproc) )); then
  echo "Số worker phải từ 1 đến $(nproc)." >&2
  exit 2
fi
if ! [[ "$seconds" =~ ^[0-9]+$ ]] || (( seconds < 10 || seconds > MAX_SECONDS )); then
  echo "Thời lượng phải từ 10 đến $MAX_SECONDS giây." >&2
  exit 2
fi

pids=()
cleanup() {
  trap - EXIT INT TERM
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
  log "KẾT THÚC host=$(hostname) workers=$workers"
}
trap cleanup EXIT
trap 'log "DỪNG SỚM theo yêu cầu"; exit 130' INT TERM

log "BẮT ĐẦU host=$(hostname) workers=$workers/$(nproc) seconds=$seconds"
for ((i = 0; i < workers; i++)); do
  timeout "$seconds" nice -n 10 yes > /dev/null &
  pids+=("$!")
done
wait "${pids[@]}" 2>/dev/null || true
