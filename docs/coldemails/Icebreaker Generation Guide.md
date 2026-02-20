# Icebreaker Generation Guide — CMH2.tech

## Overview

You have 900 leads across 3 niches. For each lead, you need a 1-line personalized icebreaker that goes into the `{{icebreaker}}` variable in your cold email sequences.

---

## Method: Google Sheets + Gemini

### Step 1: Set up your spreadsheet

Import your Apify CSV into Google Sheets. Make sure columns include:

| A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|
| firstName | lastName | companyName | title | industry | city | linkedinUrl |

Add a new column H: **icebreaker**

### Step 2: The Prompt

Paste this formula in cell **H2** (adjust column letters to match your sheet):

```
=GEMINI("You are an icebreaker generator for cold emails. Generate a single, short, casual opening line for a cold email.

PROSPECT INFO:
- Name: " & A2 & " " & B2 & "
- Company: " & C2 & "
- Title: " & D2 & "
- Industry: " & E2 & "
- Location: " & F2 & "

RULES:
1. Write in a spartan, laconic tone. One sentence max. No fluff.
2. Reference something specific about their company, role, or location — make it feel like you actually looked them up.
3. Shorten company names wherever possible (say 'XYZ' instead of 'XYZ Agency', 'Mayo' instead of 'Mayo Inc.').
4. Shorten locations (say 'San Fran' instead of 'San Francisco', 'BC' instead of 'British Columbia').
5. Do NOT use generic openers like 'I hope this email finds you well' or 'I came across your profile'.
6. Do NOT use exclamation marks.
7. The tone should sound like a real person typed this on their phone — casual, not salesy.
8. Start with 'Hey " & A2 & ".' always.
9. If the data looks like a company (not a person), return exactly: SKIP

GOOD EXAMPLES:
- Hey Mike. Love what Greystar's doing in multifamily — managing that many units is no joke.
- Hey Sarah. Saw BDO's been expanding their advisory practice in Toronto — cool to see.
- Hey James. Running ops for a 200-unit portfolio in Denver sounds like a lot of moving parts.
- Hey Lisa. Noticed Apex is hiring — looks like things are scaling fast over there.

BAD EXAMPLES (do NOT write like these):
- Hey Mike! I hope this message finds you well. I was really impressed by your company's growth!
- Hey Sarah. I came across your LinkedIn profile and was fascinated by your journey.
- Hey James. As a fellow professional in the industry, I wanted to reach out.

Return ONLY the icebreaker line, nothing else.")
```

### Step 3: Fill down

1. Paste the formula in H2
2. Wait for the result to generate (~2-3 seconds)
3. Select H2, drag the fill handle down to H901 (all 900 rows)
4. **Important:** Google Sheets rate-limits API calls. If you get errors, do it in batches of 50-100 rows at a time. Wait 30 seconds between batches.

### Step 4: Convert formulas to plain text

Once all icebreakers are generated:
1. Select the entire icebreaker column (H2:H901)
2. **Ctrl+C** to copy
3. **Ctrl+Shift+V** to paste as values only (removes the formula, keeps the text)

This is important — you don't want the formulas recalculating or breaking when you export.

### Step 5: Clean up

Manually scan the column for:
- Any rows that say "SKIP" — delete these leads (they're companies, not people)
- Any icebreakers that sound generic or robotic — rewrite or regenerate
- Any icebreakers that are too long (should be 1 sentence max)

This takes ~15 minutes for 900 leads. Don't skip this step.

### Step 6: Export and upload to Instantly

1. Download the sheet as CSV
2. In Instantly, create a new campaign
3. Upload the CSV
4. Map the `icebreaker` column to a custom variable called `{{icebreaker}}`
5. Map `firstName`, `companyName`, etc. to their respective variables

---

## Alternative: GPT for Sheets Add-on

If `=GEMINI()` isn't available in your Google Workspace:

1. Install **"GPT for Sheets and Docs"** add-on (by Talarian)
2. Add your OpenAI API key in the add-on settings
3. Use the same prompt but with `=GPT()` instead of `=GEMINI()`
4. Cost: ~$0.50 for 900 leads using GPT-4o-mini

---

## Alternative: Python Script (Bulk)

If you prefer running it locally for more control:

```python
import csv
import json
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

SYSTEM_PROMPT = """You are an icebreaker generator for cold emails. Given prospect info, generate a single casual opening line.

Rules:
- Spartan, laconic tone. One sentence max.
- Reference something specific about their company, role, or location.
- Shorten company names (XYZ instead of XYZ Agency).
- Shorten locations (San Fran instead of San Francisco).
- No generic openers. No exclamation marks.
- Sound like a real person typing on their phone.
- Always start with "Hey {firstName}."
- If data looks like a company (not a person), return exactly: SKIP

Return ONLY the icebreaker line."""

def generate_icebreaker(row):
    prompt = f"""Name: {row['firstName']} {row['lastName']}
Company: {row['companyName']}
Title: {row['title']}
Industry: {row['industry']}
Location: {row['city']}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        max_tokens=100,
        temperature=0.8
    )
    return response.choices[0].message.content.strip()

# Read input CSV
with open("leads.csv", "r") as f:
    reader = csv.DictReader(f)
    leads = list(reader)

# Generate icebreakers
for lead in leads:
    lead["icebreaker"] = generate_icebreaker(lead)
    print(f"{lead['firstName']} {lead['lastName']}: {lead['icebreaker']}")

# Write output CSV
fieldnames = list(leads[0].keys())
with open("leads_with_icebreakers.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(leads)

print(f"Done. {len(leads)} icebreakers generated.")
```

**Cost estimate:** GPT-4o-mini at ~$0.15/1M input tokens → 900 leads ≈ $0.30-0.50 total.

---

## Niche-Specific Tips

When reviewing icebreakers, make sure they feel natural for the niche:

**Property Management:**
- Reference portfolio size, number of units, or markets they operate in
- "Managing 200 units in Denver sounds like a lot of moving parts"

**Engineering/Professional Services:**
- Reference recent projects, certifications, or office locations
- "Saw Jacobs just won that infrastructure contract in Calgary — congrats"

**Accounting/Bookkeeping:**
- Reference firm size, specializations, or busy season
- "Running a 15-person firm through tax season is no small feat"

---

## Checklist Before Sending

- [ ] All 900 rows have an icebreaker (no blanks)
- [ ] "SKIP" rows are removed
- [ ] No icebreaker exceeds 1 sentence
- [ ] No exclamation marks
- [ ] Every icebreaker starts with "Hey {firstName}."
- [ ] Icebreakers sound casual, not salesy
- [ ] Spot-checked at least 20 random icebreakers for quality
- [ ] Exported as CSV with proper column mapping
- [ ] Uploaded to Instantly with `{{icebreaker}}` variable mapped
