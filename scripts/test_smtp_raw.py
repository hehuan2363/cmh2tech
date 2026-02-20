"""Debug SMTP connection to understand the starttls issue."""
import socket
import dns.resolver

email = "plangan@rvanderson.com"
domain = email.split('@')[1]

# Get MX
records = dns.resolver.resolve(domain, 'MX')
for r in records:
    print(f"MX: {r.preference} {r.exchange}")

mx_host = str(list(records)[0].exchange).rstrip('.')
print(f"\nConnecting to: {mx_host}:25")

# Raw socket connection
try:
    sock = socket.create_connection((mx_host, 25), timeout=10)
    resp = sock.recv(1024)
    print(f"Banner: {resp}")

    sock.send(b"EHLO cmh2.tech\r\n")
    resp = sock.recv(4096)
    print(f"EHLO: {resp}")

    sock.send(f"MAIL FROM:<verify@cmh2.tech>\r\n".encode())
    resp = sock.recv(1024)
    print(f"MAIL FROM: {resp}")

    sock.send(f"RCPT TO:<{email}>\r\n".encode())
    resp = sock.recv(1024)
    print(f"RCPT TO: {resp}")

    sock.send(b"QUIT\r\n")
    resp = sock.recv(1024)
    print(f"QUIT: {resp}")
    sock.close()
except Exception as e:
    print(f"Error: {e}")
