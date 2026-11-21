#!/usr/bin/env bash
set -euo pipefail

EXPECTED_HOST="${DISKTEST_HOST:-workload-vm2}"
BASE_DIR=/var/lib/moni-disktest
IMG="$BASE_DIR/disk.img"
MNT=/mnt/moni-disktest
MARKER="$MNT/.moni-disktest"
FILL_DIR="$MNT/fill"
LOG_FILE="$BASE_DIR/disktest.log"
LABEL=moni-disktest
SIZE_MB=256
MARGIN_MB=1024
MAX_TARGET=98

die() { echo "Lỗi: $*" >&2; exit 1; }

log() {
  local line
  line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $*"
  echo "$line"
  echo "$line" >> "$LOG_FILE"
}

preflight() {
  [[ "$(hostname)" == "$EXPECTED_HOST" ]] || die "máy này là $(hostname), chỉ chạy trên $EXPECTED_HOST."
  [[ $EUID -eq 0 ]] || die "cần chạy bằng sudo."
}

is_test_mount() {
  [[ "$(findmnt -n -o SOURCE --target "$MNT" 2>/dev/null)" == /dev/loop* ]] &&
    [[ "$(findmnt -n -o TARGET --target "$MNT")" == "$MNT" ]] &&
    [[ "$(losetup -n -O BACK-FILE -j "$IMG" 2>/dev/null | xargs)" == "$IMG" ]] &&
    [[ -f "$MARKER" ]]
}

require_test_mount() {
  is_test_mount || die "$MNT không phải filesystem thử đã xác minh; dừng, không ghi/xóa gì."
}

usage_pct() {
  df -P "$MNT" | awk 'NR==2 {gsub("%", "", $5); print $5}'
}

cmd_setup() {
  preflight
  if is_test_mount; then
    echo "Filesystem thử đã được mount tại $MNT, không tạo lại."
    exit 0
  fi
  [[ ! -e "$IMG" ]] || die "$IMG đã tồn tại nhưng chưa mount; dùng 'remount' hoặc 'teardown' thay vì ghi đè."
  if [[ -e "$MNT" ]] && [[ -n "$(ls -A "$MNT")" ]]; then
    die "$MNT đã có dữ liệu khác; không dùng thư mục này."
  fi
  mountpoint -q "$MNT" 2>/dev/null && die "$MNT đang là mountpoint của đối tượng khác."

  mkdir -p "$BASE_DIR"
  local free_mb
  free_mb=$(df -Pm "$BASE_DIR" | awk 'NR==2 {print $4}')
  log "KIỂM TRA nền: $(df -P "$BASE_DIR" | awk 'NR==2 {print $6}') còn ${free_mb} MiB, cần $((SIZE_MB + MARGIN_MB)) MiB"
  (( free_mb >= SIZE_MB + MARGIN_MB )) || die "filesystem nền không đủ chỗ trống."

  fallocate -l "${SIZE_MB}M" "$IMG"
  mkfs.ext4 -q -F -m 0 -L "$LABEL" "$IMG"
  mkdir -p "$MNT"
  mount -o loop,nodev,nosuid,noexec "$IMG" "$MNT"
  printf 'Filesystem thử của Moni Prototype.\nChỉ dùng để mô phỏng disk gần đầy; xóa bằng disktest.sh.\n' > "$MARKER"
  log "TẠO image=$IMG size=${SIZE_MB}MiB mount=$MNT"
  cmd_status
}

cmd_remount() {
  preflight
  if is_test_mount; then
    echo "Filesystem thử đang mount đúng, không cần remount."
    exit 0
  fi
  [[ -f "$IMG" ]] || die "không có $IMG; dùng 'setup' để tạo mới."
  [[ "$(blkid -o value -s LABEL "$IMG" 2>/dev/null)" == "$LABEL" ]] || die "$IMG không mang nhãn $LABEL; không mount."
  mountpoint -q "$MNT" 2>/dev/null && die "$MNT đang là mountpoint của đối tượng khác."
  mkdir -p "$MNT"
  mount -o loop,nodev,nosuid,noexec "$IMG" "$MNT"
  require_test_mount
  log "REMOUNT image=$IMG mount=$MNT use=$(usage_pct)%"
  cmd_status
}

cmd_status() {
  if ! is_test_mount; then
    echo "Chưa có filesystem thử hợp lệ tại $MNT." >&2
    [[ -e "$IMG" ]] && echo "Image $IMG vẫn còn: dùng 'remount' hoặc 'teardown'." >&2
    exit 1
  fi
  echo "Mount:"
  findmnt -o TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL,USE%,OPTIONS --target "$MNT"
  echo "Loop device:"
  losetup -O NAME,BACK-FILE -j "$IMG"
}

cmd_fill() {
  preflight
  local target="${1:-}"
  if ! [[ "$target" =~ ^[0-9]+$ ]] || (( target < 1 || target > MAX_TARGET )); then
    die "mức mục tiêu phải từ 1 đến $MAX_TARGET (%)."
  fi
  require_test_mount

  local size_mb avail_mb need_mb before
  read -r size_mb avail_mb < <(df -Pm "$MNT" | awk 'NR==2 {print $2, $4}')
  before=$(usage_pct)
  need_mb=$(( avail_mb - size_mb * (100 - target) / 100 ))
  if (( need_mb <= 0 )); then
    echo "Đã ở mức ${before}%, không cần ghi thêm."
    exit 0
  fi
  (( need_mb <= avail_mb - 2 )) || need_mb=$(( avail_mb - 2 ))

  mkdir -p "$FILL_DIR"
  local file
  file="$FILL_DIR/fill-$(date -u +%Y%m%dT%H%M%SZ).bin"
  log "GHI BẮT ĐẦU target=${target}% before=${before}% write=${need_mb}MiB file=$file"
  require_test_mount
  dd if=/dev/zero of="$file" bs=1M count="$need_mb" conv=fsync status=none
  log "GHI XONG use=$(usage_pct)%"
}

cmd_clean() {
  preflight
  require_test_mount
  local before
  before=$(usage_pct)
  if [[ -d "$FILL_DIR" ]]; then
    find "$FILL_DIR" -maxdepth 1 -type f -name 'fill-*.bin' -delete
    rmdir "$FILL_DIR" 2>/dev/null || true
  fi
  sync
  log "XÓA dữ liệu thử before=${before}% after=$(usage_pct)%"
}

cmd_teardown() {
  preflight
  if is_test_mount; then
    cmd_clean
    umount "$MNT"
    log "UNMOUNT $MNT"
  elif mountpoint -q "$MNT" 2>/dev/null; then
    die "$MNT đang mount một đối tượng không phải filesystem thử; không tháo."
  fi
  local loopdev
  for loopdev in $(losetup -n -O NAME -j "$IMG" 2>/dev/null); do
    losetup -d "$loopdev"
    log "THÁO loop $loopdev"
  done
  if [[ -f "$IMG" ]]; then
    rm -f "$IMG"
    log "XÓA image $IMG"
  fi
  if [[ -d "$MNT" ]] && [[ -z "$(ls -A "$MNT")" ]]; then
    rmdir "$MNT"
  fi
  log "THU DỌN xong; nhật ký giữ tại $LOG_FILE"
}

case "${1:-}" in
  setup) cmd_setup ;;
  remount) cmd_remount ;;
  status) cmd_status ;;
  fill) cmd_fill "${2:-}" ;;
  clean) cmd_clean ;;
  teardown) cmd_teardown ;;
  *) echo "Cách dùng: sudo $0 setup|status|fill <phần trăm>|clean|remount|teardown"; exit 2 ;;
esac
