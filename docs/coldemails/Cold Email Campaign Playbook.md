# Cold Email Campaign Playbook — CMH2.tech

Reusable step-by-step process for launching cold email campaigns. Run this end-to-end for any new niche or campaign.

---

## Overview

**Total time:** ~2-3 hours per niche (mostly automated)
**Cost per 1,000 leads:** ~$5 Apify scraping + ~$3 MillionVerifier + ~$0.50 Gemini API = ~$8.50

### Pipeline

```
1. Pick Niche & Write Offers
2. Source Leads (Apollo via Apify)
3. Generate Icebreakers (Gemini API)
4. Shorten Company Names (Gemini API)
5. Verify Emails (SMTP local + MillionVerifier for blocked)
6. Create Clean CSV (remove bad emails)
7. Write Email Sequences
8. Launch on Instantly
```

---

## Step 1: Pick Niche & Write Offers

### Offer Formula (from Nick Saraev's Maker School)
Every offer must be:
- **Free** — zero financial risk to the prospect
- **Low-friction response** — one-word reply ("yes", "interested")
- **Cheap to deliver** — reuse existing tools/templates

### Two Offer Types Per Niche
- **Offer A: Free Build** — build something tangible for free (bot, demo, tool)
- **Offer B: Free Audit** — review their workflows, give actionable plan

### Zero Risk Framing (from Sav/Nate Herk strategy)
Add explicit risk reversal language:
- "You wouldn't owe me anything unless it actually drives results"
- "No cost, no strings — I'll do all the work"
- "Worst case, you walk away with a clear action plan"

### Niche Directory Strategy (from Sav/Nate Herk)
Before going to Apollo, find niche-specific databases for higher quality leads:
- Ask AI: "Where can I find a database of [industry] firms?"
- Examples: AIA (architects), AICPA (accountants), industry association directories
- These give 100% accurate company lists; then use Apollo to enrich with emails

### Files
- Offer templates: `docs/coldemails/6 Offers.md`
- Offer writing guide: `docs/coldemails/How to write offer.md`

---

## Step 2: Source Leads

### Tool: Apollo via Apify
- Apify actor: Apollo scraper
- Cost: ~$5 per 1,000 leads
- Export as CSV to `docs/coldemails/Leads/`

### Naming Convention
```
YYYY-MM-DD-apollo-{Niche}-{filters}-description.csv
```
Example: `2026-02-12-apollo-Engineering-service-50-500-employees.csv`

### Key Columns to Keep
High-value (used for personalization):
- `firstName`, `lastName`, `email`, `position`
- `organizationName`, `organizationDescription`, `organizationSpecialities`
- `city`, `state`, `organizationSize`, `organizationFoundedYear`, `organizationIndustry`

Skip (noise):
- `linkedinUrl`, `phone_numbers`, `personal_email`, `source`, `country`
- `organizationWebsite`, `organizationLinkedinUrl`, `organizationCity`, `organizationState`

---

## Step 3: Generate Icebreakers

### Tool: `scripts/generate_icebreakers.py`
- Uses Gemini API (`gemini-3-flash-preview`, temperature 0.8)
- Reads CSV, adds `icebreaker` column, saves as `*-with-icebreakers.csv`
- Saves progress every 50 leads (resumable)
- Rate limit handling: 5 retries with 60s incremental backoff

### Run Command
```bash
cd scripts
export GEMINI_API_KEY="your-key-here"
uv run python -u generate_icebreakers.py
```

### Icebreaker Rules
- One sentence, 10-20 words
- Casual/spartan tone ("typed on phone")
- Always starts with "Hey {firstName}."
- References something specific (company, role, location, scale)
- Shortens company names and locations
- Returns "SKIP" for non-person entries

### API Key
- Gemini: stored in env var `GEMINI_API_KEY`

---

## Step 4: Shorten Company Names

### Tool: `scripts/shorten_company_names.py`
- Uses Gemini API (`gemini-3-flash-preview`, temperature 0.2)
- Adds `shortenedCompanyName` column
- Used as `{{companyName}}` variable in email sequences

