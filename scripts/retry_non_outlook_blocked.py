"""
Retry ip_blocked emails that are NOT on Outlook/Microsoft mail servers.
These may have been rate-limited earlier rather than permanently blocked.
"""

import csv
import os
import socket
import time
import dns.resolver

SMTP_TIMEOUT = 10
DELAY_BETWEEN = 0.5
DELAY_BETWEEN_DOMAINS = 1.5
EHLO_DOMAIN = "cmh2.tech"
SENDER_EMAIL = "verify@cmh2.tech"
SAVE_EVERY = 25

mx_cache = {}
catchall_cache = {}


def get_mx_hosts(domain):
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


def is_outlook(mx_hosts):
    for h in mx_hosts:
        h = h.lower()
        if 'outlook' in h or 'microsoft' in h or 'office365' in h:
            return True
    return False


def smtp_check(email, mx_hosts):
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
            except:
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
        except Exception as e:
            print(f"    Error: {e}")
            continue
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
    return "unknown"


def check_catch_all(domain, mx_hosts):
    if domain in catchall_cache:
        return catchall_cache[domain]
    fake = f"zxqv9k7j3m_nonexist_{int(time.time())}@{domain}"
    result = smtp_check(fake, mx_hosts)
    is_ca = (result == "valid")
    catchall_cache[domain] = is_ca
    return is_ca


def save_csv(leads, fieldnames, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(leads)


def process_file(filepath):
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Retrying non-Outlook ip_blocked: {filename}")
    print(f"{'='*60}")

    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        leads = list(reader)

    # Find ip_blocked leads with non-Outlook MX
    retry_indices = []
    outlook_count = 0
    for i, lead in enumerate(leads):
        if lead.get("email_status", "").strip() != "ip_blocked":
            continue
        email = lead.get("email", "").strip()
        if not email or '@' not in email:
            continue
        domain = email.split('@')[1]
        mx_hosts = get_mx_hosts(domain)
        if is_outlook(mx_hosts):
            outlook_count += 1
        elif mx_hosts:
            retry_indices.append(i)

    print(f"  Outlook (skipping): {outlook_count}")
    print(f"  Non-Outlook (retrying): {len(retry_indices)}")

    if not retry_indices:
        print("  Nothing to retry!")
        return

    processed = 0
    stats = {}
    last_domain = ""

    for idx in retry_indices:
        lead = leads[idx]
        email = lead.get("email", "").strip()
        domain = email.split('@')[1]

        if domain != last_domain and last_domain:
            time.sleep(DELAY_BETWEEN_DOMAINS)
        last_domain = domain

        mx_hosts = get_mx_hosts(domain)
        result = smtp_check(email, mx_hosts)

        if result == "valid":
            if check_catch_all(domain, mx_hosts):
                result = "catch_all"

        lead["email_status"] = result
        stats[result] = stats.get(result, 0) + 1
        processed += 1

        icons = {
            "valid": "OK", "catch_all": "CA", "rejected": "XX",
            "ip_blocked": "BL", "unknown": "??", "timeout": "TO"
        }
        icon = icons.get(result, "??")
        print(f"  [{processed}/{len(retry_indices)}] {icon}  {result:15s} — {email}")

        if processed % SAVE_EVERY == 0:
            save_csv(leads, fieldnames, filepath)
            print(f"  --- Saved ---")

        time.sleep(DELAY_BETWEEN)

    save_csv(leads, fieldnames, filepath)

    print(f"\nRetry results:")
    for s, c in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {s:15s}: {c}")

    # Overall stats
    overall = {}
    for lead in leads:
        s = lead.get("email_status", "unknown")
        overall[s] = overall.get(s, 0) + 1
    total = len(leads)
    print(f"\nOverall file stats:")
    for s, c in sorted(overall.items(), key=lambda x: -x[1]):
        pct = c / total * 100
        print(f"  {s:15s}: {c:>4} ({pct:5.1f}%)")


def main():
    leads_dir = "/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads"
    files = [
        os.path.join(leads_dir, "2026-02-12-apollo-Engineering-service-50-500-employees-with-icebreakers.csv"),
        os.path.join(leads_dir, "2026-02-12-apollo-Accounting-2-100-employees-with-icebreakers.csv"),
    ]
    for fp in files:
        if os.path.exists(fp):
            process_file(fp)
    print(f"\n{'='*60}")
    print("DONE — remaining ip_blocked are all Outlook/Microsoft (need paid service)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
