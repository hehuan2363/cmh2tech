"""
Email verification script — checks if email addresses are deliverable.

Three-layer verification:
1. Syntax check (regex)
2. MX record lookup (does the domain have a mail server?)
3. SMTP RCPT TO probe via raw sockets (does the mailbox exist?)

Handles Spamhaus/IP blocks by marking them separately from real rejections.
Saves progress every 50 leads. Resumable. Adds 'email_status' column to CSV.

Statuses:
  valid        — server confirmed mailbox exists
  catch_all    — server accepts any email (can't verify individual addresses)
  rejected     — server says mailbox doesn't exist (bad email, remove it)
  invalid_syntax — not a valid email format (remove it)
  no_mx        — domain has no mail server (remove it)
  no_email     — no email in the lead data
  ip_blocked   — our IP is blocked by the server (can't verify, needs VPN/service)
  timeout      — server didn't respond in time
  unknown      — couldn't determine status
"""

import csv
import os
import re
import socket
import time
import sys
import dns.resolver

# --------------- Config ---------------
SAVE_EVERY = 50
SMTP_TIMEOUT = 10
DELAY_BETWEEN = 0.3
DELAY_BETWEEN_DOMAINS = 1.0
EHLO_DOMAIN = "cmh2.tech"
SENDER_EMAIL = "verify@cmh2.tech"

# Cache per domain
mx_cache: dict[str, list[str]] = {}
catchall_cache: dict[str, bool] = {}
domain_blocked_cache: dict[str, bool] = {}


