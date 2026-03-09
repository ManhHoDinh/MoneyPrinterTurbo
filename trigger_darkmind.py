import sys
import os

from app.db.engine import SessionLocal
from app.db.models import VideoJob, Channel

db = SessionLocal()

channel_id = '0dd52585-cdbe-405b-919e-f2b0c2b2429f'
channel = db.query(Channel).filter(Channel.id == channel_id).first()
if not channel:
    print("Darkmind channel not found")
    sys.exit(1)

# Create a test job for Darkmind
job = VideoJob(
    channel_id=channel_id,
    topic="The dark truth about sleep paralysis",
    style="dark_psychology",
    language="en",
    status="pending"
)
db.add(job)
db.commit()

print(f"Created Darkmind Job: {job.id}")

# Intercept and patch config to avoid whisper
from app.config import config
config.app["subtitle_provider"] = "edge"
config.whisper["device"] = "cpu"

from app.worker.tasks import generate_video_task

print("Triggering video generation synchronously...")
# Run the task synchronously (this will take a while, maybe we should just delay and wait, but synchronous allows us to see logs)
# Let's see if generate_video_task blocks
result = generate_video_task(job.id)
print(f"Result: {result}")
