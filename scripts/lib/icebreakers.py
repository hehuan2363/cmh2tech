"""Generate icebreakers for cold email leads using Gemini API."""
import csv
import os
import time
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, SAVE_EVERY

if not GEMINI_API_KEY:
    raise ValueError("Set GEMINI_API_KEY environment variable")

client = genai.Client(api_key=GEMINI_API_KEY)

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

OUTPUT: Return ONLY the complete icebreaker sentence. Nothing else."""


def build_prospect_prompt(row: dict) -> str:
    parts = []
    if row.get("firstName"):
        parts.append(f"Name: {row['firstName']} {row.get('lastName', '')}")
    if row.get("position"):
        parts.append(f"Role: {row['position']}")
    if row.get("organizationName"):
        parts.append(f"Company: {row['organizationName']}")
    if row.get("organizationDescription"):
        parts.append(f"What they do: {row['organizationDescription'][:300]}")
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


def generate_one(row: dict, retries: int = 5) -> str:
    prospect_info = build_prospect_prompt(row)
    if not prospect_info or not row.get("firstName"):
        return "SKIP"

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=f"Generate a complete one-line icebreaker for this prospect:\n\n{prospect_info}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=1000,
                ),
            )
            text = response.text.strip().strip('"').strip("'")
            if text and len(text) > 5 and not text.startswith("{"):
                return text
            return "SKIP"
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower() or "resource" in err.lower():
                wait = 60 * (attempt + 1)
                print(f"    Rate limited (attempt {attempt+1}/{retries}), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    Error (attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    return "SKIP"
                time.sleep(5)
    return "SKIP"


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process(filepath: str) -> str:
    """Generate icebreakers for a CSV file. Returns output path."""
    filename = os.path.basename(filepath)
    output_path = filepath.replace(".csv", "-with-icebreakers.csv")

    print(f"\n{'='*60}")
    print(f"Generating icebreakers: {filename}")
    print(f"{'='*60}")

    if os.path.exists(output_path):
        print(f"Resuming from: {os.path.basename(output_path)}")
        with open(output_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames)
            leads = list(reader)
    else:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames)
            leads = [r for r in reader if r.get("firstName", "").strip() and "Refer to the log" not in r.get("fullName", "")]
        if "icebreaker" not in fieldnames:
            fieldnames = list(fieldnames) + ["icebreaker"]

    total = len(leads)
    already_done = sum(1 for r in leads if r.get("icebreaker", "").strip() and r["icebreaker"] != "SKIP")
    print(f"Found {total} leads ({already_done} already done)")

    generated = 0
    for i, lead in enumerate(leads):
        if lead.get("icebreaker", "").strip() and lead["icebreaker"] != "SKIP":
            continue

        lead["icebreaker"] = generate_one(lead)
        generated += 1

        status = "SKIP" if lead["icebreaker"] == "SKIP" else "OK"
        print(f"  [{i+1}/{total}] {status} — {lead.get('firstName', '?')} @ {lead.get('organizationName', '?')}")

        if generated % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, output_path)
            print(f"  --- Saved ({generated} new) ---")

        time.sleep(0.5)

    save_csv(leads, fieldnames, output_path)
    print(f"Done: {generated} new icebreakers. Saved to {os.path.basename(output_path)}")
    return output_path
