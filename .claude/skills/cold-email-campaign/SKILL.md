---
name: cold-email-campaign
description: Run the full cold email campaign pipeline — from lead sourcing to verified clean CSV ready for Instantly. Use when the user wants to launch a new cold email campaign, verify emails, generate icebreakers, or create clean lead lists.
argument-hint: [niche-name or "all"]
---

# Cold Email Campaign Pipeline

You are running the cold email campaign pipeline for CMH2.tech. This is a multi-step process that takes raw Apollo leads and produces a clean, verified CSV ready to import into Instantly.

## Arguments
- `$ARGUMENTS` — optional niche name (e.g., "accounting", "engineering", "property-management") or "all" to process everything. If no argument, ask the user what they want to do.

## Config
- **Gemini API key:** Set via `GEMINI_API_KEY` env var
- **MillionVerifier API key:** Set via `MV_API_KEY` env var or update in `scripts/campaign.py`
- **Leads directory:** `docs/coldemails/Leads/`
- **Scripts directory:** `scripts/`
- **Python env:** Always use `uv` — never install packages globally

## Pipeline Steps

Run these in order. Each step is idempotent and resumable.

### Step 1: Check Prerequisites
```bash
cd scripts && uv run python campaign.py check
```
Verify API keys are set, dependencies installed, and input files exist.

### Step 2: Generate Icebreakers
```bash
cd scripts && uv run python campaign.py icebreakers --file "path/to/leads.csv"
```
- Uses Gemini API (`gemini-3-flash-preview`)
- Adds `icebreaker` column
- Saves as `*-with-icebreakers.csv`
- Saves progress every 50 leads (resumable)

### Step 3: Shorten Company Names
```bash
cd scripts && uv run python campaign.py shorten --file "path/to/leads-with-icebreakers.csv"
```
- Adds `shortenedCompanyName` column
- Used as `{{companyName}}` variable in email sequences

### Step 4: Verify Emails
```bash
cd scripts && uv run python campaign.py verify --file "path/to/leads-with-icebreakers.csv"
```
- Layer 1: Local SMTP check (free, catches ~40% of bad emails)
- Layer 2: MillionVerifier API for `ip_blocked` leads (~$3/500 emails)
- Adds `email_status` column

### Step 5: Create Clean CSV
```bash
cd scripts && uv run python campaign.py clean --file "path/to/leads-with-icebreakers.csv"
```
- Removes all non-sendable leads (rejected, no_mx, invalid, no_email)
- Keeps only `valid` and `catch_all`
- Creates `*-CLEAN.csv`

### Step 6: Full Pipeline (all steps at once)
```bash
cd scripts && uv run python campaign.py run --file "path/to/leads.csv"
```
Runs steps 2-5 in sequence.

## Important Notes
- **Residential IPs are often on Spamhaus.** Outlook/Microsoft domains will return `ip_blocked`. Always budget for MillionVerifier.
- **Cloud VMs (GCP, AWS, Oracle) block outbound port 25.** Don't try SMTP verification from cloud machines.
- **All consumer VPNs block port 25.** Don't waste time with WARP, ProtonVPN, etc.
- **Target <3% bounce rate.** If higher, stop the campaign immediately and re-verify.
- **Save progress every 50 leads** to avoid losing work on interruption.
- **Always verify before sending.** Never send to unverified leads.

## File Structure Reference
```
docs/coldemails/
├── Leads/
│   ├── *.csv                      # Raw Apollo exports
│   ├── *-with-icebreakers.csv     # After icebreaker generation
│   └── *-CLEAN.csv                # Final sendable leads
├── 6 Offers.md                    # Offer templates
├── 6 Cold Email Sequences.md      # Email copy
└── Cold Email Campaign Playbook.md # Full process documentation

scripts/
├── campaign.py                    # Main CLI entry point
├── config.py                      # Configuration
├── lib/
│   ├── icebreakers.py            # Icebreaker generation
│   ├── shorten.py                # Company name shortening
│   ├── verify_smtp.py            # Local SMTP verification
│   ├── verify_mv.py              # MillionVerifier API
│   └── clean.py                  # CSV cleaning
└── pyproject.toml
```

## Playbook Reference
Full documentation: `docs/coldemails/Cold Email Campaign Playbook.md`
