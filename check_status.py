import sqlite3
import json

db = sqlite3.connect('storage/contentfarm.db')
cursor = db.cursor()

cursor.execute("SELECT id, name, encrypted_oauth_credentials FROM channels")
channels = cursor.fetchall()
print("Channels:")
for c in channels:
    print(f"  ID: {c[0]}, Name: {c[1]}, Has Creds: {bool(c[2])}")

cursor.execute("SELECT id, topic, status, video_path, error_message FROM video_jobs WHERE topic='Test video generation pipeline' ORDER BY created_at DESC LIMIT 5")
jobs = cursor.fetchall()
print("\nRecent Jobs:")
for j in jobs:
    print(f"  ID: {j[0][:8]}, Topic: '{j[1]}', Status: {j[2]}, Video Path: {j[3]}, Error: {j[4]}")

db.close()