### Run Command
```bash
cd scripts
export GEMINI_API_KEY="your-key-here"
uv run python -u shorten_company_names.py
```

### Update FILE paths in script for new campaigns
Edit the `FILES` list in the script to point to your new CSV files.

---

## Step 5: Verify Emails

### Layer 1: Local SMTP Verification
**Tool:** `scripts/verify_emails.py`
- 3-layer check: syntax → MX lookup → SMTP RCPT TO probe
- Adds `email_status` column to CSV
- Saves progress every 50 leads (resumable)
- Distinguishes Spamhaus IP blocks from real rejections

```bash
cd scripts
uv run python -u verify_emails.py
```

**Statuses:**
| Status | Meaning | Action |
|--------|---------|--------|
| `valid` | Mailbox confirmed | Safe to send |
| `catch_all` | Server accepts any email | Risky (~60% deliverable) |
| `rejected` | Mailbox doesn't exist | REMOVE |
| `no_mx` | Domain has no mail server | REMOVE |
| `invalid_syntax` | Bad email format | REMOVE |
| `no_email` | No email in lead data | REMOVE |
| `ip_blocked` | Our IP blocked (Spamhaus) | Needs MillionVerifier |
| `timeout` | Server didn't respond | Re-verify later |
| `unknown` | Can't determine | Re-verify later |

**Known issue:** Residential IP (24.150.119.121) is on Spamhaus blocklist. Most Outlook/Microsoft-hosted domains will return `ip_blocked`. Use MillionVerifier for these.

### Layer 2: MillionVerifier API (for ip_blocked leads)
**Tool:** `scripts/verify_via_millionverifier.py`
- Verifies only `ip_blocked` leads via MillionVerifier API
- Cost: ~$3 per 500 emails (or ~$15 per 25,000)
- API key stored in script (update if needed)

```bash
cd scripts
uv run python -u verify_via_millionverifier.py
```

**Important:** Set IP restriction to "Allow-only" with your current IP in MillionVerifier dashboard. Add `User-Agent` header to avoid 403 errors.

### Update FILE paths in scripts for new campaigns
Edit the `files` list in `verify_emails.py` and `verify_via_millionverifier.py` main() functions.

---

## Step 6: Create Clean CSV

After verification, create a clean file with only sendable leads:

```python
# Quick one-liner to create clean CSV
import csv, os

src = "path/to/verified-file.csv"
dst = "path/to/Niche-CLEAN.csv"

with open(src, 'r') as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    leads = [r for r in reader if r.get('email_status') in ('valid', 'catch_all')]

with open(dst, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(leads)

print(f"Clean file: {len(leads)} sendable leads")
```

---

## Step 7: Write Email Sequences

### Formula (from Nick Saraev's Maker School)
```
Personalization ({{icebreaker}}) → Who am I → Why trust me → Offer → CTA
```

### Key Insights (from Sav/Nate Herk $500K strategy)

**Subject lines:**
- Keep them short and personal: `{{firstName}}, question` or `{{firstName}}?`
- "Q from your neighbor" style creates curiosity
- Never use salesy subject lines

**CTA strategy — Sell the Video, Not the Call:**
- Instead of asking for a call directly, offer to send a short Loom video
- "Can I send you a 90-second video showing how it works?"
- Much lower friction than booking a call
- Use Loom to record 90-second to 2-minute value videos per niche

**Risk reversal language:**
- "You wouldn't owe me anything unless it actually drives results"
- "No cost, no strings"
- "Worst case you walk away with a clear action plan"

**Structure:**
- Email 1: Icebreaker → Credibility → Offer → Soft CTA
- Email 2: Follow-up (3 days later) — shorter, bullet points, same offer

**Tone rules:**
- Sign off with "Sent from my iPhone" (looks personal)
- No HTML, no images, no links — plain text only
- Short paragraphs (2-3 lines max)
- Casual, like texting a colleague

### Files
- Sequence templates: `docs/coldemails/6 Cold Email Sequences.md`
- Sequence writing guide: `docs/coldemails/3. Write six cold email sequences.pdf`

---

## Step 8: Launch on Instantly

