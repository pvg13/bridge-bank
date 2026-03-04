#!/usr/bin/env python3
"""
dosetup.py -- Run this once to authorise Enable Banking and save your session.
Re-run every 180 days to renew the session.

Usage:
  python3 dosetup.py

Requirements:
  pip install requests PyJWT cryptography
"""
import requests, time, uuid, json, os, sys
from urllib.parse import urlparse, parse_qs
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import jwt

# ---------------------------------------------------------------------------
# Configuration -- edit these or set as environment variables
# ---------------------------------------------------------------------------
APP_ID       = os.environ.get("EB_APPLICATION_ID", "")
BANK_NAME    = os.environ.get("EB_BANK_NAME", "Revolut")
BANK_COUNTRY = os.environ.get("EB_BANK_COUNTRY", "GB")   # ISO 3166-1 alpha-2
PSU_TYPE     = os.environ.get("EB_PSU_TYPE", "personal") # personal or business
DATA_DIR     = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
# ---------------------------------------------------------------------------

KEY_FILE    = os.path.join(DATA_DIR, "private.pem")
STATE_FILE  = os.path.join(DATA_DIR, "state.json")
EB_API      = "https://api.enablebanking.com"

if not APP_ID:
    print("ERROR: EB_APPLICATION_ID is not set.")
    print("  Set it as an environment variable or edit APP_ID in this script.")
    sys.exit(1)

if not os.path.exists(KEY_FILE):
    print(f"ERROR: Private key not found at {KEY_FILE}")
    print("  Download your private.pem from enablebanking.com and place it in the data/ folder.")
    sys.exit(1)

key_data = open(KEY_FILE, "rb").read()
key = load_pem_private_key(key_data, password=None)


def make_headers():
    now = int(time.time())
    payload = {
        "iss": "enablebanking.com",
        "aud": "api.enablebanking.com",
        "iat": now,
        "exp": now + 3600,
        "jti": str(uuid.uuid4()),
        "sub": APP_ID,
    }
    token = jwt.encode(payload, key, algorithm="RS256", headers={"kid": APP_ID})
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# Step 1: Request authorisation URL
valid_until = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 180 * 24 * 3600))
body = {
    "access": {"valid_until": valid_until},
    "aspsp": {"name": BANK_NAME, "country": BANK_COUNTRY},
    "state": str(uuid.uuid4()),
    "redirect_url": "https://enablebanking.com/",
    "psu_type": PSU_TYPE,
}

print(f"\nRequesting authorisation for {BANK_NAME} ({BANK_COUNTRY})...")
r = requests.post(f"{EB_API}/auth", json=body, headers=make_headers())
r.raise_for_status()
auth_url = r.json()["url"]

print(f"\nOpen this URL in your browser:\n\n  {auth_url}\n")
print("Log in to your bank, approve access, then paste the full redirect URL below.")
print("(It starts with https://enablebanking.com/?code=...)\n")
redirect_url = input("Paste redirect URL: ").strip()

# Step 2: Exchange code for session
params = parse_qs(urlparse(redirect_url).query)
if "code" not in params or "state" not in params:
    print("ERROR: Could not find 'code' and 'state' in the URL. Did you paste the full URL?")
    sys.exit(1)

code  = params["code"][0]
state = params["state"][0]

print("\nExchanging code for session...")
r2 = requests.post(f"{EB_API}/sessions", json={"code": code, "state": state}, headers=make_headers())
r2.raise_for_status()
data = r2.json()

session_id = data["session_id"]
accounts   = data.get("accounts", [])

if not accounts:
    print("ERROR: No accounts returned. Check your bank connection.")
    sys.exit(1)

print(f"\nSession ID: {session_id}")
print(f"Session valid until: {valid_until}")
print(f"\nAccounts found ({len(accounts)}):")
for i, acc in enumerate(accounts):
    uid  = acc.get("uid") or acc.get("account_uid") or acc.get("resource_id")
    iban = (acc.get("account_id") or {}).get("iban", "")
    name = acc.get("name", f"Account {i+1}")
    print(f"  [{i}] {name} | {iban} | uid={uid}")

# If multiple accounts, ask which one
if len(accounts) == 1:
    chosen = accounts[0]
else:
    idx = int(input("\nEnter account number to use [0]: ").strip() or "0")
    chosen = accounts[idx]

account_uid = chosen.get("uid") or chosen.get("account_uid") or chosen.get("resource_id")
if not account_uid:
    print("ERROR: Could not determine account UID. Check Enable Banking dashboard.")
    sys.exit(1)

# Step 3: Save state
os.makedirs(DATA_DIR, exist_ok=True)
state_data = {}
if os.path.exists(STATE_FILE):
    with open(STATE_FILE) as f:
        state_data = json.load(f)

state_data["eb_session_id"]     = session_id
state_data["eb_session_expiry"] = valid_until
state_data["eb_account_uid"]    = account_uid

with open(STATE_FILE, "w") as f:
    json.dump(state_data, f, indent=2)

print(f"\nDone! State saved to {STATE_FILE}")
print("You can now start the container:\n\n  docker compose up -d\n")
