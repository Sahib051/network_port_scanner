import socket
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BANNER = r"""
========================================
        PYTHON NETWORK PORT SCANNER
========================================
Educational use only. Scan only hosts
you own or have permission to test.
"""

def normalize_target(target: str) -> str:
    """
    Accepts a URL/domain/IP, returns hostname or IP.
    Examples:
      http://example.com      -> example.com
      https://example.com:80  -> example.com
      192.168.1.10            -> 192.168.1.10
    """
    target = target.strip()
    if "://" not in target:
        candidate = "http://" + target
    else:
        candidate = target

    parsed = urlparse(candidate)
    host = parsed.hostname
    if not host:
        host = target.split("/")[0].split(":")[0]
    return host


def resolve_host(host: str) -> str:
    """
    Resolves a hostname/domain to IPv4 address.
    """
    try:
        ip = socket.gethostbyname(host)
        return ip
    except socket.gaierror as e:
        raise SystemExit(f"[!] Could not resolve target '{host}': {e}")


def parse_ports(port_input: str):
    """
    Parses ports like:
      80
      80,443,8080
      1-1024
      22,80,443,8000-8100
    """
    port_input = port_input.strip()
    if not port_input:
        raise ValueError("Port input cannot be empty.")

    ports = set()
    parts = port_input.split(",")

    for part in parts:
        part = part.strip()
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            if start < 1 or end > 65535 or start > end:
                raise ValueError(f"Invalid port range: {part}")
            for p in range(start, end + 1):
                ports.add(p)
        else:
            p = int(part)
            if p < 1 or p > 65535:
                raise ValueError(f"Invalid port: {p}")
            ports.add(p)

    return sorted(ports)


def scan_single_port(ip: str, port: int, timeout: float = 0.5):
    """
    TCP connect scan on a single port.
    Returns (port, True/False).
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        result = s.connect_ex((ip, port))
        return port, (result == 0)


def scan_ports(ip: str, ports, timeout: float = 0.5, workers: int = 200):
    """
    Scans multiple ports using a thread pool.
    Returns list of (port, is_open).
    """
    results = []
    if not ports:
        return results

    max_workers = min(workers, len(ports))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_single_port, ip, port, timeout): port for port in ports}
        for future in as_completed(futures):
            port, is_open = future.result()
            results.append((port, is_open))

    return sorted(results, key=lambda x: x[0])


def save_report(target_str: str, host: str, ip: str, results, filename: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    open_ports = [p for p, status in results if status]

    with open(filename, "w", encoding="utf-8") as f:
        f.write("PYTHON NETWORK PORT SCAN REPORT\n")
        f.write("================================\n")
        f.write(f"Time       : {now}\n")
        f.write(f"Input      : {target_str}\n")
        f.write(f"Host       : {host}\n")
        f.write(f"Resolved IP: {ip}\n\n")
        f.write("Port Status:\n")
        for port, is_open in results:
            status = "OPEN" if is_open else "CLOSED"
            f.write(f"  Port {port:5d}: {status}\n")

        f.write("\nSummary:\n")
        f.write(f"  Total ports scanned: {len(results)}\n")
        f.write(f"  Open ports         : {len(open_ports)}\n")
        if open_ports:
            f.write(f"  List of open ports : {', '.join(str(p) for p in open_ports)}\n")


def choose_target_type():
    print("Select target type:")
    print("  1) Domain / URL (e.g. http://example.com)")
    print("  2) IP address   (e.g. 192.168.1.10)")
    while True:
        choice = input("Enter choice (1 or 2): ").strip()
        if choice in ("1", "2"):
            return choice
        print("[!] Invalid choice. Please enter 1 or 2.")


def main():
    print(BANNER)

    target_type = choose_target_type()
    if target_type == "1":
        target_str = input("Enter domain or URL (e.g. http://example.com): ").strip()
    else:
        target_str = input("Enter IP address (e.g. 192.168.1.10): ").strip()

    if not target_str:
        print("[!] Target cannot be empty.")
        return

    host = normalize_target(target_str)
    ip = resolve_host(host)

    print(f"\n[+] Normalized Host: {host}")
    print(f"[+] Resolved IP    : {ip}")

    print("\nPort input options:")
    print("  - Single port          : 80")
    print("  - Multiple ports       : 20,21 22,23,25,53,80,110,143,443,3389,8080")
    print("  - Range of ports       : 1-1024")
    print("  - Mix of above formats : 22,80,443,8000-8100")
    print("  - Scan all ports       : 1-65535")

    port_input = input("\nEnter port(s) to scan: ").strip()

    try:
        ports = parse_ports(port_input)
    except ValueError as e:
        print(f"[!] Port input error: {e}")
        return

    if not ports:
        print("[!] No valid ports to scan.")
        return

    # Optional: let user adjust timeout
    timeout_str = input("Enter timeout per port in seconds [default 0.5]: ").strip()
    if timeout_str:
        try:
            timeout = float(timeout_str)
        except ValueError:
            print("[!] Invalid timeout value. Using default 0.5 seconds.")
            timeout = 0.5
    else:
        timeout = 0.5

    print(f"\n[+] Starting scan on {ip}")
    print(f"[+] Number of ports: {len(ports)}")
    print(f"[+] Timeout/port   : {timeout} seconds\n")

    results = scan_ports(ip, ports, timeout=timeout)

    print("Scan results:")
    print("-------------")
    open_ports = []
    for port, is_open in results:
        if is_open:
            print(f"[OPEN ] Port {port}")
            open_ports.append(port)
        else:
            print(f"[closed] Port {port}")

    if open_ports:
        print(f"\n[+] Open ports found: {', '.join(str(p) for p in open_ports)}")
    else:
        print("\n[+] No open ports found in the given list.")

    # Save report
    filename = f"scan_report_{host.replace('.', '_')}.txt"
    save_report(target_str, host, ip, results, filename)
    print(f"\n[+] Report saved to: {filename}")
    print("\n====================")
    print("       DONE")
    print("====================")


if __name__ == "__main__":
    main()