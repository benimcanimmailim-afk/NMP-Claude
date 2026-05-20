#!/usr/bin/env python3
"""
Network Monitor Pro v2
Dark Cyber Dashboard — pywebview + Python async backend
Windows Roaming AppData storage + full cyber toolkit
"""

import webview
import threading
import subprocess
import socket
import json
import os
import re
import sys
import ipaddress
import platform
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ─── PLATFORM DETECT ──────────────────────────────────────────────────────────
SYSTEM = platform.system().lower()

# ─── ROAMING APP DATA PATH ────────────────────────────────────────────────────
def get_appdata_dir() -> Path:
    if SYSTEM == "windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        p = Path(base) / "NetworkMonitorPro"
    elif SYSTEM == "darwin":
        p = Path.home() / "Library" / "Application Support" / "NetworkMonitorPro"
    else:
        p = Path.home() / ".config" / "NetworkMonitorPro"
    p.mkdir(parents=True, exist_ok=True)
    return p

APP_DIR      = get_appdata_dir()
PROFILES_DIR = APP_DIR / "profiles"
PROFILES_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = APP_DIR / "settings.json"

# ─── SETTINGS ─────────────────────────────────────────────────────────────────
def load_settings() -> dict:
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text("utf-8"))
    except Exception:
        pass
    return {"theme": "dark"}

def save_settings(data: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), "utf-8")
    except Exception:
        pass

# ─── OUI / VENDOR DB ──────────────────────────────────────────────────────────
OUI_DB = {
    "00:00:0C":"Cisco","00:1A:A1":"Cisco","00:1B:D4":"Cisco",
    "FC:FB:FB":"Cisco","D0:C7:C0":"Cisco","58:AC:78":"Cisco",
    "00:50:56":"VMware","00:0C:29":"VMware","00:1C:42":"Parallels",
    "B4:99:BA":"HP","00:1E:0B":"HP","3C:D9:2B":"HP",
    "00:25:B3":"HP","00:30:C1":"HP Enterprise","FC:15:B4":"HP",
    "48:0F:CF":"Huawei","00:46:4B":"Huawei","70:72:CF":"Huawei",
    "AC:4E:91":"Huawei","00:18:82":"Huawei","54:89:98":"Huawei",
    "00:1B:21":"Intel","00:1F:3B":"Intel","00:21:6A":"Intel",
    "3C:97:0E":"Apple","A4:5E:60":"Apple","F0:18:98":"Apple",
    "00:17:F2":"Apple","AC:87:A3":"Apple","28:37:37":"Apple",
    "00:50:B6":"MikroTik","4C:5E:0C":"MikroTik","2C:C8:1B":"MikroTik",
    "E4:8D:8C":"MikroTik","DC:2C:6E":"MikroTik",
    "00:15:17":"Aruba","00:0B:86":"Aruba Networks","94:B4:0F":"Aruba",
    "B8:27:EB":"Raspberry Pi","DC:A6:32":"Raspberry Pi","E4:5F:01":"Raspberry Pi",
    "00:1A:2B":"Juniper","00:19:E2":"Juniper","28:8A:1C":"Juniper",
    "00:0D:60":"Fortinet","70:4C:A5":"Fortinet","90:6C:AC":"Fortinet",
    "00:11:6B":"D-Link","1C:7E:E5":"D-Link","00:1E:58":"D-Link",
    "C8:3A:35":"TP-Link","50:C7:BF":"TP-Link","14:CC:20":"TP-Link",
    "A0:F3:C1":"TP-Link","B0:BE:76":"TP-Link",
    "00:90:F5":"Zyxel","00:A0:C5":"Zyxel","58:8B:F3":"Zyxel",
    "00:0A:49":"Ubiquiti","04:18:D6":"Ubiquiti","F0:9F:C2":"Ubiquiti",
    "78:8A:20":"Ubiquiti","24:A4:3C":"Ubiquiti",
    "00:17:88":"Philips Hue","00:1C:B3":"Samsung","B8:27:EB":"Raspberry Pi",
    "28:6C:07":"Dell","00:14:22":"Dell","F8:BC:12":"Dell","18:60:24":"Dell",
    "00:1D:72":"Lenovo","7C:5C:F8":"Lenovo","54:EE:75":"Lenovo",
    "00:03:93":"Apple","00:05:02":"Apple","00:1C:B3":"Samsung",
    "CC:46:D6":"Cisco Meraki","00:50:F2":"Microsoft","7C:1E:52":"Microsoft",
    "00:15:5D":"Microsoft (Hyper-V)","00:03:FF":"Microsoft",
}

CRITICAL_PORTS = {
    21:"FTP", 22:"SSH", 23:"Telnet", 25:"SMTP",
    53:"DNS", 80:"HTTP", 110:"POP3", 143:"IMAP",
    443:"HTTPS", 445:"SMB", 3306:"MySQL", 3389:"RDP",
    5900:"VNC", 8080:"HTTP-Alt", 8443:"HTTPS-Alt", 9090:"WebAdmin"
}

def get_vendor(mac: str) -> str:
    if not mac or mac in ("N/A", ""):
        return "Unknown"
    prefix = mac.upper().replace("-",":")[:8]
    return OUI_DB.get(prefix, "Unknown")

def ping_host(ip: str, timeout: int = 2) -> dict:
    try:
        if SYSTEM == "windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout + 3)
        out = result.stdout.decode("utf-8", errors="ignore")
        if result.returncode == 0:
            m = re.search(r"[Tt]ime[<=](\d+\.?\d*)\s*ms", out)
            if not m:
                m = re.search(r"(\d+\.?\d*)\s*ms", out)
            return {"alive": True, "latency": float(m.group(1)) if m else 0.0}
        return {"alive": False, "latency": None}
    except Exception:
        return {"alive": False, "latency": None}

