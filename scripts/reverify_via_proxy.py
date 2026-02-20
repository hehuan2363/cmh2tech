"""
Re-verify ip_blocked emails using SOCKS5 proxies.

Reads CSVs, finds rows with email_status='ip_blocked', and re-checks
them through working SOCKS5 proxies that can reach SMTP port 25.
"""

import csv
import os
import re
import time
import sys
import socks
import socket
import dns.resolver

# --------------- Config ---------------
SAVE_EVERY = 50
SMTP_TIMEOUT = 15
DELAY_BETWEEN = 0.5
DELAY_BETWEEN_DOMAINS = 1.0
EHLO_DOMAIN = "cmh2.tech"
SENDER_EMAIL = "verify@cmh2.tech"

PROXIES = [
    ("123.54.197.49", 20498),
    ("123.54.197.52", 22840),
]
current_proxy_idx = 0

# Cache per domain
mx_cache: dict[str, list[str]] = {}
catchall_cache: dict[str, bool] = {}


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


def smtp_check_via_proxy(email: str, mx_hosts: list[str]) -> str:
    """SMTP verification through SOCKS5 proxy. Tries both proxies."""
    global current_proxy_idx

    for mx_host in mx_hosts[:2]:
        # Try each proxy
        for attempt in range(len(PROXIES)):
            proxy_host, proxy_port = PROXIES[current_proxy_idx]
            sock = None
            try:
                sock = socks.socksocket()
                sock.set_proxy(socks.SOCKS5, proxy_host, proxy_port)
                sock.settimeout(SMTP_TIMEOUT)
                sock.connect((mx_host, 25))

                banner = sock.recv(1024).decode('utf-8', errors='replace')
                if not banner.startswith('220'):
                    sock.close()
                    continue

                # EHLO
                sock.send(f"EHLO {EHLO_DOMAIN}\r\n".encode())
                resp = sock.recv(4096).decode('utf-8', errors='replace')
                if not resp.startswith('250'):
                    sock.close()
                    continue

                # MAIL FROM
                sock.send(f"MAIL FROM:<{SENDER_EMAIL}>\r\n".encode())
                resp = sock.recv(1024).decode('utf-8', errors='replace')
                if not resp.startswith('250'):
                    sock.send(b"RSET\r\n")
                    sock.recv(1024)
                    sock.send(b"MAIL FROM:<>\r\n")
                    resp = sock.recv(1024).decode('utf-8', errors='replace')
                    if not resp.startswith('250'):
                        sock.close()
                        continue

                # RCPT TO
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

                if code == "250":
                    return "valid"
                elif code in ("550", "551", "553", "554"):
                    if any(kw in resp_lower for kw in [
                        "spamhaus", "blocked", "blacklist", "blocklist",
                        "denied", "not allowed", "rejected by policy",
                        "client host", "access denied", "service unavailable"
                    ]) and "mailbox" not in resp_lower and "user" not in resp_lower:
                        # Proxy IP also blocked — try next proxy
                        current_proxy_idx = (current_proxy_idx + 1) % len(PROXIES)
                        continue
                    else:
                        return "rejected"
                elif code == "452":
                    return "unknown"
                elif code == "421":
                    # Rate limited — rotate proxy and retry
                    current_proxy_idx = (current_proxy_idx + 1) % len(PROXIES)
                    time.sleep(2)
                    continue
                else:
                    return "unknown"

            except (socket.timeout, socks.ProxyConnectionError, socks.GeneralProxyError):
                # Proxy failed — try next one
                current_proxy_idx = (current_proxy_idx + 1) % len(PROXIES)
                continue
            except ConnectionRefusedError:
                continue
            except OSError:
                continue
            except Exception as e:
                print(f"    Proxy error: {e}")
                current_proxy_idx = (current_proxy_idx + 1) % len(PROXIES)
                continue
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

    return "unknown"


def check_catch_all_via_proxy(domain: str, mx_hosts: list[str]) -> bool:
    """Check if domain is catch-all via proxy."""
    if domain in catchall_cache:
        return catchall_cache[domain]
    fake = f"zxqv9k7j3m_nonexist_{int(time.time())}@{domain}"
    result = smtp_check_via_proxy(fake, mx_hosts)
    is_ca = (result == "valid")
    catchall_cache[domain] = is_ca
    return is_ca


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process_file(filepath: str):
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Re-verifying ip_blocked leads: {filename}")
    print(f"{'='*60}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    total = len(leads)
    blocked = [i for i, r in enumerate(leads) if r.get("email_status", "").strip() == "ip_blocked"]
    print(f"Found {len(blocked)} ip_blocked leads out of {total} total")

    if not blocked:
        print("Nothing to re-verify!")
        return

    processed = 0
    last_domain = ""
    stats = {}

    for idx in blocked:
        lead = leads[idx]
        email = lead.get("email", "").strip()
        if not email:
            continue

        domain = email.split('@')[-1] if '@' in email else ""
        if domain != last_domain and last_domain:
            time.sleep(DELAY_BETWEEN_DOMAINS)
        last_domain = domain

        mx_hosts = get_mx_hosts(domain)
        if not mx_hosts:
            lead["email_status"] = "no_mx"
            stats["no_mx"] = stats.get("no_mx", 0) + 1
            processed += 1
            print(f"  [{processed}/{len(blocked)}] XX  no_mx          — {email}")
            continue

        result = smtp_check_via_proxy(email, mx_hosts)

        # Check for catch-all if valid
        if result == "valid":
            if check_catch_all_via_proxy(domain, mx_hosts):
                result = "catch_all"

        lead["email_status"] = result
        stats[result] = stats.get(result, 0) + 1
        processed += 1

        icons = {
            "valid": "OK", "catch_all": "CA", "rejected": "XX",
            "no_mx": "XX", "unknown": "??", "timeout": "TO"
        }
        icon = icons.get(result, "??")
        print(f"  [{processed}/{len(blocked)}] {icon}  {result:15s} — {email}")

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved ({processed} re-verified) ---")

        time.sleep(DELAY_BETWEEN)

    save_csv(leads, fieldnames, filepath)

    print(f"\n{'='*60}")
    print(f"Re-verification results for {filename}:")
    print(f"{'='*60}")
    for status, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {status:15s}: {count:>4}")
    print(f"  {'TOTAL':15s}: {len(blocked):>4}")

    # Show overall file stats
    overall = {}
    for lead in leads:
        s = lead.get("email_status", "unknown")
        overall[s] = overall.get(s, 0) + 1
    print(f"\nOverall file stats after re-verification:")
    for status, count in sorted(overall.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"  {status:15s}: {count:>4} ({pct:5.1f}%)")


def main():
    leads_dir = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"
    files = [
        os.path.join(leads_dir, "2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv"),
        os.path.join(leads_dir, "2026-02-12-apollo-Accounting-2-100-employees-with-icebreakers.csv"),
    ]

    print(f"Using SOCKS5 proxies:")
    for h, p in PROXIES:
        print(f"  {h}:{p}")

    for filepath in files:
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            continue
        process_file(filepath)

    print(f"\n{'='*60}")
    print("RE-VERIFICATION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
