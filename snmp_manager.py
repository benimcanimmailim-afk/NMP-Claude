import threading
from concurrent.futures import ThreadPoolExecutor
from pysnmp.hlapi import *

# OIDs
OID_SYS_DESCR = '1.3.6.1.2.1.1.1.0'
OID_SYS_NAME = '1.3.6.1.2.1.1.5.0'
OID_SYS_OBJECT_ID = '1.3.6.1.2.1.1.2.0'

def snmp_test(ip, version='v2c', community='public', timeout=1.5, port=161):
    """
    Tests SNMP connectivity for a single IP.
    Returns a dict with success status and metadata.
    """
    try:
        # Prepare target
        if version == 'v2c':
            auth_data = CommunityData(community)
        else:
            # v3 requires more params, but for discovery we'll use a default/placeholder
            # User dropdown only shows v2c and v3.
            auth_data = UsmUserData('snmpuser')

        transport = UdpTransportTarget((ip, port), timeout=timeout, retries=0)

        # We want to get sysDescr, sysName, sysObjectID
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
    """
    Parses sysDescr to detect device type.
    """
    if not sys_descr:
        return "unknown"

    sd = sys_descr.lower()
    if "ios" in sd or "cisco" in sd:
        return "cisco_ios"
    if "fortigate" in sd or "fortinet" in sd:
        return "fortigate"
    if "routeros" in sd or "mikrotik" in sd:
        return "mikrotik"
    if "windows" in sd:
        return "windows"
    if "linux" in sd:
        return "linux"

    return "unknown"

def bulk_discovery(ips, settings, callback):
    """
    Performs SNMP discovery on a list of IPs.
    settings: dict with version, community, timeout, port, workers
    callback: function called for each result
    """
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
                "ip": ip,
                "snmp_active": True,
                "snmp_version": version,
                "community": community,
                "snmp_port": port,
                "device_template": template,
                "sysDescr": res.get("sysDescr", ""),
                "sysName": res.get("sysName", ""),
                "sysObjectID": res.get("sysObjectID", "")
            }
        else:
            result = {
                "ip": ip,
                "snmp_active": False,
                "error": res["error"]
            }
        callback(result)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        executor.map(_task, ips)
