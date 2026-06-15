import asyncio
import os
from mistralai.client import Mistral

async def test_message_format():
    api_key = os.getenv("MISTRAL_API_KEY", "test-key")
    client = Mistral(api_key=api_key)
    
    # Test 1: dict format
    try:
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                {"role": "user", "content": "Hello"}
            ]
        )
        print("✓ Dict format works")
    except Exception as e:
        print(f"✗ Dict format failed: {e}")
    
    # Test 2: message object format
    try:
        from mistralai.client.models.usermessage import UserMessage
        response = await client.chat.complete_async(
            model="mistral-large-latest",
            messages=[
                UserMessage(content="Hello")
            ]
        )
        print("✓ Message object format works")
    except Exception as e:
        print(f"✗ Message object format failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_message_format())
