#!/usr/bin/env python3
"""
Quick test script to verify Binance WebSocket connectivity
"""
import asyncio
import websockets
import ssl
import json
import time

async def test_binance_websocket():
    """Test if Binance WebSocket is accessible"""
    # Test with a single stream first
    test_url = "wss://stream.binance.com:9443/stream?streams=btcusdt@ticker"
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    print("🔍 Testing Binance WebSocket connection...")
    print(f"📍 URL: {test_url}")
    print()
    
    try:
        print("⏳ Attempting to connect...")
        async with websockets.connect(
            test_url,
            ssl=ssl_context,
            ping_interval=20,
            ping_timeout=10
        ) as websocket:
            print("✅ Connection established!")
            print("⏳ Waiting for messages (10 second timeout)...")
            print()
            
            message_count = 0
            start_time = time.time()
            timeout = 10  # 10 seconds
            
            try:
                async for message in websocket:
                    message_count += 1
                    data = json.loads(message)
                    
                    if 'data' in data:
                        ticker = data['data']
                        price = float(ticker.get('c', 0))
                        symbol = ticker.get('s', 'UNKNOWN')
                        print(f"📨 Message #{message_count}: {symbol} = ${price:,.2f}")
                    else:
                        print(f"📨 Message #{message_count}: {message[:100]}")
                    
                    # Stop after receiving 3 messages or timeout
                    if message_count >= 3:
                        print("\n✅ Successfully received messages! WebSocket is working.")
                        break
                    
                    if time.time() - start_time > timeout:
                        print(f"\n⏱️  Timeout after {timeout} seconds")
                        if message_count == 0:
                            print("❌ No messages received - WebSocket may be blocked or not sending data")
                        break
                        
            except asyncio.TimeoutError:
                print("⏱️  Connection timeout")
            except Exception as e:
                print(f"❌ Error receiving messages: {e}")
                
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed with HTTP {e.status_code}")
        print(f"   Headers: {e.headers}")
        print("   This likely means the endpoint is blocked or unavailable")
        return False
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ Connection closed immediately (code: {e.code}, reason: {e.reason})")
        return False
    except Exception as e:
        print(f"❌ Connection error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return message_count > 0

if __name__ == "__main__":
    result = asyncio.run(test_binance_websocket())
    if result:
        print("\n✅ WebSocket test PASSED - Binance WebSocket is accessible")
    else:
        print("\n❌ WebSocket test FAILED - There may be connectivity issues")