### Domain/Inbox Setup
- Use 3 domains with 5 inboxes each = 15 sending accounts
- Each inbox sends ~30 emails/day
- Total capacity: ~450 emails/day across all inboxes
- Warm up all inboxes for 2+ weeks before sending

### Campaign Setup
1. Create one campaign per sequence (A/B test two offers per niche)
2. Upload clean CSV
3. Map variables: `{{firstName}}`, `{{companyName}}` (use `shortenedCompanyName` column), `{{icebreaker}}`
4. Set follow-up delay: 3 days
5. Schedule: Monday–Saturday, 7:00am–7:00pm ET
6. Start at 25 emails/day per inbox, ramp up gradually

### Monitoring
- Target: <3% bounce rate (if higher, stop and re-verify)
- Target: >1% reply rate
- After ~300 sends, compare A vs B offers — kill the loser
- Winner with >2% reply rate → add a 3rd follow-up email

---

## Dependencies & Setup

### Python Environment (scripts/)
```bash
cd scripts
uv init  # if not already done
uv add google-genai dnspython pysocks
```

### API Keys & Credentials
| Service | Key Location | Purpose |
|---------|-------------|---------|
| Gemini API | env var `GEMINI_API_KEY` | Icebreakers + company name shortening |
| MillionVerifier | hardcoded in `verify_via_millionverifier.py` | Email verification for ip_blocked |

### File Structure
```
docs/coldemails/
├── 6 Offers.md                  # Offer templates per niche
├── 6 Cold Email Sequences.md    # Email copy per niche
├── Cold Email Campaign Playbook.md  # This file (reusable process)
├── Icebreaker Generation Guide.md   # Detailed icebreaker guide
├── How to write offer.md            # Offer writing framework
├── 3. Write six cold email sequences.pdf  # Sequence writing guide
├── credentials/                     # SSH keys, etc.
└── Leads/
    ├── YYYY-MM-DD-apollo-*.csv                    # Raw Apollo exports
    ├── *-with-icebreakers.csv                     # After icebreaker generation
    └── *-CLEAN.csv                                # Final sendable leads

scripts/
├── generate_icebreakers.py      # Step 3: Gemini icebreakers
├── shorten_company_names.py     # Step 4: Gemini company name shortening
├── verify_emails.py             # Step 5a: Local SMTP verification
├── verify_via_millionverifier.py # Step 5b: MV API for ip_blocked
└── pyproject.toml               # uv project config
```

---

## Checklist: New Campaign Launch

- [ ] Niche selected with clear "why" (personal experience/proof)
- [ ] 2 offers written (A: free build, B: free audit)
- [ ] Leads scraped from Apollo (or niche directory + Apollo enrichment)
- [ ] Icebreakers generated via Gemini
- [ ] Company names shortened via Gemini
- [ ] Emails verified (local SMTP + MillionVerifier for ip_blocked)
- [ ] Clean CSV created (only valid + catch_all leads)
- [ ] 2 email sequences written (A/B test the two offers)
- [ ] Domains/inboxes warmed up (2+ weeks)
- [ ] Campaign created in Instantly with correct variable mapping
- [ ] Sending at 25/day per inbox
- [ ] Monitoring bounce rate (<3%) and reply rate (>1%)

---

## Lessons Learned

1. **Always verify emails before sending.** 16% bounce rate on unverified leads will destroy sender reputation.
2. **Residential IPs are often on Spamhaus.** Budget for MillionVerifier (~$3/500 emails) for Outlook-hosted domains.
3. **Cloud VMs (GCP, AWS, Oracle) all block outbound port 25.** Don't waste time trying to use them for SMTP verification.
4. **Consumer VPNs (WARP, ProtonVPN) also block port 25.** This is universal anti-spam policy.
5. **Free SOCKS5 proxies are also on Spamhaus.** Their IPs are dirty.
6. **Save progress every 50 leads** in all scripts to avoid losing work on interruption.
7. **Gemini model: use `gemini-3-flash-preview`** — cheap and up-to-date. Don't use older models.
8. **Python env: always use `uv`** as virtual environment manager. Never install globally.
