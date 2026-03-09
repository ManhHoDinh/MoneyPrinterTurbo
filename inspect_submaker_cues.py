import asyncio
import edge_tts

async def main():
    text = "Hello, world! This is a test."
    voice = "en-US-AriaNeural"
    communicate = edge_tts.Communicate(text, voice)
    sub_maker = edge_tts.SubMaker()
    async for chunk in communicate.stream():
        if chunk["type"] == "WordBoundary":
            sub_maker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
    
    print("Cues:", sub_maker.cues)
    if sub_maker.cues:
        print("First cue type:", type(sub_maker.cues[0]))
        print("First cue dict:", sub_maker.cues[0].__dict__ if hasattr(sub_maker.cues[0], "__dict__") else sub_maker.cues[0])

if __name__ == "__main__":
    asyncio.run(main())
