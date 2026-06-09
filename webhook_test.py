import asyncio

import httpx


async def test_bot():
    print("Sending a local webhook test request...")
    url = "http://localhost:8000/api/webhook/test?discussion_id=1&user_text=Hello"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url)
            print(f"Status code: {response.status_code}")
            print(f"Response body: {response.text}")
        except Exception as exc:
            print(f"Request failed: {exc}")


if __name__ == "__main__":
    asyncio.run(test_bot())