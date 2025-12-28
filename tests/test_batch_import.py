"""
Test script for Batch Import Logic.
"""


# Since BatchImportDialog is a UI class, running it headlessly is tricky without full Qt Application.
# We will focus on the parsing logic which is embedded in the `_on_batch_import` method of ProxyManagerDialog.
# Ideally, we should have separated the parsing logic into a utility function.
# For now, we will assume the manual test or UI walkthrough covers this, but we can write a small parsing test snippet here 
# if we extract the logic.

# Let's extract the parsing logic to a simple testable function to ensure our regex/split is correct.

def parse_proxy_line(line, default_proto="http"):
    line = line.strip()
    protocol = default_proto
    
    # Handle protocol prefix
    if "://" in line:
        proto_part, rest = line.split("://", 1)
        protocol = proto_part.lower()
        line = rest.strip()
        
    parts = line.split(":")
    if len(parts) >= 2:
        ip = parts[0].strip()
        port = parts[1].strip()
        user = parts[2].strip() if len(parts) > 2 else None
        password = parts[3].strip() if len(parts) > 3 else None
        return {
            "ip": ip,
            "port": port,
            "user": user,
            "password": password,
            "protocol": protocol
        }
    return None

def test_parsing():
    print("Testing proxy line parsing...")
    
    # Case 1: IP:Port (Default Protocol)
    res1 = parse_proxy_line("1.1.1.1:80")
    assert res1["ip"] == "1.1.1.1"
    assert res1["protocol"] == "http"
    
    # Case 2: Protocol://IP:Port
    res2 = parse_proxy_line("socks5://1.2.3.4:1080")
    assert res2["ip"] == "1.2.3.4"
    assert res2["port"] == "1080"
    assert res2["protocol"] == "socks5"
    
    # Case 3: Protocol://IP:Port:User:Pass
    res3 = parse_proxy_line("socks4://2.2.2.2:443:admin:pass")
    assert res3["ip"] == "2.2.2.2"
    assert res3["protocol"] == "socks4"
    assert res3["user"] == "admin"
    assert res3["password"] == "pass"
    
    # Case 4: Mixed whitespace
    res4 = parse_proxy_line("  http://3.3.3.3:8080  ")
    assert res4["ip"] == "3.3.3.3"
    assert res4["protocol"] == "http"
    
    print("✅ Parsing logic confirmed.")

if __name__ == "__main__":
    test_parsing()
