"""Quick test: generate icebreakers for 3 leads (1 per niche) to verify quality."""

import csv
import os
import glob
from google import genai
from google.genai import types

API_KEY = os.environ.get("GEMINI_API_KEY", "")
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

leads_dir = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"
files = sorted(f for f in glob.glob(os.path.join(leads_dir, "*.csv")) if "-with-icebreakers" not in f)

for filepath in files:
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("firstName", "").strip() or "Refer to the log" in row.get("fullName", ""):
                continue

            parts = []
            parts.append(f"Name: {row['firstName']} {row.get('lastName', '')}")
            if row.get("position"): parts.append(f"Role: {row['position']}")
            if row.get("organizationName"): parts.append(f"Company: {row['organizationName']}")
            if row.get("organizationDescription"): parts.append(f"What they do: {row['organizationDescription'][:300]}")
            if row.get("organizationSpecialities"): parts.append(f"Specialities: {row['organizationSpecialities'][:200]}")
            loc = ", ".join(filter(None, [row.get("city", ""), row.get("state", "")]))
            if loc: parts.append(f"Location: {loc}")
            if row.get("organizationSize"): parts.append(f"Company size: {row['organizationSize']}")
            if row.get("organizationFoundedYear"): parts.append(f"Founded: {row['organizationFoundedYear']}")

            prospect_info = "\n".join(parts)

            response = client.models.generate_content(
                model=MODEL,
                contents=f"Generate a complete one-line icebreaker for this prospect:\n\n{prospect_info}",
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                    max_output_tokens=1000,
                ),
            )
            icebreaker = response.text.strip().strip('"').strip("'")

            print(f"\n--- {filename} ---")
            print(f"Lead: {row['firstName']} {row.get('lastName', '')} @ {row.get('organizationName', '')}")
            print(f"Role: {row.get('position', '')}")
            print(f"Finish reason: {response.candidates[0].finish_reason}")
            print(f"Icebreaker: {icebreaker}")
            break
