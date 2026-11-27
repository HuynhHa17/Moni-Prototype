"""Build Prometheus file_sd target files from inventory.yml or a lab's private .env.

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
    "WORKLOAD_CADVISOR_PORT", "WORKLOAD_VM3_CADVISOR_PORT",
    "DEFAULT_SITE", "DEFAULT_RACK", "DEFAULT_TEAM",
}
VALID_PROFILES = {"node", "http", "cadvisor", "snmp", "redfish"}


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


def _parse_scalar(raw: str, where: str):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part, where) for part in inner.split(",")]
    if raw.startswith(("'", '"')):
        if len(raw) < 2 or raw[-1] != raw[0]:
            raise ValueError(f"{where}: unmatched quote")
        value = raw[1:-1]
    else:
        value = raw
    if "$" in value or "`" in value:
        raise ValueError(f"{where}: use a literal value, without shell expansion")
    return value


def _strip_comment(line: str) -> str:
    in_quote: str | None = None
    for idx, ch in enumerate(line):
        if ch in ("'", '"'):
            if in_quote is None:
                in_quote = ch
            elif in_quote == ch:
                in_quote = None
        elif ch == "#" and in_quote is None:
            return line[:idx]
    return line


def read_inventory(path: Path) -> dict:
    """Parse inventory.yml (JSON or structured YAML subset) using stdlib only."""
    text = path.read_text(encoding="utf-8-sig")
    stripped = text.strip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: root must be a mapping")
        return data

    lines: list[tuple[int, int, str]] = []
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        cleaned = _strip_comment(raw_line).rstrip()
        if not cleaned.strip():
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        if "\t" in cleaned[:indent]:
            raise ValueError(f"{path.name}:{line_no}: tabs are not allowed for indentation")
        lines.append((line_no, indent, cleaned.strip()))

    def parse_block(index: int, min_indent: int):
        if index >= len(lines):
            return {}, index
        is_list = lines[index][2].startswith("- ") or lines[index][2] == "-"
        if is_list:
            items = []
            list_indent = lines[index][1]
            while index < len(lines) and lines[index][1] == list_indent:
                line_no, indent, content = lines[index]
                if not (content.startswith("- ") or content == "-"):
                    break
                rest = content[2:].strip() if content.startswith("- ") else ""
                index += 1
                if not rest:
                    val, index = parse_block(index, indent + 1)
                    items.append(val)
                elif ":" in rest and not rest.startswith(("'", '"', "[")):
                    key, _, raw_val = rest.partition(":")
                    key = key.strip()
                    item: dict = {}
                    raw_val = raw_val.strip()
                    if raw_val:
                        item[key] = _parse_scalar(raw_val, f"{path.name}:{line_no}")
                    else:
                        item[key], index = parse_block(index, indent + 2)
                    while index < len(lines) and lines[index][1] > indent:
                        sub_line_no, sub_indent, sub_content = lines[index]
                        if ":" not in sub_content:
                            raise ValueError(f"{path.name}:{sub_line_no}: expected key: value")
                        sk, _, sv = sub_content.partition(":")
                        sk, sv = sk.strip(), sv.strip()
                        index += 1
                        if sv:
                            item[sk] = _parse_scalar(sv, f"{path.name}:{sub_line_no}")
                        else:
                            item[sk], index = parse_block(index, sub_indent + 1)
                    items.append(item)
                else:
                    items.append(_parse_scalar(rest, f"{path.name}:{line_no}"))
            return items, index

        mapping: dict = {}
        map_indent = lines[index][1]
        while index < len(lines) and lines[index][1] == map_indent:
            line_no, indent, content = lines[index]
            if content.startswith("- "):
                break
            if ":" not in content:
                raise ValueError(f"{path.name}:{line_no}: expected key: value")
            key, _, raw_val = content.partition(":")
            key, raw_val = key.strip(), raw_val.strip()
            if key in mapping:
                raise ValueError(f"{path.name}:{line_no}: duplicate key {key}")
            index += 1
            if raw_val:
                mapping[key] = _parse_scalar(raw_val, f"{path.name}:{line_no}")
            else:
                if index < len(lines) and lines[index][1] > indent:
                    mapping[key], index = parse_block(index, indent + 1)
                else:
                    mapping[key] = {}
        return mapping, index

    parsed, _ = parse_block(0, 0)
    if not isinstance(parsed, dict):
        raise ValueError(f"{path.name}: root must be a mapping")
    return parsed


def label(value: str, key: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,62}", value):
        raise ValueError(f"{key}: expected a non-empty label (letters, numbers, _, ., -)")
    return value


def validate_ip(raw_address: str, key: str) -> str:
    try:
        address = ipaddress.ip_address(str(raw_address))
    except ValueError as exc:
        raise ValueError(f"{key}: set the actual IPv4 or IPv6 lab address") from exc
    if address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError(f"{key}: must identify a reachable workload VM")
    return f"[{address}]" if address.version == 6 else str(address)


def port_value(values: dict[str, str], key: str, default: str) -> str:
    return validate_port(values.get(key, default), key)


def validate_port(raw_port, key: str) -> str:
    port = str(raw_port)
    if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError(f"{key}: expected a port from 1 to 65535")
    return port


def env_to_inventory(values: dict[str, str]) -> dict:
    """Convert legacy .env key-value pairs into the structured inventory format."""
    environment = values.get("ENVIRONMENT", "lab")
    defaults = {
        "site": values.get("DEFAULT_SITE", "onprem-lab"),
        "rack": values.get("DEFAULT_RACK", "rack-01"),
        "team": values.get("DEFAULT_TEAM", "infra"),
    }
    hosts = []
    for prefix, default_host in (("WORKLOAD", "workload-vm2"), ("WORKLOAD_VM3", "workload-vm3")):
        raw_address = values.get(f"{prefix}_IP", "")
        if prefix == "WORKLOAD_VM3" and not raw_address:
            continue
        http_port = port_value(values, f"{prefix}_HTTP_PORT", "8080")
        cadvisor_port = port_value(values, f"{prefix}_CADVISOR_PORT", "8081")
        if cadvisor_port == http_port:
            raise ValueError(f"{prefix}_CADVISOR_PORT: must differ from {prefix}_HTTP_PORT")
        hosts.append({
            "host": values.get(f"{prefix}_HOST", default_host),
            "address": raw_address,
            "site": defaults["site"],
            "rack": defaults["rack"],
            "team": defaults["team"],
            "profiles": ["node", "http", "cadvisor"],
            "node_port": "9100",
            "cadvisor_port": cadvisor_port,
            "http_probes": [{"service": "moni-nginx", "port": http_port, "path": "/health"}],
            "_ip_key": f"{prefix}_IP",
            "_host_key": f"{prefix}_HOST",
        })
    return {"environment": environment, "defaults": defaults, "hosts": hosts}


def build_targets_from_inventory(inventory: dict) -> dict[str, list[dict] | dict]:
    environment = label(str(inventory.get("environment", "lab")), "environment")
    defaults = inventory.get("defaults") or {}
    default_site = label(str(defaults.get("site", "onprem-lab")), "defaults.site")
    default_rack = label(str(defaults.get("rack", "rack-01")), "defaults.rack")
    default_team = label(str(defaults.get("team", "infra")), "defaults.team")

    raw_hosts = inventory.get("hosts")
    if not isinstance(raw_hosts, list) or not raw_hosts:
        raise ValueError("inventory.hosts must be a non-empty list")

    nodes, probes, containers, snmps, redfishes = [], [], [], [], []
    seen_hosts: set[str] = set()
    seen_node_addrs: set[str] = set()
    seen_target_ids: set[tuple[str, str, str]] = set()

    for idx, entry in enumerate(raw_hosts):
        if not isinstance(entry, dict):
            raise ValueError(f"hosts[{idx}] must be a mapping")
        host_key = entry.get("_host_key", f"hosts[{idx}].host")
        ip_key = entry.get("_ip_key", f"hosts[{idx}].address")
        host = label(str(entry.get("host", "")), host_key)
        authority = validate_ip(entry.get("address", ""), ip_key)
        site = label(str(entry.get("site", default_site)), f"hosts[{idx}].site")
        rack = label(str(entry.get("rack", default_rack)), f"hosts[{idx}].rack")
        team = label(str(entry.get("team", default_team)), f"hosts[{idx}].team")

        if host in seen_hosts:
            raise ValueError("Each workload must have a distinct host label and IP address")
        seen_hosts.add(host)

        profiles = entry.get("profiles") or ["node"]
        if not isinstance(profiles, list) or not profiles:
            raise ValueError(f"hosts[{idx}].profiles must be a non-empty list")
        unknown = [p for p in profiles if p not in VALID_PROFILES]
        if unknown:
            raise ValueError(f"hosts[{idx}].profiles has unsupported profile(s): {unknown}")

        if "node" in profiles:
            if authority in seen_node_addrs:
                raise ValueError("Each workload must have a distinct host label and IP address")
            seen_node_addrs.add(authority)

        base_labels = {
            "host": host,
            "environment": environment,
            "site": site,
            "rack": rack,
            "team": team,
        }

        def register(job: str, target_id: str, extra: dict | None = None) -> dict:
            tid = label(target_id, f"hosts[{idx}].target_id")
            key = (job, host, tid)
            if key in seen_target_ids:
                raise ValueError(f"Duplicate target_id {tid} for ({job}, {host})")
            seen_target_ids.add(key)
            return {**base_labels, **(extra or {}), "target_id": tid}

        if "node" in profiles:
            node_port = validate_port(entry.get("node_port", "9100"), f"hosts[{idx}].node_port")
            nodes.append({
                "targets": [f"{authority}:{node_port}"],
                "labels": register("node", f"node-{host}"),
            })

        if "http" in profiles:
            http_probes = entry.get("http_probes") or [
                {"service": "moni-nginx", "port": entry.get("http_port", "8080"), "path": "/health"}
            ]
            if not isinstance(http_probes, list) or not http_probes:
                raise ValueError(f"hosts[{idx}].http_probes must be a non-empty list")
            used_http_ports: set[str] = set()
            for p_idx, probe in enumerate(http_probes):
                svc = label(str(probe.get("service", f"svc-{p_idx}")), f"hosts[{idx}].http_probes[{p_idx}].service")
                p_port = validate_port(probe.get("port", "8080"), f"hosts[{idx}].http_probes[{p_idx}].port")
                used_http_ports.add(p_port)
                path = str(probe.get("path", "/health"))
                if not path.startswith("/"):
                    raise ValueError(f"hosts[{idx}].http_probes[{p_idx}].path must start with /")
                scheme = str(probe.get("scheme", "http"))
                if scheme not in ("http", "https"):
                    raise ValueError(f"hosts[{idx}].http_probes[{p_idx}].scheme must be http or https")
                tid = str(probe.get("target_id", f"http-{host}-{svc}"))
                probes.append({
                    "targets": [f"{scheme}://{authority}:{p_port}{path}"],
                    "labels": register("http", tid, {"service": svc}),
                })
        else:
            used_http_ports = set()

        if "cadvisor" in profiles:
            cadvisor_port = validate_port(entry.get("cadvisor_port", "8081"), f"hosts[{idx}].cadvisor_port")
            if cadvisor_port in used_http_ports:
                raise ValueError(f"hosts[{idx}].cadvisor_port must differ from http port")
            containers.append({
                "targets": [f"{authority}:{cadvisor_port}"],
                "labels": register("cadvisor", f"cadvisor-{host}"),
            })

        if "snmp" in profiles:
            snmp_port = validate_port(entry.get("snmp_port", "161"), f"hosts[{idx}].snmp_port")
            snmp_module = label(str(entry.get("snmp_module", "ups_mib")), f"hosts[{idx}].snmp_module")
            snmps.append({
                "targets": [f"{authority}:{snmp_port}"],
                "labels": register("snmp", f"snmp-{host}", {"snmp_module": snmp_module}),
            })

        if "redfish" in profiles:
            redfish_port = validate_port(entry.get("redfish_port", "8000"), f"hosts[{idx}].redfish_port")
            redfishes.append({
                "targets": [f"{authority}:{redfish_port}"],
                "labels": register("redfish", f"redfish-{host}"),
            })

    job_map = [
        ("node", nodes),
        ("http", probes),
        ("cadvisor", containers),
        ("snmp", snmps),
        ("redfish", redfishes),
    ]
    result: dict[str, list[dict] | dict] = {
        "node.json": nodes,
        "http.json": probes,
        "cadvisor.json": containers,
        "expected.rules.yml": inventory_rules(job_map),
    }
    if snmps:
        result["snmp.json"] = snmps
    if redfishes:
        result["redfish.json"] = redfishes
    return result


def build_targets(values: dict[str, str]) -> dict[str, list[dict] | dict]:
    """Build target files from a .env dict (backward-compatible entry point)."""
    return build_targets_from_inventory(env_to_inventory(values))


def inventory_rules(job_entries: list[tuple[str, list[dict]]]) -> dict:
    """Recording rules listing each target the lab expects, independent of service discovery."""
    rules = []
    for job, entries in job_entries:
        for entry in entries:
            rules.append({
                "record": "moni:target_expected",
                "expr": "vector(1)",
                "labels": {"job": job, **entry["labels"]},
            })
    return {"groups": [{"name": "moni_inventory", "rules": rules}]}


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
    parser.add_argument("--inventory-file", type=Path, default=None,
                        help="path to inventory.yml (preferred when present)")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env",
                        help="path to .env (legacy fallback when --inventory-file is omitted)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".runtime/prometheus/targets")
    args = parser.parse_args()
    try:
        if args.inventory_file is not None:
            targets = build_targets_from_inventory(read_inventory(args.inventory_file))
        else:
            targets = build_targets(read_env(args.env_file))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(args.output_dir, 0o755)
        for name, entries in targets.items():
            write_atomic(args.output_dir / name, json.dumps(entries, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError) as exc:
        print(f"Render failed: {exc}", file=sys.stderr)
        return 1
    print(f"Rendered {len(targets['node.json'])} node target(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
