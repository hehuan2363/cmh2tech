"""
Shorten organizationName into a new 'shortenedCompanyName' column using Gemini API.
Reads from the -with-icebreakers.csv files, adds the column, saves in place.
"""

import csv
import os
import time
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    raise ValueError("Set GEMINI_API_KEY environment variable")

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-3-flash-preview"

SYSTEM_PROMPT = """You shorten company names for use in cold sales emails.

RULES:
- Remove suffixes like Inc., LLC, LLP, Ltd, Corp, Corporation, Co., Group, Partners, Associates, Services, Professional Services, Solutions, Enterprises, Holdings, International, Consulting, Advisors, Management, etc.
- Keep the core recognizable brand name only.
- If the name is already short (1-2 words, no suffix), return it as-is.
- Return ONLY the shortened name, nothing else.

EXAMPLES:
- "Invictus Accounting Group LLP" → "Invictus"
- "AMS Professional Services" → "AMS"
- "Mayo Inc." → "Mayo"
- "The Property Collective Limited" → "Property Collective"
- "Burns Engineering, Inc" → "Burns"
- "R.V. Anderson Associates Limited" → "RVA"
- "Svante" → "Svante"
- "Prairie Payments Joint Venture" → "Prairie Payments"
- "Stellus Capital Management, LLC" → "Stellus"
- "SD Mayer & Associates LLP" → "SD Mayer"
- "Payroll Vault" → "Payroll Vault"
- "Curran & Associates CPAs, P.C" → "Curran"
- "JEHM Wealth & Retirement" → "JEHM"
- "CLV GROUP" → "CLV"
- "Nexus Industrial REIT" → "Nexus"

OUTPUT: Return ONLY the shortened company name. Nothing else."""

SAVE_EVERY = 50
LEADS_DIR = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"

# Only process Engineering and Accounting
FILES = [
    os.path.join(LEADS_DIR, "2026-02-12-apollo-Accounting-2-100-employees-with-icebreakers.csv"),
    os.path.join(LEADS_DIR, "2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv"),
]


def shorten_name(org_name: str, retries: int = 5) -> str:
    """Use Gemini to shorten a company name."""
    if not org_name or not org_name.strip():
        return org_name

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=f"Shorten this company name: {org_name}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=100,
                ),
            )
            text = response.text.strip().strip('"').strip("'")
            if text and len(text) > 0:
                return text
            return org_name
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower() or "resource" in err.lower():
                wait = 60 * (attempt + 1)
                print(f"    Rate limited (attempt {attempt+1}/{retries}), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Error (attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    return org_name
                time.sleep(5)
    return org_name


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process_file(filepath: str):
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    print(f"{'='*60}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    # Add column if not present
    if "shortenedCompanyName" not in fieldnames:
        fieldnames.append("shortenedCompanyName")

    total = len(leads)
    already_done = sum(1 for r in leads if r.get("shortenedCompanyName", "").strip())
    print(f"Found {total} leads ({already_done} already have shortened names)")

    processed = 0
    for i, lead in enumerate(leads):
        # Skip if already done
        if lead.get("shortenedCompanyName", "").strip():
            continue

        org = lead.get("organizationName", "")
        shortened = shorten_name(org)
        lead["shortenedCompanyName"] = shortened
        processed += 1

        changed = "OK" if shortened != org else "SAME"
        print(f"  [{i+1}/{total}] {changed} — {org} → {shortened}")

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved progress ({processed} processed so far) ---")

        time.sleep(0.3)

    # Final save
    save_csv(leads, fieldnames, filepath)
    print(f"\nDone: {processed} names shortened this run")
    print(f"Saved to: {filepath}")


def main():
    for filepath in FILES:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue
        process_file(filepath)

    print(f"\n{'='*60}")
    print("ALL DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
