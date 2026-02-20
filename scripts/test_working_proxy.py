"""Test the working proxies against a known-good domain (Gmail catch-all test)."""
import socks
import socket
import dns.resolver

# Test against Gmail which we know works
test_email = "postmaster@gmail.com"  # Known to exist
domain = "gmail.com"
records = dns.resolver.resolve(domain, 'MX')
mx_host = str(sorted(records, key=lambda r: r.preference)[0].exchange).rstrip('.')
print(f"MX for gmail.com: {mx_host}")

proxies = [
    ("123.54.197.49", 20498),
    ("123.54.197.52", 22840),
]

for host, port in proxies:
    print(f"\nTesting {host}:{port} against {mx_host}:25...")
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, host, port)
        s.settimeout(15)
        s.connect((mx_host, 25))

        banner = s.recv(1024).decode('utf-8', errors='replace')
        print(f"  Banner: {banner.strip()[:80]}")

        s.send(b"EHLO cmh2.tech\r\n")
        resp = s.recv(4096).decode('utf-8', errors='replace')
        print(f"  EHLO: OK")

        s.send(b"MAIL FROM:<test@cmh2.tech>\r\n")
        resp = s.recv(1024).decode('utf-8', errors='replace')
        print(f"  MAIL FROM: {resp.strip()[:80]}")

        s.send(f"RCPT TO:<{test_email}>\r\n".encode())
        resp = s.recv(1024).decode('utf-8', errors='replace')
        print(f"  RCPT TO ({test_email}): {resp.strip()[:80]}")

        # Also test a fake email
        fake = "zzz_nonexistent_12345@gmail.com"
        s.send(f"RCPT TO:<{fake}>\r\n".encode())
        resp = s.recv(1024).decode('utf-8', errors='replace')
        print(f"  RCPT TO ({fake}): {resp.strip()[:80]}")

        s.send(b"QUIT\r\n")
        s.close()
    except Exception as e:
        print(f"  Error: {e}")
