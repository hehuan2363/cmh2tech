"""Verify ip_blocked emails using MillionVerifier API."""
import csv
import json
import os
import time
import urllib.request
import urllib.parse
from config import MV_API_KEY, SAVE_EVERY

API_URL = "https://api.millionverifier.com/api/v3/"

MV_STATUS_MAP = {
    1: "valid",       # ok
    2: "catch_all",   # catch_all
    3: "unknown",     # unknown
    4: "unknown",     # error
    5: "rejected",    # disposable
    6: "rejected",    # invalid
}


def check_credits(api_key: str) -> dict:
    url = f"https://api.millionverifier.com/api/v3/credits?api={api_key}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read().decode())


def verify_single(email: str, api_key: str) -> dict:
    params = urllib.parse.urlencode({"api": api_key, "email": email, "timeout": 30})
    url = f"{API_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read().decode())


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process(filepath: str, api_key: str = ""):
    """Verify ip_blocked emails via MillionVerifier API."""
    api_key = api_key or MV_API_KEY
    if not api_key:
        print("ERROR: Set MV_API_KEY environment variable or pass --mv-key")
        return

    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"MillionVerifier: {filename}")
    print(f"{'='*60}")

    # Check credits
    try:
        credits = check_credits(api_key)
        remaining = credits.get("credits", 0)
        print(f"Credits remaining: {remaining}")
        if remaining <= 0:
            print("ERROR: No credits remaining. Buy more at millionverifier.com")
            return
    except Exception as e:
        print(f"Warning: Could not check credits: {e}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    blocked = [i for i, r in enumerate(leads) if r.get("email_status", "").strip() == "ip_blocked"]
    print(f"Found {len(blocked)} ip_blocked leads to verify")

    if not blocked:
        print("Nothing to verify!")
        return

    processed = 0
    stats = {}

    for idx in blocked:
        lead = leads[idx]
        email = lead.get("email", "").strip()
        if not email:
            continue

        try:
            data = verify_single(email, api_key)
            result_code = data.get("resultcode", 0)
            result_text = data.get("result", "unknown")
            our_status = MV_STATUS_MAP.get(result_code, "unknown")

            lead["email_status"] = our_status
            stats[our_status] = stats.get(our_status, 0) + 1
            processed += 1

            icons = {"valid": "OK", "catch_all": "CA", "rejected": "XX", "unknown": "??"}
            icon = icons.get(our_status, "??")
            print(f"  [{processed}/{len(blocked)}] {icon}  {our_status:15s} — {email} (MV: {result_text})")

        except Exception as e:
            print(f"  [{processed+1}/{len(blocked)}] !!  API error     — {email}: {e}")
            processed += 1
            stats["api_error"] = stats.get("api_error", 0) + 1

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved ---")

        time.sleep(0.05)

    save_csv(leads, fieldnames, filepath)

    print(f"\nMillionVerifier results:")
    for s, c in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {s:15s}: {c}")