def get_mac_for_ip(ip: str) -> str:
    try:
        cmd = ["arp", "-a", ip] if SYSTEM == "windows" else ["arp", "-n", ip]
        result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=3)
        out = result.stdout.decode("utf-8", errors="ignore")
        m = re.search(r"(([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2})", out)
        return m.group(1).upper().replace("-",":") if m else "N/A"
    except Exception:
        return "N/A"

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════════
class Api:
    """Python API — exposed to JS via pywebview bridge."""

    def __init__(self):
        self._devices   = {}       # ip -> device dict
        self._threads   = {}       # ip -> Thread
        self._running   = True
        self._lock      = threading.Lock()
        self._settings  = load_settings()

    # ── helpers ───────────────────────────────────────────────────────────────
    def _push(self, js: str):
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(js)
        except Exception:
            pass

    def _push_json(self, fn: str, data):
        payload = json.dumps(data, ensure_ascii=False)\
                      .replace("\\","\\\\").replace("'","\\'").replace("\n","\\n")
        self._push(f"window.{fn}('{payload}')")

    # ── settings ──────────────────────────────────────────────────────────────
    def get_settings(self) -> dict:
        return self._settings

    def set_theme(self, theme: str) -> dict:
        self._settings["theme"] = theme
        save_settings(self._settings)
        return {"ok": True}

    # ── device CRUD ───────────────────────────────────────────────────────────
    def add_device(self, ip: str, label: str = "") -> dict:
        ip = ip.strip()
        if not ip:
            return {"ok": False, "error": "Boş IP"}
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return {"ok": False, "error": f"Geçersiz IP: {ip}"}
        with self._lock:
            if ip not in self._devices:
                self._devices[ip] = {
                    "ip": ip, "label": label or ip,
                    "mac": "N/A", "vendor": "Unknown",
                    "alive": None, "latency": None,
                    "hostname": "", "log": []
                }
                self._start_ping(ip)
        return {"ok": True, "ip": ip}

    def add_devices_bulk(self, text: str) -> dict:
        added, errors = [], []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            r = self.add_device(parts[0], parts[1] if len(parts) > 1 else "")
            (added if r["ok"] else errors).append(parts[0])
        return {"added": added, "errors": errors}

    def remove_device(self, ip: str) -> dict:
        with self._lock:
            self._devices.pop(ip, None)
        return {"ok": True}

    def clear_all_devices(self) -> dict:
        with self._lock:
            self._devices.clear()
        return {"ok": True}

    def get_devices(self) -> list:
        with self._lock:
            return list(self._devices.values())

    def set_label(self, ip: str, label: str) -> dict:
        with self._lock:
            if ip in self._devices:
                self._devices[ip]["label"] = label
                self._save_current_profile_if_any()
                return {"ok": True}
        return {"ok": False}

    def get_log(self, ip: str) -> list:
        with self._lock:
            return list(self._devices.get(ip, {}).get("log", []))

    # ── network tools ─────────────────────────────────────────────────────────
    def resolve_hostname(self, ip: str) -> dict:
        try:
            socket.setdefaulttimeout(3)
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = "Çözümlenemedi"
        with self._lock:
            if ip in self._devices:
                self._devices[ip]["hostname"] = hostname
        return {"ip": ip, "hostname": hostname}

    def fetch_mac_vendor(self, ip: str) -> dict:
        mac = get_mac_for_ip(ip)
        vendor = get_vendor(mac)
        with self._lock:
            if ip in self._devices:
                self._devices[ip]["mac"]    = mac
                self._devices[ip]["vendor"] = vendor
        return {"ip": ip, "mac": mac, "vendor": vendor}

    def port_scan(self, ip: str) -> dict:
        """Scan critical ports, return results list."""
        results = []
        def check(port):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.8)
                c = s.connect_ex((ip, port))
                s.close()
                return port, c == 0
            except Exception:
                return port, False

        with ThreadPoolExecutor(max_workers=16) as ex:
            futures = {ex.submit(check, p): p for p in CRITICAL_PORTS}
            for f in as_completed(futures):
                port, open_ = f.result()
                results.append({"port": port, "service": CRITICAL_PORTS[port], "open": open_})
        results.sort(key=lambda x: x["port"])
        return {"ip": ip, "results": results}

    def traceroute(self, ip: str) -> dict:
        """Run traceroute/tracert and return output lines."""
        try:
            if SYSTEM == "windows":
                cmd = ["tracert", "-d", "-h", "20", "-w", "1000", ip]
            else:
                cmd = ["traceroute", "-n", "-m", "20", "-w", "2", ip]
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=60)
            lines = result.stdout.decode("utf-8", errors="ignore").splitlines()
            return {"ok": True, "lines": lines}
        except subprocess.TimeoutExpired:
            return {"ok": False, "lines": ["Zaman aşımı (60s)"]}
        except Exception as e:
            return {"ok": False, "lines": [str(e)]}

    def open_cmd_ping(self, ip: str) -> dict:
        try:
            if SYSTEM == "windows":
                subprocess.Popen(f'start cmd /k ping {ip} -t', shell=True)
            elif SYSTEM == "darwin":
                script = f'tell application "Terminal" to do script "ping {ip}"'
                subprocess.Popen(["osascript", "-e", script])
            else:
                for term in ["gnome-terminal","xterm","konsole","xfce4-terminal"]:
                    try:
                        subprocess.Popen([term, "--", "bash", "-c", f"ping {ip}; read"]); break
                    except FileNotFoundError:
                        continue
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def open_web(self, ip: str, https: bool = False) -> dict:
        import webbrowser
        url = f"{'https' if https else 'http'}://{ip}"
        webbrowser.open(url)
        return {"ok": True}

    def open_ssh(self, ip: str, user: str = "") -> dict:
        u = user or os.getenv("USERNAME", "admin")
        try:
            if SYSTEM == "windows":
                subprocess.Popen(f'start cmd /k ssh {u}@{ip}', shell=True)
            elif SYSTEM == "darwin":
                script = f'tell application "Terminal" to do script "ssh {u}@{ip}"'
                subprocess.Popen(["osascript", "-e", script])
            else:
                for term in ["gnome-terminal","xterm","konsole"]:
                    try:
                        subprocess.Popen([term, "--", "bash", "-c", f"ssh {u}@{ip}; read"]); break
                    except FileNotFoundError:
                        continue
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    def open_rdp(self, ip: str) -> dict:
        try:
            if SYSTEM == "windows":
                subprocess.Popen(["mstsc", f"/v:{ip}"])
            else:
                return {"ok": False, "error": "RDP yalnızca Windows'ta desteklenir"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True}

    # ── network scanner ───────────────────────────────────────────────────────
    def scan_network(self, start_ip: str, end_ip: str, workers: int = 64) -> dict:
        try:
            start = ipaddress.ip_address(start_ip.strip())
            end   = ipaddress.ip_address(end_ip.strip())
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if int(end) - int(start) > 1024:
            return {"ok": False, "error": "Aralık çok büyük (maks 1024)"}

        def _task():
            ips   = [str(ipaddress.ip_address(i)) for i in range(int(start), int(end)+1)]
            total = len(ips)
            found = []
            with ThreadPoolExecutor(max_workers=workers) as ex:
                ftrs = {ex.submit(ping_host, ip): ip for ip in ips}
                done = 0
                for f in as_completed(ftrs):
                    ip  = ftrs[f]
                    res = f.result()
                    done += 1
                    pct = int(done / total * 100)
                    self._push(f"window._onScanProgress({pct})")
                    if res["alive"]:
                        mac    = get_mac_for_ip(ip)
                        vendor = get_vendor(mac)
                        found.append({"ip":ip,"mac":mac,"vendor":vendor,"latency":res["latency"]})
            self._push_json("_onScanComplete", found)

        threading.Thread(target=_task, daemon=True).start()
        return {"ok": True}

    # ── profile management ────────────────────────────────────────────────────
    def save_profile(self, name: str) -> dict:
        if not name.strip():
            return {"ok": False, "error": "Boş isim"}
        safe = re.sub(r'[^a-zA-Z0-9_\- ]','', name).strip()
        path = PROFILES_DIR / f"{safe}.json"
        with self._lock:
            data = list(self._devices.values())
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")
        return {"ok": True, "name": safe}

    def load_profile(self, name: str) -> dict:
        path = PROFILES_DIR / f"{name}.json"
        if not path.exists():
            return {"ok": False, "error": "Profil bulunamadı"}
        data = json.loads(path.read_text("utf-8"))
        with self._lock:
            self._devices.clear()
        for d in data:
            self.add_device(d.get("ip",""), d.get("label",""))
        return {"ok": True, "devices": data}

    def delete_profile(self, name: str) -> dict:
        p = PROFILES_DIR / f"{name}.json"
        if p.exists():
            p.unlink()
            return {"ok": True}
        return {"ok": False, "error": "Bulunamadı"}

    def list_profiles(self) -> list:
        return [p.stem for p in sorted(PROFILES_DIR.glob("*.json"))]

    def _save_current_profile_if_any(self):
        pass  # could auto-save; left as hook

    # ── ping engine ───────────────────────────────────────────────────────────
    def _start_ping(self, ip: str):
        t = threading.Thread(target=self._ping_loop, args=(ip,), daemon=True)
        self._threads[ip] = t
        t.start()

    def _ping_loop(self, ip: str):
        import time
        prev_alive = None
        while self._running:
            with self._lock:
                if ip not in self._devices:
                    break
            res = ping_host(ip, timeout=2)
            now = ts()
            with self._lock:
                if ip not in self._devices:
                    break
                dev = self._devices[ip]
                cur = res["alive"]
                # log state changes
                if prev_alive is not None and cur != prev_alive:
                    if cur:
                        dev["log"].insert(0, f"[{now}] ✅ Cihaz Geri Geldi")
                    else:
                        dev["log"].insert(0, f"[{now}] ❌ Cihaz Erişilemez Oldu")
                    dev["log"] = dev["log"][:50]
                elif prev_alive is None and not cur:
                    dev["log"].insert(0, f"[{now}] ❌ İzleme Başladı (Erişilemez)")
                    dev["log"] = dev["log"][:50]
                dev["alive"]   = cur
                dev["latency"] = res["latency"]
                prev_alive = cur
                payload = {"ip": ip, "alive": cur, "latency": res["latency"]}
            self._push_json("_onPingUpdate", payload)
            time.sleep(5)

    def shutdown(self):
        self._running = False


