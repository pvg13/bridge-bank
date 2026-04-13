import json
import requests
import hashlib
import subprocess
import platform
import logging
import uuid
from . import db

logger = logging.getLogger(__name__)

LICENCE_BASE = "https://api.bridgebank.app"


def _cache_license_info(info):
    db.set_setting("licence_info_cache", json.dumps(info))


def _get_cached_license_info():
    raw = db.get_setting("licence_info_cache")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return None

def _get_hw_uuid():
    system = platform.system()
    try:
        if system == "Darwin":
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                timeout=5, stderr=subprocess.DEVNULL,
            ).decode()
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        elif system == "Windows":
            out = subprocess.check_output(
                ["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"],
                timeout=5, stderr=subprocess.DEVNULL,
            ).decode()
            for line in out.splitlines():
                if "MachineGuid" in line:
                    return line.strip().split()[-1]
        elif system == "Linux":
            try:
                return open("/etc/machine-id").read().strip()
            except FileNotFoundError:
                pass
    except Exception:
        pass
    return ""

def _get_fingerprint():
    stored = db.get_setting("license_instance_id_v2")
    if stored:
        return stored
    # Migrating from v1: deactivate old fingerprint to free the activation slot
    old_fp = db.get_setting("license_instance_id")
    if old_fp:
        key = db.get_setting("licence_key")
        if key:
            try:
                requests.post(
                    LICENCE_BASE + "/deactivate",
                    json={"license_key": key, "machine_fingerprint": old_fp},
                    timeout=10,
                )
            except requests.RequestException:
                pass
        db.set_setting("license_instance_id", "")
    parts = [
        str(uuid.getnode()),
        _get_hw_uuid(),
    ]
    raw = "|".join(parts)
    fp = hashlib.sha256(raw.encode()).hexdigest()[:32]
    db.set_setting("license_instance_id_v2", fp)
    return fp

def activate(key):
    db.set_setting("licence_key", key)
    db.set_setting("licence_validated", "1")
    return {"valid": True, "error": None}

def deactivate():
    db.set_setting("licence_key", "")
    db.set_setting("license_instance_id", "")
    db.set_setting("licence_validated", "")
    db.set_setting("licence_info_cache", "")
    return {"success": True, "error": None}

def validate(key=None):
    return {"valid": True, "error": None}

def get_activation_info():
    return {"usage": 1, "limit": 999, "bank_account_limit": 999, "is_trial": False, "expires_at": None}
