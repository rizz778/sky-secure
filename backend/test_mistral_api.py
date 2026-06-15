import asyncio
import os
from mistralai.client import Mistral

async def test_mistral():
    api_key = os.getenv("MISTRAL_API_KEY", "test-key")
    client = Mistral(api_key=api_key)
    
    # Check what methods are available
    print("Client type:", type(client))
    print("Chat type:", type(client.chat))
    print("\nAvailable methods on chat:")
    methods = [m for m in dir(client.chat) if not m.startswith('_')]
    for m in methods:
        print(f"  - {m}")
    
    # Try to understand complete_async
    import inspect
    try:
        sig = inspect.signature(client.chat.complete_async)
        print("\ncomplete_async signature:", sig)
    except Exception as e:
        print(f"\nError getting signature: {e}")

if __name__ == "__main__":
    asyncio.run(test_mistral())
