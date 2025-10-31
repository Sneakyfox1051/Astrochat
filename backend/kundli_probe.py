"""
Standalone ProKerala Kundli fetcher (safe debug utility)

Usage (Windows PowerShell or any shell):

  python backend/kundli_probe.py \
    --name "Test User" \
    --dob 1990-05-15 \
    --tob 14:30:00 \
    --place "Mumbai" \
    --timezone Asia/Kolkata

This script:
  1) Loads PROKERALA_CLIENT_ID/PROKERALA_CLIENT_SECRET from backend/.env or environment
  2) Gets access token
  3) Calls v2/astrology/kundli/advanced
  4) Normalizes list/dict shapes safely
  5) Prints compacted JSON with key sections (planet_positions, dasha, mangal_dosha)

It DOES NOT modify or import the main Flask app. Safe to run independently.
"""

import os
import json
import argparse
from datetime import datetime

import requests
import pytz
from dotenv import load_dotenv


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(env_path, override=True)
    cid = os.getenv('PROKERALA_CLIENT_ID')
    csec = os.getenv('PROKERALA_CLIENT_SECRET')
    return cid, csec


def get_token(client_id: str, client_secret: str) -> str:
    token_url = "https://api.prokerala.com/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    resp = requests.post(token_url, data=data, timeout=20)
    resp.raise_for_status()
    return resp.json().get("access_token")


def iso_dt(dob: str, tob: str, tz_name: str) -> str:
    # dob 'YYYY-MM-DD', tob 'HH:MM[:SS]'
    # normalize time to HH:MM:SS
    if len(tob.split(':')) == 2:
        tob = f"{tob}:00"
    dt = datetime.strptime(f"{dob} {tob}", "%Y-%m-%d %H:%M:%S")
    tz = pytz.timezone(tz_name)
    return tz.localize(dt).isoformat()


def safe_get_positions(data_dict: dict):
    raw_positions = (
        (data_dict.get('planet_position') or {}).get('planet_position')
        or data_dict.get('planet_positions')
        or data_dict.get('planets')
        or []
    )
    if isinstance(raw_positions, dict):
        return raw_positions.get('planet_position', [])
    if isinstance(raw_positions, list):
        return raw_positions
    return []


def fetch_kundli_advanced(token: str, coords: str, iso_datetime: str) -> dict:
    url = "https://api.prokerala.com/v2/astrology/kundli/advanced"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"ayanamsa": 5, "coordinates": coords, "datetime": iso_datetime}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    raw = resp.json()
    # Normalize top-level content
    if not isinstance(raw, dict):
        raw = {"data": raw}
    data = raw.get("data", {})
    # If provider sends a list, wrap it in expected shape
    if isinstance(data, list):
        data = {"planet_position": {"planet_position": data}}
    positions = safe_get_positions(data)
    dasha = data.get('dasha', {}) or data.get('dasha_periods', {})
    mangal = data.get('mangal_dosha', {})
    out = {
        "raw_keys": list(raw.keys()),
        "data_keys": list(data.keys()) if isinstance(data, dict) else str(type(data)),
        "planet_positions_count": len(positions) if isinstance(positions, list) else 0,
        "sample_positions": positions[:3] if isinstance(positions, list) else [],
        "dasha_keys": list(dasha.keys()) if isinstance(dasha, dict) else str(type(dasha)),
        "mangal_dosha": mangal,
    }
    return out


def main():
    parser = argparse.ArgumentParser(description="ProKerala Kundli Advanced Fetch Debugger")
    parser.add_argument('--name', required=False, default='Adab Bawa', help='Full name (default: Adab Bawa)')
    parser.add_argument('--dob', required=True, help='YYYY-MM-DD')
    parser.add_argument('--tob', required=True, help='HH:MM or HH:MM:SS')
    parser.add_argument('--place', required=True, help='Birth place (for display only)')
    parser.add_argument('--lat', type=float, help='Latitude (if you know exact)')
    parser.add_argument('--lon', type=float, help='Longitude (if you know exact)')
    parser.add_argument('--timezone', default='Asia/Kolkata', help='IANA timezone, default Asia/Kolkata')
    args = parser.parse_args()

    client_id, client_secret = load_env()
    if not client_id or not client_secret:
        print(json.dumps({
            "ok": False,
            "error": "Missing PROKERALA_CLIENT_ID/PROKERALA_CLIENT_SECRET in backend/.env or environment"
        }, indent=2, ensure_ascii=False))
        return

    try:
        token = get_token(client_id, client_secret)
    except Exception as e:
        print(json.dumps({"ok": False, "stage": "token", "error": str(e)}, indent=2, ensure_ascii=False))
        return

    try:
        iso = iso_dt(args.dob, args.tob, args.timezone)
        if args.lat is None or args.lon is None:
            # Minimal geocoding: default to Mumbai to avoid adding geopy dependency here
            lat, lon = 19.0760, 72.8777
        else:
            lat, lon = args.lat, args.lon
        coords = f"{lat},{lon}"

        result = fetch_kundli_advanced(token, coords, iso)
        print(json.dumps({
            "ok": True,
            "coords": coords,
            "datetime": iso,
            "result": result
        }, indent=2, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"ok": False, "stage": "advanced", "error": str(e)}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()


