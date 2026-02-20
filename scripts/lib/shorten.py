"""Shorten company names using Gemini API."""
import csv
import os
import time
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, SAVE_EVERY

if not GEMINI_API_KEY:
    raise ValueError("Set GEMINI_API_KEY environment variable")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """You shorten company names for use in cold sales emails.

RULES:
- Remove suffixes like Inc., LLC, LLP, Ltd, Corp, Co., Group, Partners, Associates, Services, Solutions, Enterprises, Holdings, International, Consulting, Advisors, Management, etc.
- Keep the core recognizable brand name only.
- If the name is already short (1-2 words, no suffix), return it as-is.
- Return ONLY the shortened name, nothing else.

EXAMPLES:
- "Invictus Accounting Group LLP" → "Invictus"
- "AMS Professional Services" → "AMS"
- "Mayo Inc." → "Mayo"
- "Burns Engineering, Inc" → "Burns"
- "SD Mayer & Associates LLP" → "SD Mayer"
- "Payroll Vault" → "Payroll Vault"
- "CLV GROUP" → "CLV"

OUTPUT: Return ONLY the shortened company name. Nothing else."""


def shorten_one(org_name: str, retries: int = 5) -> str:
    if not org_name or not org_name.strip():
        return org_name

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=f"Shorten this company name: {org_name}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=100,
                ),
            )
            text = response.text.strip().strip('"').strip("'")
            return text if text else org_name
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower() or "resource" in err.lower():
                wait = 60 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Error: {e}")
                if attempt == retries - 1:
                    return org_name
                time.sleep(5)
    return org_name


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process(filepath: str):
    """Add shortenedCompanyName column to a CSV."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Shortening company names: {filename}")
    print(f"{'='*60}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    if "shortenedCompanyName" not in fieldnames:
        fieldnames.append("shortenedCompanyName")

    total = len(leads)
    already_done = sum(1 for r in leads if r.get("shortenedCompanyName", "").strip())
    print(f"Found {total} leads ({already_done} already done)")

    processed = 0
    for i, lead in enumerate(leads):
        if lead.get("shortenedCompanyName", "").strip():
            continue

        org = lead.get("organizationName", "")
        lead["shortenedCompanyName"] = shorten_one(org)
        processed += 1

        print(f"  [{i+1}/{total}] {org} → {lead['shortenedCompanyName']}")

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved ---")

        time.sleep(0.3)

    save_csv(leads, fieldnames, filepath)
    print(f"Done: {processed} names shortened")
