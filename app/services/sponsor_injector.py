import os
import subprocess
import shutil
from loguru import logger
from typing import Optional

def inject_sponsorship(video_path: str, topic: str, affiliate_data: Optional[dict] = None) -> str:
    """
    Inject a sponsor watermark or end-screen CTA directly into the video file.
    Uses ffmpeg to overlay text on the video.
    Returns the new path of the sponsored video.
    """
    if not os.path.exists(video_path):
        logger.error(f"Cannot inject sponsor: file not found {video_path}")
        return video_path
        
    logger.info(f"Injecting sponsorship into {video_path}")
    
    # Generate unique output path
    dir_name = os.path.dirname(video_path)
    base_name = os.path.basename(video_path)
    name, ext = os.path.splitext(base_name)
    output_path = os.path.join(dir_name, f"{name}_sponsored{ext}")
    
    # Build text to overlay
    sponsor_text = "Sponsored by 1BillionRev™"
    if affiliate_data and "text" in affiliate_data:
        sponsor_text = affiliate_data["text"]
    elif "marketing" in topic.lower():
        sponsor_text = "Free Marketing Tools in Bio 👇"
    elif "psychology" in topic.lower():
        sponsor_text = "Unlock Mind Secrets - Link in Bio 🧠"
        
    # Escape tricky characters for ffmpeg
    sponsor_text = sponsor_text.replace("'", "").replace(":", "\\:").replace("=", "\\=")

    try:
        # FFMPEG drawtext filter: place text at the bottom, centered, with a semi-transparent black background
        # fontfile is generally optional if the system has default fonts, but 'Arial' usually works on Windows
        drawtext_filter = (
            f"drawtext=fontfile=/Windows/Fonts/arial.ttf:text='{sponsor_text}':"
            "fontcolor=white:fontsize=36:box=1:boxcolor=black@0.5:boxborderw=10:"
            "x=(w-text_w)/2:y=h-text_h-100"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-filter_complex", drawtext_filter,
            "-codec:a", "copy",
            "-preset", "fast",
            output_path
        ]
        
        # Run ffmpeg
        logger.debug(f"Running ffmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        logger.info(f"Successfully injected sponsor into {output_path}")
        return output_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg sponsor injection failed: {e.stderr}")
        return video_path
    except Exception as e:
        logger.error(f"Sponsor injection crashed: {e}")
        return video_path
