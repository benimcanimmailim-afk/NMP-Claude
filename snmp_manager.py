import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pysnmp.hlapi import *

# OIDs
OID_SYS_DESCR = '1.3.6.1.2.1.1.1.0'
OID_SYS_NAME = '1.3.6.1.2.1.1.5.0'
OID_SYS_OBJECT_ID = '1.3.6.1.2.1.1.2.0'

def _get_auth_data(version, community):
    if version == 'v3':
        # Defaulting to noAuthNoPriv for simplicity as UI only collects one string
        return UsmUserData(community or 'admin')
    return CommunityData(community or 'public')

def snmp_test(ip, version='v2c', community='public', timeout=1.5, port=161):
    """
    Tests SNMP connectivity for a single IP.
    """
    try:
        auth_data = _get_auth_data(version, community)
        transport = UdpTransportTarget((ip, port), timeout=timeout, retries=0)

        errorIndication, errorStatus, errorIndex, varBinds = next(
            getCmd(SnmpEngine(),
                   auth_data,
                   transport,
                   ContextData(),
                   ObjectType(ObjectIdentity(OID_SYS_DESCR)),
                   ObjectType(ObjectIdentity(OID_SYS_NAME)),
                   ObjectType(ObjectIdentity(OID_SYS_OBJECT_ID)))
        )

        if errorIndication:
            return {"ok": False, "error": str(errorIndication)}
        elif errorStatus:
            return {"ok": False, "error": f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"}
        else:
            res = {"ok": True}
            for varBind in varBinds:
                oid = str(varBind[0])
                val = str(varBind[1])
                if OID_SYS_DESCR in oid: res["sysDescr"] = val
                elif OID_SYS_NAME in oid: res["sysName"] = val
                elif OID_SYS_OBJECT_ID in oid: res["sysObjectID"] = val
            return res
    except Exception as e:
        return {"ok": False, "error": str(e)}

def detect_template(sys_descr):
    if not sys_descr:
        return "unknown"
    sd = sys_descr.lower()
    if "ios" in sd or "cisco" in sd: return "cisco_ios"
    if "fortigate" in sd or "fortinet" in sd: return "fortigate"
    if "routeros" in sd or "mikrotik" in sd: return "mikrotik"
    if "windows" in sd: return "windows"
    if "linux" in sd: return "linux"
    return "unknown"

def get_live_snmp_data(ip, template, settings):
    version = settings.get('version', 'v2c')
    community = settings.get('community', 'public')
    timeout = float(settings.get('timeout', 1500)) / 1000.0
    port = int(settings.get('port', 161))

    OID_UPTIME = '1.3.6.1.2.1.1.3.0'
    oids = [OID_UPTIME]

    if template == "cisco_ios":
        oids.extend(['1.3.6.1.4.1.9.9.109.1.1.1.1.7.1', '1.3.6.1.4.1.9.9.48.1.1.1.5.1', '1.3.6.1.4.1.9.9.48.1.1.1.6.1'])
    elif template == "fortigate":
        oids.extend(['1.3.6.1.4.1.12356.101.4.1.3.0', '1.3.6.1.4.1.12356.101.4.1.4.0', '1.3.6.1.4.1.12356.101.4.1.8.0'])
    elif template == "windows":
        oids.extend(['1.3.6.1.2.1.25.3.3.1.2.1', '1.3.6.1.2.1.25.2.3.1.6.1', '1.3.6.1.2.1.25.2.3.1.5.1'])
    elif template == "linux":
        oids.extend(['1.3.6.1.4.1.2021.11.11.0', '1.3.6.1.4.1.2021.4.5.0', '1.3.6.1.4.1.2021.4.6.0'])

    try:
        auth_data = _get_auth_data(version, community)
        transport = UdpTransportTarget((ip, port), timeout=timeout, retries=0)
        var_binds = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        errorIndication, errorStatus, errorIndex, resVarBinds = next(
            getCmd(SnmpEngine(), auth_data, transport, ContextData(), *var_binds)
        )

        if errorIndication or errorStatus:
            return {"ok": False, "error": str(errorIndication or errorStatus)}

        data = {"ok": True, "raw": {}}
        for vb in resVarBinds:
            data["raw"][str(vb[0])] = str(vb[1])

        data["uptime_ticks"] = data["raw"].get(OID_UPTIME, "0")

        if template == "cisco_ios":
            data["cpu"] = int(data["raw"].get('1.3.6.1.4.1.9.9.109.1.1.1.1.7.1', 0))
            free = int(data["raw"].get('1.3.6.1.4.1.9.9.48.1.1.1.5.1', 1))
            used = int(data["raw"].get('1.3.6.1.4.1.9.9.48.1.1.1.6.1', 0))
            data["ram"] = int((used / (used + free)) * 100) if (used+free) > 0 else 0
        elif template == "fortigate":
            data["cpu"] = int(data["raw"].get('1.3.6.1.4.1.12356.101.4.1.3.0', 0))
            data["ram"] = int(data["raw"].get('1.3.6.1.4.1.12356.101.4.1.4.0', 0))
            data["sessions"] = data["raw"].get('1.3.6.1.4.1.12356.101.4.1.8.0', "0")
        elif template == "windows":
            data["cpu"] = int(data["raw"].get('1.3.6.1.2.1.25.3.3.1.2.1', 0))
            used = int(data["raw"].get('1.3.6.1.2.1.25.2.3.1.6.1', 0))
            total = int(data["raw"].get('1.3.6.1.2.1.25.2.3.1.5.1', 1))
            data["ram"] = int((used / total) * 100) if total > 0 else 0
        elif template == "linux":
            idle = int(data["raw"].get('1.3.6.1.4.1.2021.11.11.0', 100))
            data["cpu"] = 100 - idle
            total = int(data["raw"].get('1.3.6.1.4.1.2021.4.5.0', 1))
            avail = int(data["raw"].get('1.3.6.1.4.1.2021.4.6.0', 0))
            used = total - avail
            data["ram"] = int((used / total) * 100) if total > 0 else 0
        else:
            data["cpu"] = 0
            data["ram"] = 0
        return data
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_interface_stats(ip, settings):
    version = settings.get('version', 'v2c')
    community = settings.get('community', 'public')
    timeout = float(settings.get('timeout', 1500)) / 1000.0
    port = int(settings.get('port', 161))

    try:
        auth_data = _get_auth_data(version, community)
        transport = UdpTransportTarget((ip, port), timeout=timeout, retries=0)
        interfaces = []
        for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
            SnmpEngine(), auth_data, transport, ContextData(),
            ObjectType(ObjectIdentity('1.3.6.1.2.1.2.2.1.2')),
            ObjectType(ObjectIdentity('1.3.6.1.2.1.2.2.1.8')),
            ObjectType(ObjectIdentity('1.3.6.1.2.1.2.2.1.10')),
            ObjectType(ObjectIdentity('1.3.6.1.2.1.2.2.1.16')),
            lexicographicMode=False
        ):
            if errorIndication or errorStatus: break
            interfaces.append({
                "name": str(varBinds[0][1]),
                "status": int(varBinds[1][1]),
                "in_octets": int(varBinds[2][1]),
                "out_octets": int(varBinds[3][1]),
                "ts": time.time()
            })
        return {"ok": True, "interfaces": interfaces}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def bulk_discovery(ips, settings, callback):
    workers = settings.get('workers', 50)
    version = settings.get('version', 'v2c')
    community = settings.get('community', 'public')
    timeout = float(settings.get('timeout', 1500)) / 1000.0
    port = int(settings.get('port', 161))
    auto_detect = settings.get('auto_detect', True)

    def _task(ip):
        res = snmp_test(ip, version, community, timeout, port)
        if res["ok"]:
            template = detect_template(res.get("sysDescr")) if auto_detect else "unknown"
            result = {
                "ip": ip, "snmp_active": True, "version": version, "community": community,
                "port": port, "device_template": template, "sysDescr": res.get("sysDescr", ""),
                "sysName": res.get("sysName", ""), "sysObjectID": res.get("sysObjectID", "")
            }
        else:
            result = {"ip": ip, "snmp_active": False, "error": res["error"]}
        callback(result)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        executor.map(_task, ips)
