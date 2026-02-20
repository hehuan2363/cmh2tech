"""Local SMTP email verification via raw sockets."""
import csv
import os
import re
import socket
import time
import dns.resolver
from config import SMTP_TIMEOUT, EHLO_DOMAIN, SENDER_EMAIL, SAVE_EVERY, DELAY_BETWEEN, DELAY_BETWEEN_DOMAINS

mx_cache: dict[str, list[str]] = {}
catchall_cache: dict[str, bool] = {}
domain_blocked_cache: dict[str, bool] = {}


def is_valid_syntax(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email.strip()))


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
    for mx_host in mx_hosts[:2]:
        sock = None
        try:
            sock = socket.create_connection((mx_host, 25), timeout=SMTP_TIMEOUT)
            banner = sock.recv(1024).decode('utf-8', errors='replace')
            if not banner.startswith('220'):
                continue

            sock.send(f"EHLO {EHLO_DOMAIN}\r\n".encode())
            resp = sock.recv(4096).decode('utf-8', errors='replace')
            if not resp.startswith('250'):
                continue

            sock.send(f"MAIL FROM:<{SENDER_EMAIL}>\r\n".encode())
            resp = sock.recv(1024).decode('utf-8', errors='replace')
            if not resp.startswith('250'):
                sock.send(b"RSET\r\n")
                sock.recv(1024)
                sock.send(b"MAIL FROM:<>\r\n")
                resp = sock.recv(1024).decode('utf-8', errors='replace')
                if not resp.startswith('250'):
                    continue

            sock.send(f"RCPT TO:<{email}>\r\n".encode())
            resp = sock.recv(1024).decode('utf-8', errors='replace')

            try:
                sock.send(b"QUIT\r\n")
                sock.recv(1024)
            except Exception:
                pass

            code = resp[:3] if len(resp) >= 3 else "000"
            resp_lower = resp.lower()

            if code == "250":
                return "valid"
            elif code in ("550", "551", "553", "554"):
                if any(kw in resp_lower for kw in [
                    "spamhaus", "blocked", "blacklist", "blocklist",
                    "denied", "not allowed", "rejected by policy",
                    "client host", "access denied", "service unavailable"
                ]) and "mailbox" not in resp_lower and "user" not in resp_lower:
                    return "ip_blocked"
                else:
                    return "rejected"
            elif code == "452":
                return "unknown"
            elif code == "421":
                return "ip_blocked"
            else:
                return "unknown"

        except socket.timeout:
            return "timeout"
        except ConnectionRefusedError:
            continue
        except OSError:
            continue
        except Exception:
            continue
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    return "unknown"


def check_catch_all(domain: str, mx_hosts: list[str]) -> bool:
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
    if domain_blocked_cache.get(domain):
        return "ip_blocked"

    result = smtp_raw_check(email, mx_hosts)
    if result == "ip_blocked":
        domain_blocked_cache[domain] = True
    if result == "valid":
        if check_catch_all(domain, mx_hosts):
            return "catch_all"
    return result


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process(filepath: str):
    """Run SMTP verification on a CSV file."""
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"SMTP Verification: {filename}")
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

    print(f"\nResults:")
    for status, count in sorted(stats.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {status:15s}: {count:>4} ({pct:5.1f}%)")
    print(f"  {'TOTAL':15s}: {total:>4}")

    blocked = stats.get("ip_blocked", 0)
    if blocked > 0:
        print(f"\n  {blocked} leads are ip_blocked — run 'campaign.py verify-mv' to verify these via MillionVerifier")
