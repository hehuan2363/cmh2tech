"""
Generate icebreakers for cold email leads using Gemini API.
Reads CSVs from the Leads folder, adds an 'icebreaker' column, saves updated CSVs.
Saves progress every 50 leads so work isn't lost on interruption.
"""

import csv
import glob
import os
import time
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    raise ValueError("Set GEMINI_API_KEY environment variable")

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-3-flash-preview"

SYSTEM_PROMPT = """You generate one-line icebreakers for cold sales emails.

RULES:
- One complete sentence. Between 10 and 20 words.
- Spartan, laconic, casual tone. Like you typed it on your phone.
- Always start with "Hey {firstName}." using the prospect's actual first name.
- Reference something specific about their company, role, location, or scale.
- Shorten company names: "XYZ" not "XYZ Agency", "Mayo" not "Mayo Inc."
- Shorten locations: "San Fran" not "San Francisco", "BC" not "British Columbia"
- No generic openers. No exclamation marks. No quotes around the output.
- If the data is a company not a person, return: SKIP

GOOD EXAMPLES:
- Hey Mike. Love what Greystar's doing in multifamily — managing that many units is no joke.
- Hey Sarah. Saw BDO's been expanding their advisory practice in Toronto — cool to see.
- Hey James. Running ops for a 200-unit portfolio in Denver sounds like a lot of moving parts.
- Hey Lisa. Noticed Apex is hiring — looks like things are scaling fast.
- Hey Oliver. Building a full-service accounting firm in Vancouver since 2012 — solid track record.

OUTPUT: Return ONLY the complete icebreaker sentence. Nothing else."""

SAVE_EVERY = 50  # Save progress every N leads


def build_prospect_prompt(row: dict) -> str:
    """Build a prompt from the high-value columns only."""
    parts = []
    if row.get("firstName"):
        parts.append(f"Name: {row['firstName']} {row.get('lastName', '')}")
    if row.get("position"):
        parts.append(f"Role: {row['position']}")
    if row.get("organizationName"):
        parts.append(f"Company: {row['organizationName']}")
    if row.get("organizationDescription"):
        desc = row["organizationDescription"][:300]
        parts.append(f"What they do: {desc}")
    if row.get("organizationSpecialities"):
        parts.append(f"Specialities: {row['organizationSpecialities'][:200]}")
    if row.get("city") or row.get("state"):
        loc = ", ".join(filter(None, [row.get("city", ""), row.get("state", "")]))
        parts.append(f"Location: {loc}")
    if row.get("organizationSize"):
        parts.append(f"Company size: {row['organizationSize']}")
    if row.get("organizationFoundedYear"):
        parts.append(f"Founded: {row['organizationFoundedYear']}")
    if row.get("organizationIndustry"):
        parts.append(f"Industry: {row['organizationIndustry']}")
    return "\n".join(parts)


def generate_icebreaker(row: dict, retries: int = 5) -> str:
    """Generate a single icebreaker for a prospect row."""
    prospect_info = build_prospect_prompt(row)
    if not prospect_info or not row.get("firstName"):
        return "SKIP"

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=f"Generate a complete one-line icebreaker for this prospect:\n\n{prospect_info}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=1000,
                ),
            )
            text = response.text.strip().strip('"').strip("'")
            # Basic quality check
            if text and len(text) > 5 and not text.startswith("{"):
                return text
            return "SKIP"
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower() or "resource" in err.lower():
                wait = 60 * (attempt + 1)  # 60s, 120s, 180s, 240s, 300s
                print(f"    Rate limited (attempt {attempt+1}/{retries}), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Error (attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    return "SKIP"
                time.sleep(5)
    return "SKIP"


def save_csv(leads: list, fieldnames: list, output_path: str):
    """Save leads to CSV."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process_csv(filepath: str):
    """Read a CSV, generate icebreakers, write updated CSV with periodic saves."""
    filename = os.path.basename(filepath)
    output_path = filepath.replace(".csv", "-with-icebreakers.csv")

    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    print(f"{'='*60}")

    # If output file exists, resume from it
    if os.path.exists(output_path):
        print(f"Resuming from existing output file: {os.path.basename(output_path)}")
        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            leads = [r for r in reader]
    else:
        # Read from source
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = [r for r in reader]
        # Filter out Apify log rows
        leads = [r for r in rows if r.get("firstName", "").strip() and "Refer to the log" not in r.get("fullName", "")]
        # Add icebreaker field
        if "icebreaker" not in fieldnames:
            fieldnames = list(fieldnames) + ["icebreaker"]

    total = len(leads)
    already_done = sum(1 for r in leads if r.get("icebreaker", "").strip() and r["icebreaker"] != "SKIP")
    print(f"Found {total} valid leads ({already_done} already have icebreakers)")

    generated_this_run = 0

    for i, lead in enumerate(leads):
        # Skip if icebreaker already exists
        if lead.get("icebreaker", "").strip() and lead["icebreaker"] != "SKIP":
            continue

        icebreaker = generate_icebreaker(lead)
        lead["icebreaker"] = icebreaker
        generated_this_run += 1

        status = "SKIP" if icebreaker == "SKIP" else "OK"
        print(f"  [{i+1}/{total}] {status} — {lead.get('firstName', '?')} {lead.get('lastName', '?')} @ {lead.get('organizationName', '?')}")
        if status == "OK":
            print(f"           {icebreaker}")

        # Save progress periodically
        if generated_this_run % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, output_path)
            print(f"  --- Saved progress ({generated_this_run} new icebreakers so far) ---")

        # Delay between API calls
        time.sleep(0.5)

    # Final save
    save_csv(leads, fieldnames, output_path)

    skipped = sum(1 for r in leads if r.get("icebreaker") == "SKIP")
    generated = total - skipped
    print(f"\nDone: {generated} total icebreakers, {skipped} skipped, {generated_this_run} new this run")
    print(f"Saved to: {output_path}")
    return output_path


def main():
    leads_dir = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"
    csv_files = sorted(glob.glob(os.path.join(leads_dir, "2026-02-12-apollo-*.csv")))

    # Skip files that are already processed output files
    csv_files = [f for f in csv_files if "-with-icebreakers" not in f]

    if not csv_files:
        print("No CSV files found!")
        return

    print(f"Found {len(csv_files)} CSV files to process")
    output_files = []

    for filepath in csv_files:
        output = process_csv(filepath)
        output_files.append(output)

    print(f"\n{'='*60}")
    print("ALL DONE")
    print(f"{'='*60}")
    for f in output_files:
        print(f"  {os.path.basename(f)}")


if __name__ == "__main__":
    main()
