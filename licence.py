import requests
import logging
from db import get_setting, set_setting

logger = logging.getLogger(__name__)

LEMON_BASE = "https://api.lemonsqueezy.com/v1/licenses"

def _instance_id():
    return get_setting("licence_instance_id")

def activate(key: str) -> dict:
    existing = _instance_id()
    if existing:
        result = validate(key)
        if result["valid"]:
            return result
        set_setting("licence_instance_id", "")

    try:
        resp = requests.post(
            f"{LEMON_BASE}/activate",
            json={"license_key": key, "instance_name": "bridge-bank"},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("activated"):
            instance_id = data["instance"]["id"]
            set_setting("licence_instance_id", instance_id)
            set_setting("licence_key", key)
            return {"valid": True, "error": None}
        else:
            msg = data.get("error") or data.get("message") or "Invalid licence key."
            return {"valid": False, "error": msg}
    except requests.RequestException as e:
        logger.warning("Licence activate failed (network): %s", e)
        return {"valid": True, "error": None, "offline": True}

def validate(key: str = None) -> dict:
    import os
    key = key or os.environ.get("LICENCE_KEY", "")
    if not key:
        return {"valid": False, "error": "No licence key configured. Add LICENCE_KEY to your .env file."}

    instance_id = _instance_id()

    if not instance_id:
        return activate(key)

    try:
        resp = requests.post(
            f"{LEMON_BASE}/validate",
            json={"license_key": key, "instance_id": instance_id},
            timeout=10,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("valid"):
            return {"valid": True, "error": None}
        else:
            msg = data.get("error") or data.get("message") or "Invalid licence key."
            return {"valid": False, "error": msg}
    except requests.RequestException as e:
        logger.warning("Licence check failed (network): %s", e)
        return {"valid": True, "error": None, "offline": True}
