"""
Engagement Optimizer — GOD MODE Engagement Trifecta.

Every video MUST include:
1. A polarizing statement
2. A direct question
3. An incomplete conclusion

Also handles power words, caption formatting, and CTA injection.
"""

import re
import random
from typing import Dict, List, Any, Optional

from loguru import logger

from app.services import style_presets


# ── Power Words Database ────────────────────────────────────────────────────

UNIVERSAL_POWER_WORDS = [
    # Core viral power words
    "secret", "free", "instant", "new", "proven", "guaranteed",
    "shocking", "warning", "urgent", "limited", "exclusive", "banned",
    "incredible", "unbelievable", "revolutionary", "ultimate", "powerful",
    "dangerous", "hidden", "ancient", "forbidden", "truth", "exposed",
    "never", "always", "everything", "nothing", "impossible", "unstoppable",
    # Engagement & emotion words
    "manipulat", "control", "trick", "brain", "mind", "psych",
    "scariest", "scary", "terrif", "creep", "disturb",
    "insane", "crazy", "wild", "obsess",
    "destroy", "kill", "toxic", "trap",
    "millions", "billions", "percent",
    # Action words
    "stop", "start", "quit", "avoid", "escape", "run",
    "discover", "reveal", "unlock", "master",
]

DEFAULT_COMMENT_BAIT = [
    "What do you think? Comment below 👇",
    "Do you agree? Let me know…",
    "Save this for later ❤️",
    "Share this with someone who needs it!",
    "Follow for more 🔥",
]


# ── Script Optimization ─────────────────────────────────────────────────────


def optimize_script(script: str, style_name: Optional[str] = None) -> str:
    """
    Post-process a generated script for maximum engagement.
    
    - Adds comment bait at the end
    - Formats for punchy delivery
    - Ensures proper CTA
    """
    if not script:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]

    # Get style-specific comment bait or use defaults
    if style_name:
        bait_options = style_presets.get_comment_bait(style_name)
    else:
        bait_options = DEFAULT_COMMENT_BAIT

    # Pick a comment bait to append
    comment_bait = random.choice(bait_options) if bait_options else ""

    # Ensure the script ends with engagement CTA
    optimized_lines = []
    for line in lines:
        # Make lines punchier — break long sentences
        optimized_lines.append(_punch_up_line(line))

    # Add comment bait as final line if not already present
    if comment_bait and not _has_question_ending(optimized_lines):
        optimized_lines.append(comment_bait)

    result = "\n\n".join(optimized_lines)
    logger.info(f"script optimized with engagement layer (style={style_name})")
    return result


def _punch_up_line(line: str) -> str:
    """Make a line more punchy by formatting long sentences."""
    # If line is very long, it's fine for script — TTS handles it
    # Just ensure no weird formatting artifacts
    line = line.strip()
    line = re.sub(r'\s+', ' ', line)  # collapse multiple spaces
    return line


def _has_question_ending(lines: list) -> bool:
    """Check if the script already ends with a question or CTA."""
    if not lines:
        return False
    last_line = lines[-1].lower()
    question_indicators = ["?", "comment", "share", "follow", "tag", "let me know", "agree"]
    return any(indicator in last_line for indicator in question_indicators)


# ── Caption Formatting ───────────────────────────────────────────────────────


def extract_power_words(text: str, style_name: Optional[str] = None) -> List[str]:
    """
    Extract words that should be emphasized in captions.
    Uses stem/prefix matching to catch word variants
    (e.g., 'manipulate' matches 'manipulated', 'manipulation').
    """
    stems_to_check = set(UNIVERSAL_POWER_WORDS)

    if style_name:
        caption_style = style_presets.get_caption_style(style_name)
        emphasis_words = caption_style.get("emphasis_words", [])
        stems_to_check.update(w.lower() for w in emphasis_words)

    text_words = re.findall(r'\b\w+\b', text.lower())
    found = [w for w in text_words if _stem_match(w, stems_to_check)]

    return list(set(found))


def _stem_match(word: str, stems: set) -> bool:
    """Check if word matches any stem via prefix/startswith matching."""
    word = word.lower().strip()
    # Exact match first
    if word in stems:
        return True
    # Stem matching — check if word starts with any stem
    for stem in stems:
        if len(stem) >= 4 and word.startswith(stem):
            return True
        if len(word) >= 4 and stem.startswith(word):
            return True
    return False


def format_caption_text(text: str, style_name: Optional[str] = None) -> str:
    """
    Format caption text for maximum impact:
    - Uppercase power words for emphasis
    """
    if not text:
        return text

    power_words = extract_power_words(text, style_name)

    # Uppercase power words for emphasis
    result = text
    for word in power_words:
        # Case-insensitive word boundary replacement with uppercase
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
        result = pattern.sub(lambda m: m.group(0).upper(), result)

    return result


def get_power_word_color(style_name: Optional[str] = None) -> str:
    """Get the highlight color for power words based on style."""
    if style_name:
        caption_style = style_presets.get_caption_style(style_name)
        return caption_style.get("power_word_color", "#FFFF00")
    return "#FFFF00"


