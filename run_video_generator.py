
import os

import requests

import subprocess

import time

import json

import argparse

from datetime import datetime

import sys



# Configuration



API_BASE_URL = "http://127.0.0.1:8080"



MAX_POLL_TIME = 1800  # 30 minutes



POLL_INTERVAL = 30  # 30 seconds



def generate_video(topic):

    """Sends a request to generate a video for a given topic."""

    print(f"Requesting video generation for topic: '{topic}'")

    try:

        payload = {

            "video_subject": topic,

            "voice_name": "en-US-EmmaMultilingualNeural-Female"

        }

        response = requests.post(f"{API_BASE_URL}/api/v1/videos", json=payload, timeout=60)

        response.raise_for_status()

        task_id = response.json()["data"]["task_id"]

        print(f"Video generation task started with ID: {task_id}")

        return task_id

    except requests.exceptions.RequestException as e:

        print(f"Error starting video generation: {e}")

        return None



def poll_task_status(task_id):

    """Polls the task status until it's completed or fails."""

    start_time = time.time()

    while time.time() - start_time < MAX_POLL_TIME:

        try:

            print(f"Polling status for task ID: {task_id}...")

            response = requests.get(f"{API_BASE_URL}/api/v1/tasks/{task_id}", timeout=60)

            response.raise_for_status()

            task_data = response.json().get("data", {})

            

            if not task_data:

                print("Polling response did not contain 'data' field. Retrying...")

                time.sleep(POLL_INTERVAL)

                continue



            status = task_data.get("state")

            progress = task_data.get("progress", 0)

            

            print(f"Task status: {status}, Progress: {progress}%")



            if status == "completed":

                print("Video generation completed.")

                videos = task_data.get("combined_videos", task_data.get("videos", []))

                if videos:

                    return videos[0]

                else:

                    print("Error: Task completed but no video URL found.")

                    return None

            elif status == "failed":

                print(f"Video generation failed for task {task_id}.")

                return None



            time.sleep(POLL_INTERVAL)

        except requests.exceptions.RequestException as e:

            print(f"Error polling task status: {e}")

            time.sleep(POLL_INTERVAL)

        except json.JSONDecodeError:

            print("Error decoding JSON from polling response. Waiting before retry.")

            time.sleep(POLL_INTERVAL)



    print("Polling timed out.")

    return None



def download_video(video_url, download_path):

    """Downloads the video from the given URL."""

    try:

        # The URL from the API is like http://127.0.0.1:8080/tasks/.../final.mp4

        # We need to change it to the download endpoint

        download_url = video_url.replace("/tasks/", "/download/")

        print(f"Downloading video from {download_url} to {download_path}")

        response = requests.get(download_url, stream=True, timeout=300)

        response.raise_for_status()

        with open(download_path, "wb") as f:

            for chunk in response.iter_content(chunk_size=8192):

                f.write(chunk)

        print("Video downloaded successfully.")

        return download_path

    except requests.exceptions.RequestException as e:

        print(f"Error downloading video: {e}")

        return None



def upload_to_youtube(video_path, topic):

    """Uploads the video to YouTube."""

    print(f"Uploading '{video_path}' to YouTube...")

    try:

        # youtube-uploader-selenium --video-path="path" --title="title" --description="description"

        description = f"AI-generated video about {topic}. Created on {datetime.now().strftime('%Y-%m-%d')}."

        # The command requires title and description to be quoted

        cmd = [

            "youtube-uploader-selenium",

            f'--video-path="{video_path}"',

            f'--title="{topic}"',

            f'--description="{description}"'

        ]

        print(f"Executing command: {' '.join(cmd)}")

        # Note: This command will open a browser window for authentication on first run.

        # It needs to be configured with a profile to run headlessly in a GitHub Action.

        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)

        print("YouTube upload stdout:", result.stdout)

        print("YouTube upload successful.")

    except subprocess.CalledProcessError as e:

        print(f"Error uploading to YouTube: {e}")

        print("Stderr:", e.stderr)

    except FileNotFoundError:

        print("Error: 'youtube-uploader-selenium' command not found.")

        print("Please ensure it's installed and in the system's PATH.")





def main():

    parser = argparse.ArgumentParser(description="Generate and upload videos based on topics.")

    parser.add_argument("topics_file", help="Path to the file containing video topics, one per line.")

    args = parser.parse_args()



    if not os.path.exists(args.topics_file):

        print(f"Error: Topics file not found at '{args.topics_file}'")

        return



    print("Waiting for server to be ready...")

    # Health check to ensure the server is up before proceeding

    for _ in range(5):

        try:

            response = requests.get(f"{API_BASE_URL}/docs", timeout=10)

            if response.status_code == 200:

                print("Server is ready.")

                break

        except requests.ConnectionError:

            pass

        print("Server not ready yet, retrying in 5 seconds...")

        time.sleep(5)

    else:

        print("Server did not become ready in time. Aborting.")

        sys.exit(1)





    with open(args.topics_file, "r", encoding="utf-8") as f:

        topics = [line.strip() for line in f if line.strip()]



    for topic in topics:

        task_id = generate_video(topic)

        if not task_id:

            continue



        video_url = poll_task_status(task_id)

        if not video_url:

            continue

        

        video_filename = os.path.basename(video_url)

        download_path = os.path.join(os.getcwd(), video_filename)



        if download_video(video_url, download_path):

                # Set outputs for GitHub Actions
            print(f"::set-output name=video_path::{download_path}")
            print(f"::set-output name=video_title::{topic}")
            print(f"Video for topic '{topic}' is ready at {download_path}")



if __name__ == "__main__":

    main()



