"""
Fetch fresh SOCKS5 proxies and test SMTP port 25 access.
"""
import socks
import socket
import time
import urllib.request
import dns.resolver

test_email = "karen.miller@svanteinc.com"
domain = test_email.split('@')[1]
records = dns.resolver.resolve(domain, 'MX')
mx_host = str(sorted(records, key=lambda r: r.preference)[0].exchange).rstrip('.')
print(f"Testing SMTP to: {mx_host}:25 for {test_email}\n")

# Fetch fresh SOCKS5 proxies from GitHub lists
proxies = []
urls = [
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode()
        for line in text.strip().split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                parts = line.split(':')
                if len(parts) == 2:
                    try:
                        proxies.append((parts[0], int(parts[1])))
                    except ValueError:
                        pass
        print(f"  Got {len(proxies)} proxies from {url.split('/')[-2]}")
    except Exception as e:
        print(f"  Failed: {e}")

# Shuffle and take 40
import random
random.shuffle(proxies)
proxies = proxies[:40]
print(f"\nTesting {len(proxies)} proxies for SMTP port 25...\n")

working = []
for i, (host, port) in enumerate(proxies):
    print(f"  [{i+1}/{len(proxies)}] {host}:{port} ... ", end="", flush=True)
    try:
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, host, port)
        s.settimeout(8)
        s.connect((mx_host, 25))

        banner = s.recv(1024).decode('utf-8', errors='replace')
        if banner.startswith('220'):
            s.send(b"EHLO cmh2.tech\r\n")
            s.recv(4096)
            s.send(b"MAIL FROM:<verify@cmh2.tech>\r\n")
            s.recv(1024)
            s.send(f"RCPT TO:<{test_email}>\r\n".encode())
            resp = s.recv(1024).decode('utf-8', errors='replace')
            code = resp[:3]
            s.send(b"QUIT\r\n")
            try: s.recv(1024)
            except: pass
            s.close()
            print(f"SMTP OK! code={code}")
            working.append((host, port, code))
            if len(working) >= 3:
                break
        else:
            s.close()
            print("bad banner")
    except Exception as e:
        err = str(e)[:50]
        print(f"FAIL — {err}")
    time.sleep(0.3)

print(f"\n{'='*60}")
print(f"Working SMTP proxies: {len(working)}")
for h, p, c in working:
    print(f"  {h}:{p} (RCPT code: {c})")
if not working:
    print("\nNo free proxies support SMTP port 25.")
    print("This is expected — almost all proxies block port 25 to prevent spam.")
    print("\nAlternatives:")
    print("  1. Install Cloudflare WARP: sudo apt install cloudflare-warp")
    print("     Then run: warp-cli connect && python verify_emails.py")
    print("  2. MillionVerifier: ~$3 for 1,000 emails (cheapest paid option)")
    print("  3. Use any VPN app (NordVPN, ProtonVPN free tier, etc.)")
