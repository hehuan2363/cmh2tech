# CMH2.tech — AI Automation Consulting

## Project Structure
- `scripts/` — Python campaign automation tools (use `uv` for virtual env)
- `docs/coldemails/` — Cold email campaign docs, offers, sequences, leads
- `.claude/skills/cold-email-campaign/` — Reusable cold email campaign skill

## Cold Email Campaign
Use `/cold-email-campaign` to run the full pipeline, or run individual steps:

```bash
cd scripts
uv run python campaign.py check                    # Verify setup
uv run python campaign.py run --file path/to.csv   # Full pipeline
uv run python campaign.py stats --file path/to.csv # View stats
```

### Required Environment Variables
```bash
export GEMINI_API_KEY="your-gemini-key"  # For icebreakers + company names
export MV_API_KEY="your-mv-key"          # For MillionVerifier (ip_blocked emails)
```

## Rules
- Always use `uv` as virtual env manager — never `pip install` globally
- Use Gemini model `gemini-3-flash-preview` — not older models
- Don't ask for permission on routine tasks — just execute
- Save progress every 50 leads in all long-running scripts
