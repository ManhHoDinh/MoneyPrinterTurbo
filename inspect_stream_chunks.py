import asyncio
import edge_tts

async def main():
    text = "Hello, world! This is a test."
    voice = "en-US-AriaNeural"
    communicate = edge_tts.Communicate(text, voice)
    
    chunks = []
    async for chunk in communicate.stream():
        chunks.append(chunk["type"])
    
    print("Chunk types received:", set(chunks))
    print("Total chunks:", len(chunks))

if __name__ == "__main__":
    asyncio.run(main())
