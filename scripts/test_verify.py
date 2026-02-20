"""Quick test: verify first 10 emails from Engineering CSV."""
import csv
import time
from verify_emails import verify_email

filepath = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads/2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv"
with open(filepath, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    tested = 0
    for row in reader:
        email = row.get("email", "").strip()
        if not email:
            continue
        status = verify_email(email)
        print(f"  {status:15s} — {email}")
        tested += 1
        if tested >= 10:
            break
        time.sleep(0.5)