def is_power_word(word: str, style_name: Optional[str] = None) -> bool:
    """Check if a word should be highlighted as a power word."""
    word_lower = word.lower().strip(".,!?;:'\"")
    
    if _stem_match(word_lower, set(UNIVERSAL_POWER_WORDS)):
        return True
    
    if style_name:
        caption_style = style_presets.get_caption_style(style_name)
        emphasis_words = set(w.lower() for w in caption_style.get("emphasis_words", []))
        if _stem_match(word_lower, emphasis_words):
            return True
    
    return False


# ── Engagement Trifecta (GOD MODE) ──────────────────────────────────────────

POLARIZING_TEMPLATES = [
    "Most people won't agree with this.",
    "This is going to offend some people.",
    "Unpopular opinion: {topic} is misunderstood.",
    "You're either with me on this or against me.",
    "I know this sounds extreme. But the evidence is clear.",
    "Only a few people will get this. The rest will scroll away.",
]

QUESTION_TEMPLATES = [
    "Do you agree with this?",
    "Most people get this wrong — are you one of them?",
    "What would YOU do in this situation?",
    "Am I the only one who thinks this?",
    "Have you ever experienced this before?",
    "Which of these resonated with you most?",
]

INCOMPLETE_CONCLUSION_TEMPLATES = [
    "And the craziest part? We haven't even scratched the surface.",
    "There's one more thing I didn't mention. But that's for next time.",
    "The real answer might surprise you. Stay tuned.",
    "But here's what nobody tells you about what happens AFTER...",
    "The full truth? It goes deeper than I can cover here.",
    "This is just part one. The real revelation is coming.",
]


def ensure_engagement_trifecta(
    script: str,
    video_subject: str = "",
    style_name: Optional[str] = None,
) -> str:
    """
    Validate and enforce the engagement trifecta.
    
    Every video MUST include:
    1. A polarizing statement
    2. A direct question
    3. An incomplete conclusion
    
    Returns the enhanced script.
    """
    if not script:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if len(lines) < 3:
        return script

    text_lower = " ".join(lines).lower()
    topic = video_subject or "this topic"

    # 1. Check for polarizing statement
    polarizing_indicators = [
        "won't agree", "offend", "unpopular", "extreme", "against me",
        "controversial", "no middle ground",
    ]
    has_polarizing = any(ind in text_lower for ind in polarizing_indicators)
    if not has_polarizing:
        pos = max(2, int(len(lines) * 0.6))
        statement = random.choice(POLARIZING_TEMPLATES).format(topic=topic)
        lines.insert(pos, statement)

    # 2. Check for direct question
    has_question = "?" in " ".join(lines[-3:])  # check last 3 lines
    if not has_question:
        question = random.choice(QUESTION_TEMPLATES)
        lines.append(question)

    # 3. Check for incomplete conclusion
    incomplete_indicators = [
        "next time", "stay tuned", "part one", "coming",
        "scratched the surface", "deeper", "didn't mention",
    ]
    has_incomplete = any(ind in text_lower for ind in incomplete_indicators)
    if not has_incomplete:
        # Replace the very last line or add after
        conclusion = random.choice(INCOMPLETE_CONCLUSION_TEMPLATES)
        lines.append(conclusion)

    result = "\n\n".join(lines)
    logger.info("engagement trifecta enforced (polarizing + question + incomplete conclusion)")
    return result


def validate_engagement_score(
    script: str,
    style_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Score a script on engagement readiness (0-100).
    
    Returns:
        {"score": 85, "has_polarizing": True, "has_question": True,
         "has_incomplete_conclusion": False, "issues": ["..."]}
    """
    if not script:
        return {"score": 0, "issues": ["empty script"],
                "has_polarizing": False, "has_question": False,
                "has_incomplete_conclusion": False}

    text_lower = script.lower()
    issues = []
    score = 0

    # Check polarizing
    polarizing_indicators = [
        "won't agree", "offend", "unpopular", "extreme", "against me",
        "controversial", "no middle ground",
    ]
    has_polarizing = any(ind in text_lower for ind in polarizing_indicators)
    if has_polarizing:
        score += 30
    else:
        issues.append("missing polarizing statement")

    # Check question
    lines = script.strip().split("\n")
    has_question = any("?" in line for line in lines[-4:])
    if has_question:
        score += 35
    else:
        issues.append("missing direct question")

    # Check incomplete conclusion
    incomplete_indicators = [
        "next time", "stay tuned", "part one", "coming",
        "scratched the surface", "deeper", "didn't mention",
    ]
    has_incomplete = any(ind in text_lower for ind in incomplete_indicators)
    if has_incomplete:
        score += 35
    else:
        issues.append("missing incomplete conclusion")

    # Bonus for power words
    power_count = len(extract_power_words(script, style_name))
    if power_count >= 3:
        score = min(score + 5, 100)

    return {
        "score": score,
        "has_polarizing": has_polarizing,
        "has_question": has_question,
        "has_incomplete_conclusion": has_incomplete,
        "issues": issues,
    }
