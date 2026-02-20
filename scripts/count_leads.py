import csv
import glob

files = sorted(glob.glob("/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads/*.csv"))
for f in files:
    with open(f, "r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [r for r in reader if r.get("firstName", "").strip() and "Refer to the log" not in r.get("fullName", "")]
        print(f"{len(rows):>4} leads — {f.split('/')[-1]}")
