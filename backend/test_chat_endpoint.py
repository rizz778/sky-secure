import asyncio
import urllib.request
import json

async def test_chat():
    url = "http://127.0.0.1:9000/assistant/chat"
    payload = {
        "message": "List my Zoho portals",
        "session_id": "test-session",
        "user_id": "test-user"
    }
    
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chat())
