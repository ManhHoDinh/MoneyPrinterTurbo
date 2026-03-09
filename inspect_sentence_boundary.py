import asyncio
import edge_tts

async def main():
    text = "Hello, world! This is a test."
    voice = "en-US-AriaNeural"
    communicate = edge_tts.Communicate(text, voice)
    
    async for chunk in communicate.stream():
        if chunk["type"] == "SentenceBoundary":
            print(chunk)

if __name__ == "__main__":
    asyncio.run(main())
