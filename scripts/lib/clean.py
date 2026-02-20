"""Create clean CSV with only sendable leads."""
import csv
import os


def process(filepath: str) -> str:
    """Remove non-sendable leads, create *-CLEAN.csv. Returns output path."""
    filename = os.path.basename(filepath)
    output_path = filepath.replace("-with-icebreakers.csv", "-CLEAN.csv").replace(".csv", "-CLEAN.csv")
    if output_path == filepath:
        output_path = filepath.replace(".csv", "-CLEAN.csv")

    print(f"\n{'='*60}")
    print(f"Cleaning: {filename}")
    print(f"{'='*60}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    sendable = [r for r in leads if r.get("email_status", "") in ("valid", "catch_all")]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sendable)

    total = len(leads)
    valid = sum(1 for r in sendable if r["email_status"] == "valid")
    catch_all = sum(1 for r in sendable if r["email_status"] == "catch_all")
    removed = total - len(sendable)

    print(f"  Total leads:    {total}")
    print(f"  Sendable:       {len(sendable)} ({valid} valid + {catch_all} catch_all)")
    print(f"  Removed:        {removed}")
    print(f"  Saved to:       {os.path.basename(output_path)}")

    return output_path