# ══════════════════════════════════════════════════════════════════════════════
# HTML / CSS / JS  (single-file inline)
# ══════════════════════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Network Monitor Pro</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Exo+2:wght@300;400;600;700;900&display=swap');

/* ── TOKENS ── */
:root {
  --bg:      #1a1c23;
  --surface: #222531;
  --hover:   #2a2f42;
  --border:  #2e3347;
  --accent:  #00d4ff;
  --green:   #10b981;
  --red:     #ef4444;
  --yellow:  #f59e0b;
  --text:    #e2e8f0;
  --muted:   #64748b;
  --mono:    'JetBrains Mono','Consolas',monospace;
  --head:    'Exo 2',sans-serif;
  --radius:  10px;
  --trans:   .18s ease;
}
.light-mode {
  --bg:      #f0f2f7;
  --surface: #ffffff;
  --hover:   #e8ecf4;
  --border:  #d1d9e6;
  --accent:  #0077b6;
  --text:    #1e2130;
  --muted:   #6b7280;
}

* { box-sizing:border-box; margin:0; padding:0; }
::-webkit-scrollbar { width:5px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--border); border-radius:99px; }
html,body { height:100%; background:var(--bg); color:var(--text);
            font-family:var(--head); overflow:hidden; transition:background var(--trans),color var(--trans); }

/* Grid background (dark only) */
body:not(.light-mode)::before {
  content:''; position:fixed; inset:0; z-index:0; pointer-events:none;
  background-image:linear-gradient(rgba(0,212,255,.025) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(0,212,255,.025) 1px,transparent 1px);
  background-size:40px 40px;
  animation:gridDrift 80s linear infinite;
}
@keyframes gridDrift{ to{ background-position:40px 40px; } }

/* ── HEADER ── */
header {
  position:fixed; top:0; left:0; right:0; z-index:100;
  height:62px;
  background:color-mix(in srgb, var(--bg) 94%, transparent);
  border-bottom:1px solid var(--border);
  backdrop-filter:blur(14px);
  display:flex; align-items:center; gap:12px; padding:0 20px;
  transition:background var(--trans);
}
.logo { display:flex; align-items:center; gap:10px; flex-shrink:0; }
.logo-icon {
  width:34px; height:34px; border-radius:8px;
  background:linear-gradient(135deg,color-mix(in srgb,var(--accent) 15%,transparent),
                                     color-mix(in srgb,var(--accent) 30%,transparent));
  border:1px solid color-mix(in srgb,var(--accent) 40%,transparent);
  display:flex; align-items:center; justify-content:center; font-size:17px;
  box-shadow:0 0 14px color-mix(in srgb,var(--accent) 15%,transparent);
}
.logo-text { font-size:14px; font-weight:700; letter-spacing:.06em; white-space:nowrap; }
.logo-text span { color:var(--accent); }
.sep { width:1px; height:28px; background:var(--border); flex-shrink:0; }

/* Search */
.search-wrap { position:relative; flex:1; max-width:320px; }
.search-wrap svg { position:absolute; left:13px; top:50%; transform:translateY(-50%);
                   color:var(--muted); pointer-events:none; }
#searchInput {
  width:100%; height:36px; background:var(--surface); color:var(--text);
  border:1px solid var(--border); border-radius:50px;
  font-family:var(--mono); font-size:12px; padding:0 14px 0 36px; outline:none;
  transition:border-color var(--trans),box-shadow var(--trans),background var(--trans);
}
#searchInput::placeholder { color:var(--muted); }
#searchInput:focus {
  border-color:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 14%,transparent);
}

