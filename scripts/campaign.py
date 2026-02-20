#!/usr/bin/env python3
"""
Cold Email Campaign CLI — CMH2.tech

Single entry point for the entire cold email pipeline.

Usage:
  campaign.py check                         Check prerequisites
  campaign.py icebreakers --file FILE       Generate icebreakers
  campaign.py shorten --file FILE           Shorten company names
  campaign.py verify --file FILE            SMTP email verification
  campaign.py verify-mv --file FILE         MillionVerifier for ip_blocked
  campaign.py clean --file FILE             Create clean CSV
  campaign.py run --file FILE               Full pipeline (all steps)
  campaign.py stats --file FILE             Show verification stats

Environment variables:
  GEMINI_API_KEY    Gemini API key (for icebreakers + company name shortening)
  MV_API_KEY        MillionVerifier API key (for ip_blocked email verification)
"""
import argparse
import os
import sys

# Add scripts dir to path so config.py and lib/ are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def cmd_check(args):
    """Check all prerequisites."""
    from config import GEMINI_API_KEY, MV_API_KEY, LEADS_DIR

    print("Checking prerequisites...\n")
    ok = True

    # Check API keys
    if GEMINI_API_KEY:
        print(f"  GEMINI_API_KEY: set ({GEMINI_API_KEY[:8]}...)")
    else:
        print("  GEMINI_API_KEY: NOT SET — needed for icebreakers and company names")
        ok = False

    if MV_API_KEY:
        print(f"  MV_API_KEY:     set ({MV_API_KEY[:8]}...)")
    else:
        print("  MV_API_KEY:     not set — needed only for ip_blocked verification")

    # Check dependencies
    try:
        import dns.resolver
        print("  dnspython:      installed")
    except ImportError:
        print("  dnspython:      NOT INSTALLED — run: uv add dnspython")
        ok = False

    try:
        from google import genai
        print("  google-genai:   installed")
    except ImportError:
        print("  google-genai:   NOT INSTALLED — run: uv add google-genai")
        ok = False

    # Check leads directory
    leads_dir = os.path.abspath(LEADS_DIR)
    if os.path.isdir(leads_dir):
        csvs = [f for f in os.listdir(leads_dir) if f.endswith(".csv")]
        print(f"  Leads dir:      {leads_dir} ({len(csvs)} CSV files)")
    else:
        print(f"  Leads dir:      NOT FOUND at {leads_dir}")

    print(f"\n{'All good!' if ok else 'Fix the issues above before proceeding.'}")


def cmd_icebreakers(args):
    """Generate icebreakers."""
    from lib.icebreakers import process
    process(args.file)


def cmd_shorten(args):
    """Shorten company names."""
    from lib.shorten import process
    process(args.file)


def cmd_verify(args):
    """SMTP email verification."""
    from lib.verify_smtp import process
    process(args.file)


def cmd_verify_mv(args):
    """MillionVerifier verification for ip_blocked leads."""
    from lib.verify_mv import process
    process(args.file, api_key=getattr(args, 'mv_key', ''))


def cmd_clean(args):
    """Create clean CSV."""
    from lib.clean import process
    process(args.file)


def cmd_stats(args):
    """Show verification statistics."""
    import csv
    filepath = args.file
    filename = os.path.basename(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads = list(reader)

    total = len(leads)
    stats = {}
    for lead in leads:
        s = lead.get("email_status", "(not verified)")
        stats[s] = stats.get(s, 0) + 1

    has_icebreaker = sum(1 for r in leads if r.get("icebreaker", "").strip() and r["icebreaker"] != "SKIP")
    has_shortened = sum(1 for r in leads if r.get("shortenedCompanyName", "").strip())

    print(f"\n{'='*60}")
    print(f"Stats: {filename}")
    print(f"{'='*60}")
    print(f"  Total leads:          {total}")
    print(f"  With icebreaker:      {has_icebreaker}")
    print(f"  With shortened name:  {has_shortened}")
    print(f"\n  Email verification:")
    for s, c in sorted(stats.items(), key=lambda x: -x[1]):
        pct = c / total * 100
        print(f"    {s:20s}: {c:>4} ({pct:5.1f}%)")

    valid = stats.get("valid", 0)
    catch_all = stats.get("catch_all", 0)
    bad = stats.get("rejected", 0) + stats.get("no_mx", 0) + stats.get("no_email", 0) + stats.get("invalid_syntax", 0)
    blocked = stats.get("ip_blocked", 0)
    print(f"\n  SENDABLE:    {valid + catch_all} (valid: {valid}, catch_all: {catch_all})")
    print(f"  REMOVE:      {bad}")
    if blocked:
        print(f"  IP BLOCKED:  {blocked} — run 'campaign.py verify-mv' to verify these")


def cmd_run(args):
    """Run full pipeline."""
    filepath = args.file
    print(f"Running full pipeline on: {os.path.basename(filepath)}")
    print(f"{'='*60}\n")

    # Step 1: Icebreakers
    from lib.icebreakers import process as gen_icebreakers
    icebreaker_file = gen_icebreakers(filepath)

    # Step 2: Shorten company names
    from lib.shorten import process as shorten_names
    shorten_names(icebreaker_file)

    # Step 3: SMTP verification
    from lib.verify_smtp import process as verify_smtp
    verify_smtp(icebreaker_file)

    # Step 4: MillionVerifier for ip_blocked
    from config import MV_API_KEY
    if MV_API_KEY:
        from lib.verify_mv import process as verify_mv
        verify_mv(icebreaker_file)
    else:
        import csv
        with open(icebreaker_file, "r") as f:
            blocked = sum(1 for r in csv.DictReader(f) if r.get("email_status") == "ip_blocked")
        if blocked:
            print(f"\n  {blocked} leads are ip_blocked. Set MV_API_KEY to verify these via MillionVerifier.")

    # Step 5: Clean
    from lib.clean import process as clean_csv
    clean_file = clean_csv(icebreaker_file)

    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Clean file ready for Instantly: {os.path.basename(clean_file)}")


def main():
    parser = argparse.ArgumentParser(
        description="Cold Email Campaign CLI — CMH2.tech",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # check
    subparsers.add_parser("check", help="Check prerequisites")

    # icebreakers
    p = subparsers.add_parser("icebreakers", help="Generate icebreakers")
    p.add_argument("--file", required=True, help="Path to CSV file")

    # shorten
    p = subparsers.add_parser("shorten", help="Shorten company names")
    p.add_argument("--file", required=True, help="Path to CSV file")

    # verify
    p = subparsers.add_parser("verify", help="SMTP email verification")
    p.add_argument("--file", required=True, help="Path to CSV file")

    # verify-mv
    p = subparsers.add_parser("verify-mv", help="MillionVerifier for ip_blocked")
    p.add_argument("--file", required=True, help="Path to CSV file")
    p.add_argument("--mv-key", default="", help="MillionVerifier API key (or set MV_API_KEY env var)")

    # clean
    p = subparsers.add_parser("clean", help="Create clean CSV")
    p.add_argument("--file", required=True, help="Path to CSV file")

    # stats
    p = subparsers.add_parser("stats", help="Show verification stats")
    p.add_argument("--file", required=True, help="Path to CSV file")

    # run
    p = subparsers.add_parser("run", help="Full pipeline (all steps)")
    p.add_argument("--file", required=True, help="Path to raw CSV file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "check": cmd_check,
        "icebreakers": cmd_icebreakers,
        "shorten": cmd_shorten,
        "verify": cmd_verify,
        "verify-mv": cmd_verify_mv,
        "clean": cmd_clean,
        "stats": cmd_stats,
        "run": cmd_run,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