def is_valid_syntax(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def get_mx_hosts(domain: str) -> list[str]:
    if domain in mx_cache:
        return mx_cache[domain]
    try:
        records = dns.resolver.resolve(domain, 'MX')
        hosts = sorted(records, key=lambda r: r.preference)
        result = [str(r.exchange).rstrip('.') for r in hosts]
        mx_cache[domain] = result
        return result
    except Exception:
        mx_cache[domain] = []
        return []


def smtp_raw_check(email: str, mx_hosts: list[str]) -> str:
    """
    Raw socket SMTP verification. Returns status string.
    """
    for mx_host in mx_hosts[:2]:
        sock = None
        try:
            sock = socket.create_connection((mx_host, 25), timeout=SMTP_TIMEOUT)
            banner = sock.recv(1024).decode('utf-8', errors='replace')

            if not banner.startswith('220'):
                continue

            # EHLO
            sock.send(f"EHLO {EHLO_DOMAIN}\r\n".encode())
            resp = sock.recv(4096).decode('utf-8', errors='replace')

            if not resp.startswith('250'):
                continue

            # MAIL FROM
            sock.send(f"MAIL FROM:<{SENDER_EMAIL}>\r\n".encode())
            resp = sock.recv(1024).decode('utf-8', errors='replace')

            if not resp.startswith('250'):
                # Some servers reject our sender — try empty sender
                sock.send(b"RSET\r\n")
                sock.recv(1024)
                sock.send(b"MAIL FROM:<>\r\n")
                resp = sock.recv(1024).decode('utf-8', errors='replace')
                if not resp.startswith('250'):
                    continue

            # RCPT TO — this is the actual check
            sock.send(f"RCPT TO:<{email}>\r\n".encode())
            resp = sock.recv(1024).decode('utf-8', errors='replace')

            # QUIT
            try:
                sock.send(b"QUIT\r\n")
                sock.recv(1024)
            except Exception:
                pass

            code = resp[:3] if len(resp) >= 3 else "000"
            resp_lower = resp.lower()

            # Parse the response
            if code == "250":
                return "valid"
            elif code in ("550", "551", "553", "554"):
                # Check if it's an IP block or a real rejection
                if any(kw in resp_lower for kw in [
                    "spamhaus", "blocked", "blacklist", "blocklist",
                    "denied", "not allowed", "rejected by policy",
                    "client host", "access denied", "service unavailable"
                ]) and "mailbox" not in resp_lower and "user" not in resp_lower:
                    return "ip_blocked"
                else:
                    return "rejected"
            elif code == "452":
                return "unknown"  # Mailbox full or rate limited
            elif code == "421":
                return "ip_blocked"  # Usually connection rate limit
            else:
                return "unknown"

        except socket.timeout:
            return "timeout"
        except ConnectionRefusedError:
            continue
        except OSError:
            continue
        except Exception as e:
            print(f"    Error: {e}")
            continue
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    return "unknown"


def check_catch_all(domain: str, mx_hosts: list[str]) -> bool:
    """Check if domain accepts any random email (catch-all)."""
    if domain in catchall_cache:
        return catchall_cache[domain]

    fake = f"zxqv9k7j3m_nonexist_{int(time.time())}@{domain}"
    result = smtp_raw_check(fake, mx_hosts)
    is_ca = (result == "valid")
    catchall_cache[domain] = is_ca
    return is_ca


def verify_email(email: str) -> str:
    email = email.strip().lower()

    if not is_valid_syntax(email):
        return "invalid_syntax"

    domain = email.split('@')[1]

    mx_hosts = get_mx_hosts(domain)
    if not mx_hosts:
        return "no_mx"

    # If we already know this domain blocks our IP, skip SMTP
    if domain_blocked_cache.get(domain):
        return "ip_blocked"

    result = smtp_raw_check(email, mx_hosts)

    # Cache domain-level IP blocks
    if result == "ip_blocked":
        domain_blocked_cache[domain] = True

    # Check for catch-all if valid
    if result == "valid":
        if check_catch_all(domain, mx_hosts):
            return "catch_all"

    return result


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

    if "email_status" not in fieldnames:
        fieldnames.append("email_status")

    total = len(leads)
    already_done = sum(1 for r in leads if r.get("email_status", "").strip())
    print(f"Found {total} leads ({already_done} already verified)")

    processed = 0
    last_domain = ""
    stats = {}

    for i, lead in enumerate(leads):
        if lead.get("email_status", "").strip():
            s = lead["email_status"]
            stats[s] = stats.get(s, 0) + 1
            continue

        email = lead.get("email", "").strip()
        if not email:
            lead["email_status"] = "no_email"
            stats["no_email"] = stats.get("no_email", 0) + 1
            processed += 1
            print(f"  [{i+1}/{total}] --  no_email       — (no email in lead)")
            continue

        domain = email.split('@')[-1] if '@' in email else ""
        if domain != last_domain and last_domain:
            time.sleep(DELAY_BETWEEN_DOMAINS)
        last_domain = domain

        status = verify_email(email)
        lead["email_status"] = status
        stats[status] = stats.get(status, 0) + 1
        processed += 1

        icons = {
            "valid": "OK", "catch_all": "CA", "rejected": "XX",
            "no_mx": "XX", "invalid_syntax": "XX", "ip_blocked": "BL",
            "unknown": "??", "timeout": "TO", "no_email": "--"
        }
        icon = icons.get(status, "??")
        print(f"  [{i+1}/{total}] {icon}  {status:15s} — {email}")

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved ({processed} verified) ---")

        time.sleep(DELAY_BETWEEN)

    save_csv(leads, fieldnames, filepath)

    print(f"\n{'='*60}")
    print(f"Results for {filename}:")
    print(f"{'='*60}")
    for status, count in sorted(stats.items(), key=lambda x: -x[1]):
        if count > 0:
            pct = count / total * 100
            bar = "#" * int(pct / 2)
            print(f"  {status:15s}: {count:>4} ({pct:5.1f}%) {bar}")
    print(f"  {'TOTAL':15s}: {total:>4}")

    safe = stats.get("valid", 0)
    risky = stats.get("catch_all", 0)
    bad = stats.get("rejected", 0) + stats.get("no_mx", 0) + stats.get("invalid_syntax", 0) + stats.get("no_email", 0)
    blocked = stats.get("ip_blocked", 0)
    print(f"\n  SAFE to send:  {safe} (valid)")
    print(f"  RISKY:         {risky} (catch-all — usually ~60% deliverable)")
    print(f"  REMOVE:        {bad} (rejected/no_mx/invalid/no_email)")
    print(f"  UNVERIFIABLE:  {blocked} (IP blocked — need VPN or paid service)")
    print(f"\nSaved to: {filepath}")


def main():
    leads_dir = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"
    files = [
        os.path.join(leads_dir, "2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv"),
        os.path.join(leads_dir, "2026-02-12-apollo-Accounting-2-100-employees-with-icebreakers.csv"),
    ]

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue
        process_file(filepath)

    print(f"\n{'='*60}")
    print("ALL DONE")
    print(f"{'='*60}")
    print("\nACTION ITEMS:")
    print("  1. Remove all 'rejected', 'no_mx', 'invalid_syntax' leads — these WILL bounce")
    print("  2. 'valid' leads are safe to send")
    print("  3. 'catch_all' leads are risky (~60% deliverable) — send but monitor bounces")
    print("  4. 'ip_blocked' leads couldn't be verified from your IP")
    print("     → Re-run with a VPN, or use MillionVerifier ($3/1K emails) for these")
    print("  5. 'unknown'/'timeout' — re-run later or use a paid service")


if __name__ == "__main__":
    main()
