"""
Thumbnail Generation Service

Uses DALL-E 3 to generate a background image for a YouTube thumbnail, then 
uses Pillow to overlay bold, high-CTR text.
"""

import os
import uuid
from io import BytesIO
from typing import Optional

from loguru import logger
from PIL import Image, ImageDraw, ImageFont

from app.config import config
from app.utils.utils import get_resource_dir


def generate_thumbnail(topic: str, style: str, output_dir: str) -> Optional[str]:
    """
    Generates a YouTube thumbnail combining AI image generation and text overlay.
    
    1. Uses DALL-E 3 (or configured provider) to generate background.
    2. Overlays high-CTR text using Pillow.
    3. Saves to `output_dir` and returns the file path.
    """
    logger.info(f"[Thumbnail] Generating thumbnail for topic: {topic}")
    
    try:
        # 1. Generate Background Image
        bg_image_data = _generate_ai_background(topic, style)
        if not bg_image_data:
            logger.warning("[Thumbnail] AI background generation failed. Creating fallback.")
            bg_image_data = _create_fallback_background(style)
            
        # 2. Add Text Overlay
        img = Image.open(BytesIO(bg_image_data))
        
        # Resize to YouTube standard (1280x720) if not already
        if img.size != (1280, 720):
            img = img.resize((1280, 720), Image.Resampling.LANCZOS)
            
        # Get language if provided, though we only have topic/style here. 
        # By this point 'topic' in worker should already be translated, but let's just make sure
        # _overlay_text gets the correct localized string.
        img = _overlay_text(img, topic, style)
        
        # 3. Save to file
        os.makedirs(output_dir, exist_ok=True)
        filename = f"thumbnail_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(output_dir, filename)
        
        # Convert to RGB if necessary (e.g. from RGBA)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        img.save(filepath, "JPEG", quality=90)
        logger.info(f"[Thumbnail] Saved thumbnail to {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"[Thumbnail] Failed to generate thumbnail: {e}")
        return None

def _generate_ai_background(topic: str, style: str) -> Optional[bytes]:
    """Calls OpenAI API to generate a thumbnail background via DALL-E 3."""
    provider = config.app.get("llm_provider", "openai")
    
    if provider != "openai":
        logger.warning(f"[Thumbnail] Provider {provider} not supported for images yet. Provide an OpenAI key.")
        return None
        
    api_key = config.app.get("openai_api_key")
    if not api_key:
        logger.error("[Thumbnail] OpenAI API key not found in config.")
        return None
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = (
            f"A YouTube thumbnail background without any text. "
            f"High contrast, eye-catching, cinematic lighting. "
            f"Topic: {topic}. Style: {style}. "
            f"Vibrant colors, dramatic composition, highly engaging, highly detailed."
        )
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt[:1000],
            size="1024x1024",  # DALL-E 3 doesn't support 16:9 easily without specific models
            quality="standard",
            n=1,
            response_format="b64_json"
        )
        
        import base64
        b64_img = response.data[0].b64_json
        return base64.b64decode(b64_img)
        
    except Exception as e:
        logger.error(f"[Thumbnail] OpenAI Image API error: {e}")
        return None

def _create_fallback_background(style: str) -> bytes:
    """Creates a simple, colorful gradient background if API fails."""
    # Define colors based on style
    colors = {
        "dark_psychology": ((15, 15, 30), (50, 10, 50)),
        "motivation": ((100, 20, 20), (255, 100, 50)),
        "luxury": ((20, 20, 20), (200, 150, 50)),
        "default": ((20, 50, 80), (10, 20, 40))
    }
    
    color1, color2 = colors.get(style, colors["default"])
    
    # Create gradient
    img = Image.new('RGB', (1280, 720), color=color1)
    draw = ImageDraw.Draw(img)
    for y in range(720):
        r = int(color1[0] + (color2[0] - color1[0]) * (y / 720))
        g = int(color1[1] + (color2[1] - color1[1]) * (y / 720))
        b = int(color1[2] + (color2[2] - color1[2]) * (y / 720))
        draw.line([(0, y), (1280, y)], fill=(r, g, b))
        
    # Convert to bytes
    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

def _overlay_text(img: Image.Image, topic: str, style: str) -> Image.Image:
    """Overlays high-impact thumbnail text."""
    draw = ImageDraw.Draw(img)
    
    # Try to load a bold font, fallback to default
    try:
        # Assuming there's a bold font available in the system or project
        font_path = os.path.join(get_resource_dir(), "fonts", "impact.ttf")
        if not os.path.exists(font_path):
            font = ImageFont.load_default()
            font = font.font_variant(size=80) if hasattr(font, 'font_variant') else font
        else:
            font = ImageFont.truetype(font_path, 100)
    except Exception:
        font = ImageFont.load_default()
        
    # Simplify topic for text overlay (keep it under 4 words)
    words = topic.split()
    if len(words) > 4:
        display_text = " ".join(words[:4]) + "..."
    else:
        display_text = topic
        
    display_text = display_text.upper()
    
    # Calculate text layout
    if hasattr(draw, 'textbbox'):
        bbox = draw.textbbox((0, 0), display_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    else:
        # Fallback for older Pillow
        text_width = 800
        text_height = 100
        
    x = (1280 - text_width) / 2
    # Place text in the lower third
    y = 720 - text_height - 100 
    
    # Draw outline/shadow for readability
    outline_color = (0, 0, 0)
    thickness = 5
    for adj_x in range(-thickness, thickness + 1):
        for adj_y in range(-thickness, thickness + 1):
            draw.text((x + adj_x, y + adj_y), display_text, font=font, fill=outline_color)
            
    # Draw main text
    text_colors = {
        "dark_psychology": (255, 50, 50), # Red
        "motivation": (255, 255, 50),     # Yellow
        "luxury": (255, 215, 0),          # Gold
        "default": (255, 255, 255)        # White
    }
    fill_color = text_colors.get(style, text_colors["default"])
    draw.text((x, y), display_text, font=font, fill=fill_color)
    
    return img
