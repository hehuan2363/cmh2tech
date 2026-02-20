"""
Verify ip_blocked emails using MillionVerifier API.
Only processes leads with email_status='ip_blocked'.
Updates the CSV in-place with new statuses.
"""

import csv
import os
import time
import sys
import urllib.request
import urllib.parse
import json

API_KEY = os.environ.get("MV_API_KEY", "")
API_URL = "https://api.millionverifier.com/api/v3/"
SAVE_EVERY = 50
DELAY_BETWEEN = 0.05  # 20 req/s to be safe (limit is 300/s)

# MillionVerifier result codes → our status labels
MV_STATUS_MAP = {
    1: "valid",       # ok
    2: "catch_all",   # catch_all
    3: "unknown",     # unknown
    4: "unknown",     # error
    5: "rejected",    # disposable
    6: "rejected",    # invalid
}


def check_credits():
    url = f"https://api.millionverifier.com/api/v3/credits?api={API_KEY}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    return data


def verify_single(email):
    params = urllib.parse.urlencode({"api": API_KEY, "email": email, "timeout": 30})
    url = f"{API_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read().decode())
    return data


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process_file(filepath):
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"MillionVerifier: {filename}")
    print(f"{'='*60}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    blocked_indices = [
        i for i, r in enumerate(leads)
        if r.get("email_status", "").strip() == "ip_blocked"
    ]
    print(f"Found {len(blocked_indices)} ip_blocked leads to verify")

    if not blocked_indices:
        print("Nothing to verify!")
        return 0

    processed = 0
    stats = {}

    for idx in blocked_indices:
        lead = leads[idx]
        email = lead.get("email", "").strip()
        if not email:
            continue

        try:
            data = verify_single(email)
            result_code = data.get("resultcode", 0)
            result_text = data.get("result", "unknown")
            our_status = MV_STATUS_MAP.get(result_code, "unknown")

            lead["email_status"] = our_status
            stats[our_status] = stats.get(our_status, 0) + 1
            processed += 1

            icons = {
                "valid": "OK", "catch_all": "CA", "rejected": "XX",
                "unknown": "??",
            }
            icon = icons.get(our_status, "??")
            print(f"  [{processed}/{len(blocked_indices)}] {icon}  {our_status:15s} — {email} (MV: {result_text})")

        except Exception as e:
            print(f"  [{processed+1}/{len(blocked_indices)}] !!  API error     — {email}: {e}")
            processed += 1
            stats["api_error"] = stats.get("api_error", 0) + 1

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved ({processed} verified) ---")

        time.sleep(DELAY_BETWEEN)

    save_csv(leads, fieldnames, filepath)

    print(f"\nMillionVerifier results:")
    for s, c in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {s:15s}: {c}")

    # Overall file stats
    overall = {}
    for lead in leads:
        s = lead.get("email_status", "unknown")
        overall[s] = overall.get(s, 0) + 1
    total = len(leads)
    print(f"\nOverall file stats:")
    for s, c in sorted(overall.items(), key=lambda x: -x[1]):
        pct = c / total * 100
        print(f"  {s:15s}: {c:>4} ({pct:5.1f}%)")

    return processed


def main():
    # Check credits first
    print("Checking MillionVerifier credits...")
    try:
        credits = check_credits()
        print(f"Credits remaining: {credits}")
    except Exception as e:
        print(f"Warning: Could not check credits: {e}")

    leads_dir = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"
    files = [
        os.path.join(leads_dir, "2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv"),
        os.path.join(leads_dir, "2026-02-12-apollo-Accounting-2-100-employees-with-icebreakers.csv"),
    ]

    # Count total ip_blocked
    total_blocked = 0
    for fp in files:
        if not os.path.exists(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("email_status", "").strip() == "ip_blocked":
                    total_blocked += 1

    print(f"\nTotal ip_blocked to verify: {total_blocked}")
    if total_blocked > 499:
        print(f"WARNING: You have ~499 credits but {total_blocked} emails to verify.")
        print(f"Will process first 499 across both files.")

    credits_used = 0
    for fp in files:
        if not os.path.exists(fp):
            print(f"File not found: {fp}")
            continue
        used = process_file(fp)
        credits_used += used
        if credits_used >= 499:
            print(f"\nReached credit limit, stopping.")
            break

    print(f"\n{'='*60}")
    print(f"DONE — Used ~{credits_used} MillionVerifier credits")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
