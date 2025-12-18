
import os
import requests
import subprocess
import time
import json
import argparse
from datetime import datetime
import sys
import signal

# Configuration
API_BASE_URL = "http://127.0.0.1:8080"
MAX_POLL_TIME = 1800  # 30 minutes
POLL_INTERVAL = 30  # 30 seconds

def start_server():
    """Starts the FastAPI server as a background process, compatible with Windows and Linux."""
    print("Starting FastAPI server...")
    try:
        if sys.platform == "win32":
            # Use CREATE_NEW_PROCESS_GROUP on Windows to allow killing the process tree
            server_process = subprocess.Popen(
                ["python", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Use preexec_fn=os.setsid on Linux/macOS to run in a new session
            server_process = subprocess.Popen(
                ["python", "main.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
        
        time.sleep(10)  # Wait for the server to start
        print(f"Server started with PID: {server_process.pid}")
        return server_process
    except Exception as e:
        print(f"Error starting server: {e}")
        return None

def stop_server(process):
    """Stops the FastAPI server, compatible with Windows and Linux."""
    if process:
        print(f"Stopping FastAPI server with PID: {process.pid}...")
        try:
            if sys.platform == "win32":
                # On Windows, terminate the entire process group.
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], check=True)
            else:
                # On Linux/macOS, kill the entire process group using the session ID.
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            process.wait(timeout=30)
            print("Server stopped.")
        except (subprocess.CalledProcessError, ProcessLookupError, OSError) as e:
            print(f"Error stopping server, it might have already been stopped: {e}")




def generate_video(topic):
    """Sends a request to generate a video for a given topic."""
    print(f"Requesting video generation for topic: '{topic}'")
    try:
        payload = {
            "video_subject": topic,
            "voice_name": "en-US-EmmaMultilingualNeural-Female"
        }
        response = requests.post(f"{API_BASE_URL}/videos", json=payload)
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
            response = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
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
        response = requests.get(download_url, stream=True)
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

    server_process = start_server()
    if not server_process:
        return

    try:
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
                 # For now, we will skip the upload part until the user confirms the setup
                 # upload_to_youtube(download_path, topic)
                 print(f"Video for topic '{topic}' is ready at {download_path}")
                 print("Skipping YouTube upload for now.")

    finally:
        stop_server(server_process)

if __name__ == "__main__":
    main()

