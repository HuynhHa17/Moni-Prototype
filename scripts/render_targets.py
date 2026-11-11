"""Build Prometheus file_sd target files from a lab's private .env.

No network access or deployment is performed. Uses only Python's standard library.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_KEYS = {
    "WORKLOAD_IP", "WORKLOAD_HOST", "WORKLOAD_HTTP_PORT", "ENVIRONMENT",
    "WORKLOAD_VM3_IP", "WORKLOAD_VM3_HOST", "WORKLOAD_VM3_HTTP_PORT",
}


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key.strip()):
            raise ValueError(f"{path.name}:{line_number}: expected KEY=value")
        key, value = key.strip(), value.strip()
        if key in values:
            raise ValueError(f"{path.name}:{line_number}: duplicate key {key}")
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"{path.name}:{line_number}: unmatched quote")
            value = value[1:-1]
        if key in INVENTORY_KEYS and ("$" in value or "`" in value):
            raise ValueError(f"{key}: use a literal value, without shell expansion")
        values[key] = value
    return values


def label(value: str, key: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}", value):
        raise ValueError(f"{key}: expected a non-empty label (letters, numbers, _, ., -)")
    return value


def build_targets(values: dict[str, str]) -> dict[str, list[dict]]:
    environment = label(values.get("ENVIRONMENT", "lab"), "ENVIRONMENT")
    nodes, probes = [], []
    hosts: set[str] = set()
    addresses: set[str] = set()
    for prefix, default_host in (("WORKLOAD", "workload-vm2"), ("WORKLOAD_VM3", "workload-vm3")):
        raw_address = values.get(f"{prefix}_IP", "")
        if prefix == "WORKLOAD_VM3" and not raw_address:
            continue
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise ValueError(f"{prefix}_IP: set the actual IPv4 or IPv6 lab address") from exc
        if address.is_unspecified or address.is_multicast or address.is_loopback:
            raise ValueError(f"{prefix}_IP: must identify a reachable workload VM")
        host = label(values.get(f"{prefix}_HOST", default_host), f"{prefix}_HOST")
        port = values.get(f"{prefix}_HTTP_PORT", "8080")
        if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError(f"{prefix}_HTTP_PORT: expected a port from 1 to 65535")
        if host in hosts or str(address) in addresses:
            raise ValueError("Each workload must have a distinct host label and IP address")
        hosts.add(host)
        addresses.add(str(address))
        authority = f"[{address}]" if address.version == 6 else str(address)
        common = {"host": host, "environment": environment}
        nodes.append({"targets": [f"{authority}:9100"], "labels": common})
        probes.append({"targets": [f"http://{authority}:{port}/health"],
                       "labels": {**common, "service": "moni-nginx"}})
    return {"node.json": nodes, "http.json": probes}


def write_atomic(path: Path, text: str) -> None:
    descriptor, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".runtime/prometheus/targets")
    args = parser.parse_args()
    try:
        targets = build_targets(read_env(args.env_file))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(args.output_dir, 0o755)
        for name, entries in targets.items():
            write_atomic(args.output_dir / name, json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError) as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 1
    print(f"Rendered {len(targets['node.json'])} workload(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
