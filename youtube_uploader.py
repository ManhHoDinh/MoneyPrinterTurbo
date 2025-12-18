
import argparse
import base64
import json
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_credentials():
    """Reads and decodes credentials from environment variable."""
    creds_base64 = os.environ.get("YOUTUBE_CREDENTIALS")
    if not creds_base64:
        raise ValueError("YOUTUBE_CREDENTIALS environment variable not set.")
    
    creds_json = base64.b64decode(creds_base64).decode("utf-8")
    creds_info = json.loads(creds_json)
    
    # The JSON from Google contains 'installed' key, but Credentials wants the inner keys directly
    if 'installed' in creds_info:
        creds_info = creds_info['installed']

    # The user-provided JSON already contains the refresh_token after local authorization
    if 'refresh_token' not in creds_info:
        raise ValueError("Credentials missing 'refresh_token'. Please re-authorize locally.")

    return Credentials.from_authorized_user_info(
        info={
            "client_id": creds_info["client_id"],
            "client_secret": creds_info["client_secret"],
            "refresh_token": creds_info["refresh_token"],
        },
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

def upload_video(youtube, args):
    """Uploads a video to YouTube."""
    body = {
        "snippet": {
            "title": args.title,
            "description": args.description,
            "tags": args.tags.split(',') if args.tags else [],
        },
        "status": {
            "privacyStatus": args.privacy_status
        }
    }

    print(f"Uploading video '{args.video_path}' with title '{args.title}'...")
    media = MediaFileUpload(args.video_path, chunksize=-1, resumable=True)
    
    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%.")
            
    print(f"Upload successful! Video ID: {response.get('id')}")
    print(f"Watch on YouTube: https://www.youtube.com/watch?v={response.get('id')}")

def main():
    parser = argparse.ArgumentParser(description="Upload a video to YouTube.")
    parser.add_argument("--video-path", required=True, help="Path to the video file.")
    parser.add_argument("--title", required=True, help="Title of the video.")
    parser.add_argument("--description", default="", help="Description of the video.")
    parser.add_argument("--tags", default="", help="Comma-separated tags for the video.")
    parser.add_argument("--privacy-status", default="private", choices=["public", "private", "unlisted"], help="Privacy status of the video.")
    
    args = parser.parse_args()

    if not os.path.exists(args.video_path):
        raise FileNotFoundError(f"Video file not found at: {args.video_path}")

    try:
        credentials = get_credentials()
        youtube = build("youtube", "v3", credentials=credentials)
        upload_video(youtube, args)
    except Exception as e:
        print(f"An error occurred: {e}")
        # In a CI/CD environment, exiting with a non-zero code is important
        exit(1)

if __name__ == "__main__":
    main()
