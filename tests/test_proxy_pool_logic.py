
"""
Manual test script for Proxy IP Pool Logic.

Prerequisites:
    - Browser API running (mock or real)
    - Database initialized with proxy_ips table
"""

import sys
from unittest.mock import MagicMock, patch

from src.utils.storage import EnvironmentRepository, ProxyIPRepository


def test_proxy_ip_pool():
    print("🚀 Starting Proxy IP Pool Test...")
    
    proxy_repo = ProxyIPRepository()
    env_repo = EnvironmentRepository()
    
    # 1. Clear existing IPs for test
    print("🧹 Cleaning up old test data...")
    proxy_repo._execute_write("DELETE FROM proxy_ips")
    
    # 2. Add IPs
    print("➕ Adding Test IPs...")
    id1 = proxy_repo.create("192.168.1.101", "8080", "user1", "pass1", "http")
    id2 = proxy_repo.create("192.168.1.102", "8080", "user2", "pass2", "socks5")
    id3 = proxy_repo.create("192.168.1.103", "8080", "user3", "pass3", "http")
    
    print(f"   Added IDs: {id1}, {id2}, {id3}")
    
    # 3. Test Get Least Used (Should be id1 because of ID order if usage is same)
    print("🔍 Testing get_least_used (Expect id1)...")
    least = proxy_repo.get_least_used()
    print(f"   Result: ID={least['id']}, IP={least['ip']}, Usage={least['usage_count']}")
    assert least['id'] == id1
    
    # 4. Increment Usage for id1
    print("📈 Incrementing usage for id1...")
    proxy_repo.increment_usage(id1)
    
    # 5. Test Get Least Used (Should be id2 now)
    print("🔍 Testing get_least_used (Expect id2)...")
    least = proxy_repo.get_least_used()
    print(f"   Result: ID={least['id']}, IP={least['ip']}, Usage={least['usage_count']}")
    assert least['id'] == id2
    
    # 6. Increment Usage for id2 and id3
    print("📈 Incrementing usage for id2 and id3...")
    proxy_repo.increment_usage(id2)
    proxy_repo.increment_usage(id3)
    
    # Now all have usage=1. Should return id1 again.
    least = proxy_repo.get_least_used()
    print(f"   Result with all=1 usage: ID={least['id']} (Expect {id1})")
    assert least['id'] == id1
    
    # 7. Decrement Usage for id2
    print("📉 Decrementing usage for id2...")
    proxy_repo.decrement_usage(id2) # id2 usage should be 0
    
    # 8. Test Get Least Used (Should be id2)
    print("🔍 Testing get_least_used (Expect id2)...")
    least = proxy_repo.get_least_used()
    print(f"   Result: ID={least['id']}, IP={least['ip']}, Usage={least['usage_count']}")
    assert least['id'] == id2
    assert least['usage_count'] == 0
    
    print("✅ Proxy IP Pool Logic Test Passed!")

if __name__ == "__main__":
    try:
        test_proxy_ip_pool()
    except AssertionError as e:
        print(f"❌ Test Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        sys.exit(1)
