import csv, os

files = [
    "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads/2026-02-12-apollo-Accounting-2-100-employees-with-icebreakers.csv",
    "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads/2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv",
]

for f in files:
    with open(f, "r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    total = len(rows)
    has_short = sum(1 for r in rows if r.get("shortenedCompanyName", "").strip())
    print(f"{os.path.basename(f)}")
    print(f"  Total: {total} | With shortened name: {has_short}")
    # Show 10 samples: original → shortened
    samples = [r for r in rows if r.get("shortenedCompanyName", "").strip()][:10]
    for s in samples:
        org = s.get("organizationName", "")
        short = s.get("shortenedCompanyName", "")
        marker = "  " if org != short else "=="
        print(f"  {marker} {org} → {short}")
    print()