/* Buttons */
.btn {
  height:36px; padding:0 16px; border:none; border-radius:50px; cursor:pointer;
  font-family:var(--head); font-size:11px; font-weight:700; letter-spacing:.06em;
  display:flex; align-items:center; gap:6px; white-space:nowrap; transition:all var(--trans);
}
.btn-ghost {
  background:var(--surface); color:var(--text);
  border:1px solid var(--border);
}
.btn-ghost:hover {
  background:var(--hover); border-color:var(--accent); color:var(--accent);
  box-shadow:0 0 10px color-mix(in srgb,var(--accent) 15%,transparent);
}
.btn-accent {
  background:linear-gradient(135deg,#00b4d8,#0077b6); color:#fff;
  box-shadow:0 3px 12px rgba(0,180,216,.3);
}
.btn-accent:hover { filter:brightness(1.15); transform:translateY(-1px); }
.btn-green  { background:linear-gradient(135deg,#059669,#10b981); color:#fff; box-shadow:0 3px 12px rgba(16,185,129,.3); }
.btn-green:hover  { filter:brightness(1.1); transform:translateY(-1px); }
.btn-danger { background:linear-gradient(135deg,#dc2626,#ef4444); color:#fff; }
.btn-danger:hover { filter:brightness(1.1); transform:translateY(-1px); }

/* Theme switch */
.theme-switch {
  width:50px; height:26px; background:var(--hover); border:1px solid var(--border);
  border-radius:50px; cursor:pointer; position:relative;
  transition:background var(--trans); flex-shrink:0;
}
.theme-switch-knob {
  width:20px; height:20px; border-radius:50%; background:var(--accent);
  position:absolute; top:2px; left:2px;
  transition:transform var(--trans), background var(--trans);
  display:flex; align-items:center; justify-content:center; font-size:10px;
}
.light-mode .theme-switch-knob { transform:translateX(24px); background:#f59e0b; }

/* Profile select */
#profileSelect {
  height:36px; padding:0 12px; background:var(--surface); color:var(--text);
  border:1px solid var(--border); border-radius:50px;
  font-family:var(--head); font-size:11px; outline:none; cursor:pointer;
  transition:border-color var(--trans);
}
#profileSelect:focus { border-color:var(--accent); }
#profileSelect option { background:var(--surface); }

.nav-right { margin-left:auto; display:flex; gap:8px; align-items:center; }

/* ── STATS BAR ── */
.stats-bar {
  position:fixed; top:62px; left:0; right:0; z-index:99;
  height:42px;
  background:color-mix(in srgb,var(--bg) 90%,transparent);
  border-bottom:1px solid var(--border); backdrop-filter:blur(10px);
  display:flex; align-items:center; gap:20px; padding:0 20px;
}
.stat { display:flex; align-items:center; gap:7px; font-size:11px; }
.stat-label { color:var(--muted); letter-spacing:.1em; text-transform:uppercase; }
.stat-val { font-family:var(--mono); font-weight:600; font-size:13px; }
.c-green  { color:var(--green); }
.c-red    { color:var(--red); }
.c-blue   { color:var(--accent); }
.c-yellow { color:var(--yellow); }

/* ── MAIN ── */
main { position:fixed; top:104px; bottom:0; left:0; right:0;
       overflow-y:auto; overflow-x:hidden; padding:18px 20px 80px; z-index:1; }

/* Table header */
.tbl-head {
  display:grid;
  grid-template-columns:30px 160px 1fr 130px 90px 80px 130px 48px;
  padding:0 14px; margin-bottom:8px;
  font-size:9px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); font-weight:700;
}

/* ── DEVICE CARD ── */
.device-card {
  display:grid;
  grid-template-columns:30px 160px 1fr 130px 90px 80px 130px 48px;
  align-items:center; gap:0;
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:0 14px; height:56px;
  margin-bottom:5px; cursor:default;
  transition:background var(--trans),border-color var(--trans),transform .1s;
  position:relative;
}
.device-card:hover { background:var(--hover); border-color:color-mix(in srgb,var(--accent) 35%,var(--border)); transform:translateX(2px); }
.device-card.offline { border-color:color-mix(in srgb,var(--red) 30%,var(--border)); background:color-mix(in srgb,var(--red) 4%,var(--surface)); }
.device-card.offline:hover { background:color-mix(in srgb,var(--red) 8%,var(--surface)); }
.device-card.new-card { animation:slideIn .35s ease; }
@keyframes slideIn { from{opacity:0;transform:translateX(-10px)} to{opacity:1;transform:none} }

/* LED */
.led { width:11px; height:11px; border-radius:50%; flex-shrink:0; transition:all .4s; }
.led.on  { background:var(--green); box-shadow:0 0 5px var(--green),0 0 12px color-mix(in srgb,var(--green) 50%,transparent); animation:ledPulse 2.5s ease-in-out infinite; }
.led.off { background:var(--red);   box-shadow:0 0 5px var(--red),0 0 12px color-mix(in srgb,var(--red) 50%,transparent);   animation:ledBlink 1.1s ease-in-out infinite; }
.led.unk { background:var(--border); }
@keyframes ledPulse { 0%,100%{box-shadow:0 0 4px var(--green),0 0 8px color-mix(in srgb,var(--green) 40%,transparent)} 50%{box-shadow:0 0 8px var(--green),0 0 20px color-mix(in srgb,var(--green) 65%,transparent)} }
@keyframes ledBlink { 0%,100%{opacity:1} 50%{opacity:.3} }

/* Cells */
.cell { padding:0 6px; overflow:hidden; }
.c-ip   { font-family:var(--mono); font-size:13px; color:var(--accent); letter-spacing:.04em; white-space:nowrap; }
.c-lbl  { display:flex; flex-direction:column; gap:1px; overflow:hidden; }
.lbl-main { font-size:12px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.lbl-hn   { font-family:var(--mono); font-size:10px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.c-mac  { font-family:var(--mono); font-size:10px; color:var(--muted); white-space:nowrap; }
.c-vendor { font-size:11px; font-weight:600; color:#94a3b8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.c-lat  { font-family:var(--mono); font-size:12px; font-weight:600; text-align:right; }
.lat-fast{color:var(--green)} .lat-med{color:var(--yellow)} .lat-slow{color:var(--red)} .lat-na{color:var(--muted)}
.c-timer { font-family:var(--mono); font-size:11px; color:var(--red); letter-spacing:.04em; white-space:nowrap; }

/* Gear button */
.gear-btn { background:none; border:none; cursor:pointer; color:var(--muted);
            padding:5px 8px; border-radius:6px; font-size:15px; transition:all .15s; }
.gear-btn:hover { background:var(--hover); color:var(--accent); }

/* Empty row */
.device-card.empty { border:1px dashed var(--border); background:color-mix(in srgb,var(--surface) 60%,transparent); }
.device-card.empty:hover { background:var(--surface); border-color:var(--border); transform:none; }
.inline-ip  { background:none; border:none; outline:none; font-family:var(--mono); font-size:13px; color:var(--accent); width:100%; }
.inline-lbl { background:none; border:none; outline:none; font-family:var(--head); font-size:12px; color:var(--text); width:100%; }
.inline-ip::placeholder,.inline-lbl::placeholder { color:var(--border); }

/* ── CONTEXT MENU ── */
.ctx-menu {
  position:fixed; z-index:9999;
  background:color-mix(in srgb,var(--surface) 97%,#000);
  border:1px solid var(--border); border-radius:12px; padding:6px 0;
  min-width:210px;
  box-shadow:0 10px 40px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.03);
  animation:ctxIn .12s ease; backdrop-filter:blur(10px);
}
@keyframes ctxIn { from{opacity:0;transform:scale(.95) translateY(-4px)} to{opacity:1;transform:none} }
.ctx-item {
  display:flex; align-items:center; gap:10px;
  padding:8px 16px; font-size:12px; font-weight:500; color:var(--text);
  cursor:pointer; transition:background .12s; letter-spacing:.02em;
}
.ctx-item:hover { background:var(--hover); color:var(--accent); }
.ctx-item.danger:hover { color:var(--red); }
.ctx-sep { height:1px; background:var(--border); margin:4px 12px; }
.ctx-section { padding:4px 14px 2px; font-size:9px; letter-spacing:.12em; color:var(--muted); text-transform:uppercase; }

/* ── MODALS ── */
.overlay {
  display:none; position:fixed; inset:0; z-index:500;
  background:rgba(10,11,16,.78); backdrop-filter:blur(5px);
  align-items:center; justify-content:center;
}
.overlay.open { display:flex; }
.modal {
  background:color-mix(in srgb,var(--surface) 97%,#000);
  border:1px solid var(--border); border-radius:16px; padding:26px;
  min-width:440px; max-width:580px; width:90%;
  box-shadow:0 20px 60px rgba(0,0,0,.55);
  animation:modalIn .2s ease; max-height:85vh; overflow-y:auto;
}
@keyframes modalIn { from{opacity:0;transform:translateY(14px) scale(.97)} to{opacity:1;transform:none} }
.modal-title { font-size:15px; font-weight:700; margin-bottom:4px; color:var(--text); }
.modal-sub { font-size:11px; color:var(--muted); margin-bottom:18px; }
.field { margin-bottom:13px; }
.field label { display:block; font-size:9px; font-weight:700; letter-spacing:.12em;
               text-transform:uppercase; color:var(--muted); margin-bottom:5px; }
.finput {
  width:100%; height:38px; background:var(--surface); color:var(--text);
  border:1px solid var(--border); border-radius:8px;
  font-family:var(--mono); font-size:12px; padding:0 12px; outline:none;
  transition:border-color var(--trans),box-shadow var(--trans);
}
.finput:focus { border-color:var(--accent); box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 12%,transparent); }
.ftextarea {
  width:100%; height:150px; background:var(--surface); color:var(--text);
  border:1px solid var(--border); border-radius:8px;
  font-family:var(--mono); font-size:12px; padding:10px 12px; outline:none; resize:vertical; line-height:1.6;
  transition:border-color var(--trans);
}
.ftextarea:focus { border-color:var(--accent); }
.mrow { display:flex; gap:12px; }
.mrow .field { flex:1; }
.mactions { display:flex; gap:8px; margin-top:18px; justify-content:flex-end; }

/* Progress */
.prog-wrap { background:var(--surface); border-radius:99px; height:5px; overflow:hidden; margin-top:10px; }
.prog-bar  { height:100%; background:linear-gradient(90deg,#00b4d8,#10b981); width:0%;
             border-radius:99px; transition:width .25s; box-shadow:0 0 6px rgba(0,180,216,.5); }
.prog-lbl  { font-family:var(--mono); font-size:10px; color:var(--muted); margin-top:4px; }

/* Port scan results */
.port-table { width:100%; border-collapse:collapse; margin-top:12px; }
.port-table th { font-size:9px; letter-spacing:.12em; text-transform:uppercase;
                 color:var(--muted); text-align:left; padding:4px 10px; border-bottom:1px solid var(--border); }
.port-table td { font-family:var(--mono); font-size:11px; padding:7px 10px; border-bottom:1px solid color-mix(in srgb,var(--border) 40%,transparent); }
.port-open  { color:var(--green); font-weight:700; }
.port-closed { color:var(--muted); }

/* Traceroute terminal */
.term-box {
  background:#0d0f14; border:1px solid var(--border); border-radius:8px;
  padding:12px; margin-top:12px; max-height:260px; overflow-y:auto;
  font-family:var(--mono); font-size:11px; line-height:1.7; color:#a8d8a8;
}
.term-box .t-hop  { color:#00d4ff; }
.term-box .t-ip   { color:#e2e8f0; }
.term-box .t-meta { color:var(--muted); }

/* Log panel */
.log-panel {
  background:var(--surface); border:1px solid var(--border); border-radius:8px;
  padding:10px 12px; max-height:200px; overflow-y:auto; margin-top:12px;
}
.log-entry { font-family:var(--mono); font-size:11px; padding:3px 0;
             border-bottom:1px solid color-mix(in srgb,var(--border) 30%,transparent);
             color:var(--text); line-height:1.5; }
.log-entry:last-child { border-bottom:none; }
.log-empty { color:var(--muted); font-size:11px; }

/* Toast */
#toast {
  position:fixed; bottom:22px; right:22px; z-index:9999;
  background:var(--surface); border:1px solid var(--border); border-radius:10px;
  padding:10px 16px; font-size:12px; color:var(--text);
  box-shadow:0 8px 24px rgba(0,0,0,.4);
  transform:translateY(70px); opacity:0; transition:all .28s ease;
  max-width:300px;
}
#toast.show { transform:translateY(0); opacity:1; }
#toast.ok  { border-color:var(--green); color:var(--green); }
#toast.err { border-color:var(--red);   color:var(--red); }
#toast.inf { border-color:var(--accent); color:var(--accent); }

/* SSH user row */
.ssh-row { display:flex; gap:8px; }
.ssh-row input { flex:1; }
</style>
</head>
<body id="appBody">

<!-- ═══ HEADER ═══════════════════════════════════════════════════════════════ -->
<header>
  <div class="logo">
    <div class="logo-icon">⬡</div>
    <div class="logo-text">Network <span>Monitor Pro</span></div>
  </div>
  <div class="sep"></div>

  <div class="search-wrap">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input type="text" id="searchInput" placeholder="IP, cihaz adı, hostname...">
  </div>

  <button class="btn btn-ghost" onclick="openModal('bulkModal')">
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>Toplu IP
  </button>
  <button class="btn btn-ghost" onclick="openModal('scanModal')">
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>Ağ Keşfi
  </button>

  <div class="nav-right">
    <!-- Theme Switch -->
    <div class="theme-switch" id="themeSwitch" onclick="toggleTheme()" title="Tema Değiştir">
      <div class="theme-switch-knob" id="themeKnob">🌙</div>
    </div>

    <button class="btn btn-danger" onclick="clearAll()" title="Ekranı Temizle">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>Temizle
    </button>

    <div class="sep"></div>
    <select id="profileSelect" onchange="onProfileChange(this.value)">
      <option value="">— Profil —</option>
    </select>
    <button class="btn btn-green" onclick="openModal('saveProfileModal')">
      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>Kaydet
    </button>
  </div>
</header>

<!-- ═══ STATS BAR ════════════════════════════════════════════════════════════ -->
<div class="stats-bar">
  <div class="stat"><span class="stat-label">Toplam</span><span class="stat-val c-blue" id="stTotal">0</span></div>
  <span style="color:var(--border)">|</span>
  <div class="stat"><span class="stat-label">Online</span><span class="stat-val c-green" id="stOnline">0</span></div>
  <span style="color:var(--border)">|</span>
  <div class="stat"><span class="stat-label">Offline</span><span class="stat-val c-red" id="stOffline">0</span></div>
  <span style="color:var(--border)">|</span>
  <div class="stat"><span class="stat-label">Ort. Gecikme</span><span class="stat-val c-blue" id="stAvg">— ms</span></div>
  <span style="color:var(--border)">|</span>
  <div class="stat"><span class="stat-label">Veri Klasörü</span><span class="stat-val" id="stPath" style="font-family:var(--mono);font-size:10px;color:var(--muted)">—</span></div>
</div>

<!-- ═══ MAIN ══════════════════════════════════════════════════════════════════ -->
<main>
  <div class="tbl-head">
    <div></div><div>IP ADRESİ</div><div>CİHAZ / HOSTNAME</div>
    <div>MAC ADRESİ</div><div>MARKA</div>
    <div style="text-align:right">GECİKME</div>
    <div>DURUM / KRONOMETRESİ</div><div></div>
  </div>
  <div id="deviceList"></div>
</main>

<!-- ═══ TOAST ════════════════════════════════════════════════════════════════ -->
<div id="toast"></div>

<!-- ═══ CONTEXT MENU ══════════════════════════════════════════════════════════ -->
<div class="ctx-menu" id="ctxMenu" style="display:none">
  <div class="ctx-section">Cihaz Yönetimi</div>
  <div class="ctx-item" id="ctxLabel">✏️ Etiket Düzenle</div>
  <div class="ctx-item" id="ctxHostname">🔍 Hostname Çöz</div>
  <div class="ctx-item" id="ctxMacVendor">🏷 MAC / Üretici Bul</div>
  <div class="ctx-item" id="ctxLog">📋 Kesinti Geçmişi</div>
  <div class="ctx-sep"></div>
  <div class="ctx-section">Ağ Araçları</div>
  <div class="ctx-item" id="ctxPortScan">🔌 Port Tarama</div>
  <div class="ctx-item" id="ctxTrace">🛤 Trace Route</div>
  <div class="ctx-item" id="ctxCmdPing">💻 CMD Ping (Sürekli)</div>
  <div class="ctx-sep"></div>
  <div class="ctx-section">Bağlantı</div>
  <div class="ctx-item" id="ctxWebHttp">🌐 Web (HTTP)</div>
  <div class="ctx-item" id="ctxWebHttps">🔒 Web (HTTPS)</div>
  <div class="ctx-item" id="ctxSSH">🖥 SSH Bağlantısı</div>
  <div class="ctx-item" id="ctxRDP">🖱 RDP (Uzak Masaüstü)</div>
  <div class="ctx-sep"></div>
  <div class="ctx-item danger" id="ctxDelete">🗑 Cihazı Sil</div>
</div>

<!-- ═══ MODAL: Toplu IP ════════════════════════════════════════════════════════ -->
<div class="overlay" id="bulkModal">
  <div class="modal">
    <div class="modal-title">Toplu IP Ekle</div>
    <div class="modal-sub">Her satıra bir IP. "192.168.1.1 Etiket" formatıyla etiket de ekleyebilirsiniz.</div>
    <div class="field"><label>IP Listesi</label>
      <textarea class="ftextarea" id="bulkIPs" placeholder="192.168.1.1 Core Switch&#10;192.168.1.254 Firewall&#10;10.0.0.1"></textarea>
    </div>
    <div class="mactions">
      <button class="btn btn-ghost" onclick="closeModal('bulkModal')">İptal</button>
      <button class="btn btn-accent" onclick="submitBulk()">Ekle</button>
    </div>
  </div>
</div>

<!-- ═══ MODAL: Ağ Keşfi ═══════════════════════════════════════════════════════ -->
<div class="overlay" id="scanModal">
  <div class="modal">
    <div class="modal-title">Ağ Keşfi</div>
    <div class="modal-sub">Taranacak IP aralığını girin (maks 1024 adres).</div>
    <div class="mrow">
      <div class="field"><label>Başlangıç IP</label><input type="text" class="finput" id="scanStart" placeholder="192.168.1.1"></div>
      <div class="field"><label>Bitiş IP</label><input type="text" class="finput" id="scanEnd" placeholder="192.168.1.254"></div>
    </div>
    <div class="prog-wrap" id="scanProgWrap" style="display:none"><div class="prog-bar" id="scanProgBar"></div></div>
    <div class="prog-lbl" id="scanProgLbl"></div>
    <div class="mactions">
      <button class="btn btn-ghost" onclick="closeModal('scanModal')">Kapat</button>
      <button class="btn btn-accent" id="scanBtn" onclick="startScan()">Taramayı Başlat</button>
    </div>
  </div>
</div>

<!-- ═══ MODAL: Profil Kaydet ══════════════════════════════════════════════════ -->
<div class="overlay" id="saveProfileModal">
  <div class="modal">
    <div class="modal-title">Profili Kaydet</div>
    <div class="modal-sub">Cihaz listesi Windows Roaming AppData klasörüne kaydedilecek.</div>
    <div class="field"><label>Profil Adı</label><input type="text" class="finput" id="profileNameInput" placeholder="Örn: Datacenter-A"></div>
    <div class="mactions">
      <button class="btn btn-ghost" onclick="closeModal('saveProfileModal')">İptal</button>
      <button class="btn btn-green" onclick="saveProfile()">Kaydet</button>
    </div>
  </div>
</div>

<!-- ═══ MODAL: Etiket Düzenle ═════════════════════════════════════════════════ -->
<div class="overlay" id="labelModal">
  <div class="modal">
    <div class="modal-title">Etiket Düzenle</div>
    <div class="modal-sub">Cihaz adını değiştirin. Boş bırakırsanız IP adresi gösterilir.</div>
    <div class="field"><label>Yeni Etiket</label><input type="text" class="finput" id="labelInput" placeholder="Cihaz adı..."></div>
    <div class="mactions">
      <button class="btn btn-ghost" onclick="closeModal('labelModal')">İptal</button>
      <button class="btn btn-accent" onclick="submitLabel()">Kaydet</button>
    </div>
  </div>
</div>

<!-- ═══ MODAL: Port Tarama ════════════════════════════════════════════════════ -->
<div class="overlay" id="portModal">
  <div class="modal" style="min-width:480px">
    <div class="modal-title">Port Tarama Sonuçları</div>
    <div class="modal-sub" id="portModalSub">Taranıyor...</div>
    <div id="portResults"></div>
    <div class="mactions"><button class="btn btn-ghost" onclick="closeModal('portModal')">Kapat</button></div>
  </div>
</div>

<!-- ═══ MODAL: Traceroute ══════════════════════════════════════════════════════ -->
<div class="overlay" id="traceModal">
  <div class="modal" style="min-width:520px">
    <div class="modal-title">Trace Route</div>
    <div class="modal-sub" id="traceModalSub">Çalıştırılıyor...</div>
    <div class="term-box" id="traceOutput">Lütfen bekleyin...</div>
    <div class="mactions"><button class="btn btn-ghost" onclick="closeModal('traceModal')">Kapat</button></div>
  </div>
</div>

<!-- ═══ MODAL: SSH ════════════════════════════════════════════════════════════ -->
<div class="overlay" id="sshModal">
  <div class="modal">
    <div class="modal-title">SSH Bağlantısı</div>
    <div class="modal-sub" id="sshModalSub">SSH bağlantısı için kullanıcı adını girin.</div>
    <div class="field"><label>Kullanıcı Adı</label>
      <input type="text" class="finput" id="sshUser" placeholder="admin">
    </div>
    <div class="mactions">
      <button class="btn btn-ghost" onclick="closeModal('sshModal')">İptal</button>
      <button class="btn btn-accent" onclick="submitSSH()">Bağlan</button>
    </div>
  </div>
</div>

<!-- ═══ MODAL: Kesinti Geçmişi ════════════════════════════════════════════════ -->
<div class="overlay" id="logModal">
  <div class="modal">
    <div class="modal-title">Kesinti Geçmişi</div>
    <div class="modal-sub" id="logModalSub">Son 50 olay listelenmektedir.</div>
    <div class="log-panel" id="logContent"></div>
    <div class="mactions"><button class="btn btn-ghost" onclick="closeModal('logModal')">Kapat</button></div>
  </div>
</div>

<script>
// ─────────────────────────────────────────────────────────────────────────────
// STATE
// ─────────────────────────────────────────────────────────────────────────────
const devices = {};    // ip -> device obj
const timers  = {};    // ip -> { start, interval }
let   ctxIp   = null;
let   theme   = 'dark';

// ─── UTILS ───────────────────────────────────────────────────────────────────
function esc(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function toast(msg, type=''){
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'show ' + type;
  clearTimeout(t._t);
  t._t = setTimeout(()=>{ t.className=''; }, 3300);
}

// ─── THEME ───────────────────────────────────────────────────────────────────
function applyTheme(t){
  theme = t;
  const body  = document.getElementById('appBody');
  const knob  = document.getElementById('themeKnob');
  if(t === 'light'){ body.classList.add('light-mode'); knob.textContent='☀️'; }
  else             { body.classList.remove('light-mode'); knob.textContent='🌙'; }
}
async function toggleTheme(){
  const next = theme === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  await window.pywebview.api.set_theme(next);
}

// ─── MODAL ───────────────────────────────────────────────────────────────────
function openModal(id){ document.getElementById(id).classList.add('open'); }
function closeModal(id){ document.getElementById(id).classList.remove('open'); }
document.querySelectorAll('.overlay').forEach(ov=>{
  ov.addEventListener('click', e=>{ if(e.target===ov) ov.classList.remove('open'); });
});

// ─── STATS ───────────────────────────────────────────────────────────────────
function updateStats(){
  const all = Object.values(devices);
  const on  = all.filter(d=>d.alive===true).length;
  const off = all.filter(d=>d.alive===false).length;
  const lats = all.filter(d=>d.latency!=null).map(d=>d.latency);
  const avg  = lats.length ? (lats.reduce((a,b)=>a+b,0)/lats.length).toFixed(1)+' ms' : '— ms';
  document.getElementById('stTotal').textContent  = all.length;
  document.getElementById('stOnline').textContent = on;
  document.getElementById('stOffline').textContent= off;
  document.getElementById('stAvg').textContent    = avg;
}

// ─── LATENCY HELPERS ─────────────────────────────────────────────────────────
function latClass(ms){ if(ms==null)return'lat-na'; if(ms<10)return'lat-fast'; if(ms<60)return'lat-med'; return'lat-slow'; }
function latText(ms) { return ms==null ? '—' : ms.toFixed(1)+' ms'; }
function ledCls(a)   { return a===true?'on':a===false?'off':'unk'; }

// ─── CARD BUILD ──────────────────────────────────────────────────────────────
function cardId(ip){ return 'card-'+ip.replace(/\./g,'-'); }
function ledId(ip) { return 'led-'+ip.replace(/\./g,'-'); }
function latId(ip) { return 'lat-'+ip.replace(/\./g,'-'); }
function hnId(ip)  { return 'hn-'+ip.replace(/\./g,'-'); }
function stId(ip)  { return 'st-'+ip.replace(/\./g,'-'); }
function timId(ip) { return 'tim-'+ip.replace(/\./g,'-'); }

function buildStatus(dev){
  if(dev.alive===false){
    return `<span class="c-timer" id="${timId(dev.ip)}">⏱ 00:00:00</span>`;
  }
  if(dev.alive===true) return `<span class="c-green" style="font-size:11px">● Online</span>`;
  return `<span style="color:var(--muted);font-size:11px">⋯ Bekleniyor</span>`;
}

function buildCardHTML(dev){
  return `
    <div style="display:flex;align-items:center;justify-content:center">
      <div class="led ${ledCls(dev.alive)}" id="${ledId(dev.ip)}"></div>
    </div>
    <div class="cell c-ip">${esc(dev.ip)}</div>
    <div class="cell c-lbl">
      <span class="lbl-main">${esc(dev.label||dev.ip)}</span>
      <span class="lbl-hn" id="${hnId(dev.ip)}">${esc(dev.hostname||'')}</span>
    </div>
    <div class="cell c-mac">${esc(dev.mac||'N/A')}</div>
    <div class="cell c-vendor">${esc(dev.vendor||'Unknown')}</div>
    <div class="cell c-lat ${latClass(dev.latency)}" id="${latId(dev.ip)}">${latText(dev.latency)}</div>
    <div class="cell" id="${stId(dev.ip)}">${buildStatus(dev)}</div>
    <div class="cell" style="text-align:right">
      <button class="gear-btn" onclick="showCtx(event,'${dev.ip}')">⚙</button>
    </div>`;
}

function addDeviceToUI(dev, animate=false){
  devices[dev.ip] = dev;
  const list = document.getElementById('deviceList');
  let card = document.getElementById(cardId(dev.ip));
  if(card){ updateCardDOM(dev); return; }
  card = document.createElement('div');
  card.className = 'device-card'+(dev.alive===false?' offline':'')+(animate?' new-card':'');
  card.id = cardId(dev.ip); card.dataset.ip = dev.ip;
  card.innerHTML = buildCardHTML(dev);
  card.addEventListener('contextmenu', e=>{ e.preventDefault(); showCtx(e,dev.ip); });
  const emptyCard = list.querySelector('.device-card.empty');
  if(emptyCard) list.insertBefore(card, emptyCard); else list.appendChild(card);
  if(dev.alive===false) startTimer(dev.ip);
  updateStats(); ensureEmpty();
}

function updateCardDOM(dev){
  devices[dev.ip] = {...(devices[dev.ip]||{}), ...dev};
  const card = document.getElementById(cardId(dev.ip));
  if(!card) return;
  const led  = document.getElementById(ledId(dev.ip));
  const latEl= document.getElementById(latId(dev.ip));
  const stEl = document.getElementById(stId(dev.ip));
  if(led)  led.className = 'led '+ledCls(dev.alive);
  if(latEl){ latEl.className='cell c-lat '+latClass(dev.latency); latEl.textContent=latText(dev.latency); }
  if(dev.alive===false){ card.classList.add('offline'); if(!timers[dev.ip]){ if(stEl) stEl.innerHTML=`<span class="c-timer" id="${timId(dev.ip)}">⏱ 00:00:00</span>`; startTimer(dev.ip); } }
  else { card.classList.remove('offline'); stopTimer(dev.ip); if(stEl) stEl.innerHTML=buildStatus(dev); }
  updateStats();
}

// ─── TIMER ───────────────────────────────────────────────────────────────────
function startTimer(ip){
  if(timers[ip]) return;
  const start = Date.now();
  const k = ip.replace(/\./g,'-');
  const iv = setInterval(()=>{
    const el = document.getElementById('tim-'+k);
    if(!el){ clearInterval(iv); delete timers[ip]; return; }
    const s=Math.floor((Date.now()-start)/1000);
    const h=String(Math.floor(s/3600)).padStart(2,'0');
    const m=String(Math.floor((s%3600)/60)).padStart(2,'0');
    const sc=String(s%60).padStart(2,'0');
    el.textContent=`⏱ ${h}:${m}:${sc}`;
  },1000);
  timers[ip]={start,iv};
}
function stopTimer(ip){ if(!timers[ip]) return; clearInterval(timers[ip].iv); delete timers[ip]; }

// ─── EMPTY ROW ───────────────────────────────────────────────────────────────
function ensureEmpty(){
  const list = document.getElementById('deviceList');
  if(list.querySelector('.device-card.empty')) return;
  const card = document.createElement('div');
  card.className = 'device-card empty';
  card.innerHTML=`
    <div></div>
    <div class="cell"><input type="text" class="inline-ip" id="emptyIp" placeholder="x.x.x.x"></div>
    <div class="cell"><input type="text" class="inline-lbl" placeholder="Cihaz adı (isteğe bağlı)"></div>
    <div class="cell c-mac" style="color:var(--border)">—</div>
    <div class="cell c-vendor" style="color:var(--border)">—</div>
    <div class="cell c-lat lat-na">—</div>
    <div class="cell"></div><div class="cell"></div>`;
  list.appendChild(card);
  const ipIn  = card.querySelector('.inline-ip');
  const lblIn = card.querySelector('.inline-lbl');
  const submit = ()=>{ const ip=ipIn.value.trim(), lbl=lblIn.value.trim(); if(ip) doAddDevice(ip,lbl); };
  ipIn.addEventListener('keydown', e=>{ if(e.key==='Enter'||e.key==='Tab') submit(); });
  lblIn.addEventListener('keydown',e=>{ if(e.key==='Enter') submit(); });
}

async function doAddDevice(ip, label=''){
  const r = await window.pywebview.api.add_device(ip, label);
  if(r.ok) toast('✔ '+ip+' eklendi','ok');
  else     toast('✘ '+r.error,'err');
}

// ─── CLEAR ALL ────────────────────────────────────────────────────────────────
async function clearAll(){
  if(!confirm('Tüm cihazlar listeden kaldırılsın mı?')) return;
  await window.pywebview.api.clear_all_devices();
  Object.keys(devices).forEach(ip=>{ stopTimer(ip); delete devices[ip]; });
  document.getElementById('deviceList').innerHTML='';
  ensureEmpty(); updateStats();
  toast('Ekran temizlendi','inf');
}

// ─── BULK ADD ─────────────────────────────────────────────────────────────────
async function submitBulk(){
  const text = document.getElementById('bulkIPs').value;
  if(!text.trim()) return;
  const r = await window.pywebview.api.add_devices_bulk(text);
  closeModal('bulkModal');
  if(r.added.length)  toast('✔ '+r.added.length+' IP eklendi','ok');
  if(r.errors.length) toast('⚠ '+r.errors.length+' hata','err');
}

// ─── SCAN ─────────────────────────────────────────────────────────────────────
async function startScan(){
  const s=document.getElementById('scanStart').value.trim();
  const e=document.getElementById('scanEnd').value.trim();
  if(!s||!e){toast('IP aralığı girin','err');return;}
  document.getElementById('scanProgWrap').style.display='block';
  document.getElementById('scanProgBar').style.width='0%';
  document.getElementById('scanProgLbl').textContent='Taranıyor...';
  document.getElementById('scanBtn').disabled=true;
  const r = await window.pywebview.api.scan_network(s,e);
  if(!r.ok){ toast('✘ '+r.error,'err'); document.getElementById('scanBtn').disabled=false; }
}
window._onScanProgress=pct=>{
  document.getElementById('scanProgBar').style.width=pct+'%';
  document.getElementById('scanProgLbl').textContent=`Taranıyor... %${pct}`;
};
window._onScanComplete=json=>{
  const found=JSON.parse(json);
  document.getElementById('scanProgLbl').textContent=`Tamamlandı — ${found.length} cihaz`;
  document.getElementById('scanBtn').disabled=false;
  found.forEach(d=>addDeviceToUI({ip:d.ip,label:d.vendor||d.ip,mac:d.mac,vendor:d.vendor,alive:true,latency:d.latency,hostname:'',log:[]},true));
  toast('✔ '+found.length+' cihaz bulundu','ok');
  setTimeout(()=>closeModal('scanModal'),1200);
};

// ─── PING UPDATES ─────────────────────────────────────────────────────────────
window._onPingUpdate=json=>{
  const d=JSON.parse(json);
  if(!devices[d.ip]) return;
  updateCardDOM({ip:d.ip,alive:d.alive,latency:d.latency});
};

// ─── CONTEXT MENU ─────────────────────────────────────────────────────────────
function showCtx(e, ip){
  ctxIp=ip;
  const m=document.getElementById('ctxMenu');
  m.style.display='block';
  const vw=window.innerWidth,vh=window.innerHeight;
  let x=e.clientX,y=e.clientY;
  m.style.left=(x+m.offsetWidth>vw?x-m.offsetWidth:x)+'px';
  m.style.top =(y+m.offsetHeight>vh?y-m.offsetHeight:y)+'px';
  e.stopPropagation();
}
document.addEventListener('click',()=>{ document.getElementById('ctxMenu').style.display='none'; });

// ctx: label
document.getElementById('ctxLabel').addEventListener('click',()=>{
  if(!ctxIp) return;
  document.getElementById('labelInput').value = devices[ctxIp]?.label||'';
  openModal('labelModal');
});
async function submitLabel(){
  const lbl=document.getElementById('labelInput').value.trim();
  const ip=ctxIp;
  const r=await window.pywebview.api.set_label(ip, lbl||ip);
  closeModal('labelModal');
  if(r.ok){
    if(devices[ip]) devices[ip].label=lbl||ip;
    const mainEl=document.querySelector(`#${cardId(ip)} .lbl-main`);
    if(mainEl) mainEl.textContent=lbl||ip;
    toast('✔ Etiket güncellendi','ok');
  }
}

// ctx: hostname
document.getElementById('ctxHostname').addEventListener('click',async()=>{
  if(!ctxIp) return;
  toast('Hostname çözümleniyor...','inf');
  const r=await window.pywebview.api.resolve_hostname(ctxIp);
  const el=document.getElementById(hnId(ctxIp));
  if(el) el.textContent=r.hostname;
  toast('✔ '+r.hostname,'ok');
});

// ctx: mac/vendor
document.getElementById('ctxMacVendor').addEventListener('click',async()=>{
  if(!ctxIp) return;
  toast('MAC adresi sorgulanıyor...','inf');
  const r=await window.pywebview.api.fetch_mac_vendor(ctxIp);
  if(devices[ctxIp]){ devices[ctxIp].mac=r.mac; devices[ctxIp].vendor=r.vendor; }
  const macEl=document.querySelector(`#${cardId(ctxIp)} .c-mac`);
  const vndEl=document.querySelector(`#${cardId(ctxIp)} .c-vendor`);
  if(macEl) macEl.textContent=r.mac;
  if(vndEl) vndEl.textContent=r.vendor;
  toast('✔ '+r.vendor+' ('+r.mac+')','ok');
});

// ctx: log
document.getElementById('ctxLog').addEventListener('click',async()=>{
  if(!ctxIp) return;
  document.getElementById('logModalSub').textContent='IP: '+ctxIp;
  const log=await window.pywebview.api.get_log(ctxIp);
  const el=document.getElementById('logContent');
  if(!log||!log.length){ el.innerHTML='<div class="log-empty">Henüz kesinti kaydı yok.</div>'; }
  else { el.innerHTML=log.map(l=>`<div class="log-entry">${esc(l)}</div>`).join(''); }
  openModal('logModal');
});

// ctx: port scan
document.getElementById('ctxPortScan').addEventListener('click',async()=>{
  if(!ctxIp) return;
  document.getElementById('portModalSub').textContent='Taranıyor: '+ctxIp+'  ...';
  document.getElementById('portResults').innerHTML='';
  openModal('portModal');
  const r=await window.pywebview.api.port_scan(ctxIp);
  document.getElementById('portModalSub').textContent='Sonuçlar: '+r.ip;
  const open=r.results.filter(x=>x.open);
  let html=`<table class="port-table"><thead><tr><th>Port</th><th>Servis</th><th>Durum</th></tr></thead><tbody>`;
  r.results.forEach(p=>{
    html+=`<tr>
      <td>${p.port}</td>
      <td>${esc(p.service)}</td>
      <td class="${p.open?'port-open':'port-closed'}">${p.open?'● AÇIK':'○ Kapalı'}</td>
    </tr>`;
  });
  html+=`</tbody></table>`;
  html+=`<div style="margin-top:10px;font-size:11px;color:var(--muted)">${open.length} açık port bulundu.</div>`;
  document.getElementById('portResults').innerHTML=html;
});

// ctx: traceroute
document.getElementById('ctxTrace').addEventListener('click',async()=>{
  if(!ctxIp) return;
  document.getElementById('traceModalSub').textContent='Hedef: '+ctxIp;
  document.getElementById('traceOutput').textContent='Çalıştırılıyor, lütfen bekleyin...';
  openModal('traceModal');
  const r=await window.pywebview.api.traceroute(ctxIp);
  const box=document.getElementById('traceOutput');
  if(!r.ok){ box.textContent=r.lines.join('\n'); return; }
  box.innerHTML=r.lines.map(l=>{
    l=esc(l);
    l=l.replace(/(\d+\s+ms)/g,'<span class="t-ip">$1</span>');
    l=l.replace(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/g,'<span class="t-hop">$1</span>');
    return '<div>'+l+'</div>';
  }).join('');
});

// ctx: cmd ping
document.getElementById('ctxCmdPing').addEventListener('click',async()=>{
  if(!ctxIp) return;
  await window.pywebview.api.open_cmd_ping(ctxIp);
});

// ctx: web http/https
document.getElementById('ctxWebHttp').addEventListener('click',async()=>{
  if(!ctxIp) return;
  await window.pywebview.api.open_web(ctxIp,false);
});
document.getElementById('ctxWebHttps').addEventListener('click',async()=>{
  if(!ctxIp) return;
  await window.pywebview.api.open_web(ctxIp,true);
});

// ctx: ssh
document.getElementById('ctxSSH').addEventListener('click',()=>{
  if(!ctxIp) return;
  document.getElementById('sshModalSub').textContent='Hedef: '+ctxIp;
  document.getElementById('sshUser').value='';
  openModal('sshModal');
});
async function submitSSH(){
  const u=document.getElementById('sshUser').value.trim()||'admin';
  closeModal('sshModal');
  const r=await window.pywebview.api.open_ssh(ctxIp,u);
  if(r.ok) toast('✔ SSH terminali açıldı','ok');
  else     toast('✘ '+r.error,'err');
}

// ctx: rdp
document.getElementById('ctxRDP').addEventListener('click',async()=>{
  if(!ctxIp) return;
  const r=await window.pywebview.api.open_rdp(ctxIp);
  if(r.ok) toast('✔ RDP bağlantısı açıldı','ok');
  else     toast('✘ '+(r.error||'Hata'),'err');
});

// ctx: delete
document.getElementById('ctxDelete').addEventListener('click',async()=>{
  if(!ctxIp) return;
  await window.pywebview.api.remove_device(ctxIp);
  const card=document.getElementById(cardId(ctxIp));
  if(card){ card.style.transition='opacity .2s'; card.style.opacity='0'; setTimeout(()=>card.remove(),200); }
  delete devices[ctxIp]; stopTimer(ctxIp); updateStats();
  toast('Cihaz silindi','');
  ctxIp=null;
});

// ─── SEARCH FILTER ────────────────────────────────────────────────────────────
document.getElementById('searchInput').addEventListener('input',function(){
  const q=this.value.toLowerCase();
  document.querySelectorAll('#deviceList .device-card:not(.empty)').forEach(c=>{
    c.style.display=c.textContent.toLowerCase().includes(q)?'':'none';
  });
});

// ─── PROFILE ─────────────────────────────────────────────────────────────────
async function refreshProfiles(){
  const names=await window.pywebview.api.list_profiles();
  const sel=document.getElementById('profileSelect');
  sel.innerHTML='<option value="">— Profil —</option>';
  names.forEach(n=>{
    const o=document.createElement('option'); o.value=o.textContent=n; sel.appendChild(o);
  });
}
async function onProfileChange(name){
  if(!name) return;
  const r=await window.pywebview.api.load_profile(name);
  if(!r.ok){toast('✘ '+r.error,'err');return;}
  Object.keys(devices).forEach(ip=>{stopTimer(ip);delete devices[ip];});
  document.getElementById('deviceList').innerHTML='';
  ensureEmpty();
  r.devices.forEach(d=>addDeviceToUI(d));
  toast('✔ Profil yüklendi: '+name,'ok');
}
async function saveProfile(){
  const name=document.getElementById('profileNameInput').value.trim();
  if(!name){toast('Profil adı girin','err');return;}
  const r=await window.pywebview.api.save_profile(name);
  closeModal('saveProfileModal');
  if(r.ok){toast('✔ Kaydedildi: '+r.name,'ok');refreshProfiles();}
  else    {toast('✘ '+r.error,'err');}
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
window.addEventListener('pywebviewready', async ()=>{
  // Apply stored theme
  const cfg=await window.pywebview.api.get_settings();
  applyTheme(cfg.theme||'dark');

  // Show AppData path in stats bar
  try{
    // We'll derive it from a quick call
    document.getElementById('stPath').textContent='AppData\\Roaming\\NetworkMonitorPro';
  }catch(e){}

  ensureEmpty();
  await refreshProfiles();

  const devs=await window.pywebview.api.get_devices();
  devs.forEach(d=>addDeviceToUI(d));
});
</script>
</body>
</html>"""


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    api = Api()
    window = webview.create_window(
        'Network Monitor Pro',
        html=HTML,
        js_api=api,
        width=1340,
        height=840,
        min_size=(960, 620),
        background_color='#1a1c23',
    )
    webview.start(debug=False)
    api.shutdown()
