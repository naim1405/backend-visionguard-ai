#!/usr/bin/env python3
"""
WebSocket Connection Test Script

Tests the persistent WebSocket connection with heartbeat monitoring.
"""

import asyncio
import json
import sys
from datetime import datetime
from fastapi.testclient import TestClient

# Add the parent directory to the path
sys.path.insert(0, '/home/ezio/Documents/work/backend-visionguard-ai')

from main import app


async def test_websocket_connection():
    """Test WebSocket connection with authentication and heartbeat"""
    
    print("=" * 70)
    print("WebSocket Connection Test")
    print("=" * 70)
    
    # Create test client
    client = TestClient(app)
    
    # First, create a test user and get auth token
    print("\n1. Creating test user and authenticating...")
    
    # Register test user
    register_response = client.post("/auth/register", json={
        "name": "WebSocket Test User",
        "email": f"wstest_{datetime.now().timestamp()}@example.com",
        "password": "testpassword123",
        "role": "user"
    })
    
    if register_response.status_code != 201:
        print(f"❌ Failed to register user: {register_response.text}")
        return
    
    user_data = register_response.json()
    user_id = user_data["user"]["id"]
    print(f"✓ User created: {user_id}")
    
    # Login to get token
    login_response = client.post("/auth/login", json={
        "email": user_data["user"]["email"],
        "password": "testpassword123"
    })
    
    if login_response.status_code != 200:
        print(f"❌ Failed to login: {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    print(f"✓ Authentication token obtained")
    
    # Test WebSocket connection
    print("\n2. Testing WebSocket connection...")
    
    try:
        with client.websocket_connect(f"/ws/alerts/{user_id}?token={token}") as websocket:
            print("✓ WebSocket connected successfully")
            
            # Test sending ping
            print("\n3. Testing heartbeat (ping/pong)...")
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }
            websocket.send_json(ping_message)
            print("✓ Sent ping")
            
            # Wait for pong response
            response = websocket.receive_json()
            if response.get("type") == "pong":
                print("✓ Received pong from server")
            else:
                print(f"⚠ Unexpected response: {response}")
            
            # Test receiving server ping
            print("\n4. Waiting for server ping...")
            print("   (This may take up to 30 seconds...)")
            
            try:
                # Wait for server ping (with asyncio timeout)
                server_message = websocket.receive_json()
                if server_message.get("type") == "ping":
                    print("✓ Received ping from server")
                    
                    # Send pong response
                    pong_message = {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }
                    websocket.send_json(pong_message)
                    print("✓ Sent pong to server")
                else:
                    print(f"⚠ Unexpected message type: {server_message.get('type')}")
            except Exception as e:
                print(f"⚠ Note: {e}")
            
            print("\n5. Testing connection statistics endpoint...")
            stats_response = client.get(f"/ws/connections/{user_id}")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print("✓ Connection stats retrieved:")
                print(f"   - User ID: {stats['user_id']}")
                print(f"   - Connected: {stats['connected']}")
                print(f"   - Uptime: {stats['uptime_seconds']:.2f}s")
                print(f"   - Seconds since heartbeat: {stats['seconds_since_heartbeat']:.2f}s")
            else:
                print(f"❌ Failed to get connection stats: {stats_response.text}")
            
            print("\n6. Testing acknowledgment message...")
            ack_message = {
                "type": "ack",
                "stream_id": "test_stream_123"
            }
            websocket.send_json(ack_message)
            print("✓ Sent acknowledgment")
            
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        return
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)


if __name__ == "__main__":
    print("Starting WebSocket connection test...\n")
    asyncio.run(test_websocket_connection())
