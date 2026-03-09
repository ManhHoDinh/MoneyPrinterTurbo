"""
Viral Story Structure Engine — GOD MODE Script Psychology.

Enforces elite script psychology:
  HOOK → micro mystery → escalation → false belief break → emotional peak → unresolved ending

Injects open loops every 5-7 sentences, belief-violating statements,
polarizing lines, and comment-bait endings.
"""

import re
import random
from typing import List, Optional, Dict, Any
from loguru import logger


# ── Open Loop Templates ──────────────────────────────────────────────────────

OPEN_LOOP_INJECTIONS = [
    "But that's not even the craziest part.",
    "And it gets worse.",
    "Wait until you hear what happens next.",
    "But here's where it gets interesting.",
    "Now here's the part nobody talks about.",
    "This next one will blow your mind.",
    "But the real question is…",
    "And that's just the beginning.",
    "Hold on. It gets even crazier.",
    "You won't believe what comes next.",
]

# ── Mid-Video Pattern Interrupts ─────────────────────────────────────────────

PATTERN_INTERRUPTS = [
    "Stop. Let that sink in.",
    "Read that again.",
    "Think about that for a second.",
    "Let me say that one more time.",
    "Pause. This is important.",
    "Did you catch that?",
    "Now pay attention to this part.",
    "Here's the twist.",
]

# ── Comment Bait Endings ─────────────────────────────────────────────────────

COMMENT_BAIT_ENDINGS = {
    "question": [
        "What would YOU do?",
        "Do you agree or disagree?",
        "Which one resonated with you most?",
        "Have you experienced this?",
        "What's YOUR take on this?",
        "Comment your answer below.",
        "Am I wrong? Tell me.",
    ],
    "challenge": [
        "Try this for 7 days and watch what happens.",
        "I dare you to prove me wrong.",
        "Send this to someone who needs to hear it.",
        "Save this before it's too late.",
        "If this helped, you know what to do.",
    ],
    "polarizing": [
        "Most people won't agree with this. And that's the point.",
        "This will offend some people. But it's the truth.",
        "You either get it or you don't.",
        "Only 1% of people actually understand this.",
        "Unpopular opinion. But I stand by it.",
    ],
}

# Style-specific endings
STYLE_ENDINGS = {
    "dark_psychology": "polarizing",
    "motivation": "challenge",
    "luxury_lifestyle": "question",
    "stoic_philosophy": "question",
    "viral_facts": "question",
}


# ── Script Rewriting ─────────────────────────────────────────────────────────

def rewrite_for_virality(
    script: str,
    video_style: str = "",
    inject_open_loops: bool = True,
    inject_pattern_interrupt: bool = True,
    inject_comment_bait: bool = True,
) -> str:
    """
    Post-process a generated script for maximum virality.

    Injects:
    1. Open loops — unresolved curiosity at ~30% and ~60% of script
    2. Mid-video pattern interrupt — at ~50% of script
    3. Comment bait ending — engagement-driving final line

    Returns the rewritten script.
    """
    if not script or len(script) < 50:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if len(lines) < 3:
        return script

    original_line_count = len(lines)

    # 1. Inject open loops at strategic positions
    if inject_open_loops and len(lines) >= 5:
        lines = _inject_open_loops(lines)

    # 2. Inject mid-video pattern interrupt
    if inject_pattern_interrupt and len(lines) >= 6:
        lines = _inject_pattern_interrupt(lines)

    # 3. Replace/enhance ending with comment bait
    if inject_comment_bait:
        lines = _inject_comment_bait(lines, video_style)

    result = "\n\n".join(lines)

    injected = len(lines) - original_line_count
    logger.info(
        f"viral rewrite complete: {original_line_count} → {len(lines)} lines "
        f"(+{injected} injected), style={video_style or 'default'}"
    )
    return result


def _inject_open_loops(lines: list) -> list:
    """
    Insert open loop statements at ~30% and ~60% of the script.
    These create unresolved curiosity that keeps viewers watching.
    """
    result = list(lines)
    n = len(result)

    # Position 1: ~30% through
    pos1 = max(2, n // 3)
    # Position 2: ~60% through
    pos2 = max(pos1 + 2, int(n * 0.6))

    # Pick two distinct open loops
    loops = random.sample(OPEN_LOOP_INJECTIONS, min(2, len(OPEN_LOOP_INJECTIONS)))

    # Insert in reverse order to preserve indices
    if pos2 < len(result):
        result.insert(pos2, loops[1] if len(loops) > 1 else loops[0])

    if pos1 < len(result):
        result.insert(pos1, loops[0])

    return result


def _inject_pattern_interrupt(lines: list) -> list:
    """
    Insert a pattern interrupt at ~50% of the script.
    This re-grabs attention at the point where viewers typically drop off.
    """
    result = list(lines)
    n = len(result)

    mid_point = n // 2
    # Avoid inserting right next to an already-injected open loop
    # by looking for a clean insertion point
    insert_pos = mid_point
    for offset in range(3):
        candidate = mid_point + offset
        if candidate < len(result) and result[candidate] not in OPEN_LOOP_INJECTIONS:
            insert_pos = candidate
            break

    interrupt = random.choice(PATTERN_INTERRUPTS)
    result.insert(insert_pos, interrupt)

    return result


def _inject_comment_bait(lines: list, video_style: str = "") -> list:
    """
    Replace or append a comment-bait ending to the script.
    """
    result = list(lines)

    # Determine ending type based on style
    ending_type = STYLE_ENDINGS.get(video_style, "question")
    endings = COMMENT_BAIT_ENDINGS.get(ending_type, COMMENT_BAIT_ENDINGS["question"])

    bait = random.choice(endings)

    # Check if last line already has a question/CTA
    last_line = result[-1].lower() if result else ""
    has_question = any(
        indicator in last_line
        for indicator in ["?", "comment", "share", "follow", "agree", "disagree", "save"]
    )

    if has_question:
        # BLACK OPS: Force comment bait by replacing weak questions with proven high-converting triggers
        result[-1] = bait
        return result

    result.append(bait)
    return result


# ── LLM-Powered Viral Rewrite ────────────────────────────────────────────────

def rewrite_script_via_llm(
    script: str,
    video_subject: str,
    video_style: str = "",
) -> str:
    """
    Use LLM to do a full viral rewrite of the script.

    This is a heavier operation that completely restructures the script
    for viral psychology. Falls back to template-based injection if LLM fails.
    """
    from app.services.llm import _generate_response

    prompt = f"""
# Role: Viral Video Script Optimizer

## Task:
Rewrite the following script to maximize viewer RETENTION and ENGAGEMENT.

## Viral Psychology Rules:
1. Add at least 2 OPEN LOOPS — tease what's coming without revealing it
2. Add 1 MID-VIDEO PATTERN INTERRUPT — a jarring pause that re-grabs attention
3. End with COMMENT BAIT — a question or statement that FORCES viewers to comment
4. Keep the core content and facts IDENTICAL — only restructure for engagement
5. Maintain the original language

## Script Structure to Follow:
- Hook (already in script — keep it)
- Value point 1
- OPEN LOOP ("But that's not even the craziest part...")  
- Value point 2-3
- PATTERN INTERRUPT ("Stop. Let that sink in.")
- OPEN LOOP ("Wait until you hear this…")
- Value point 4-5
- Climax/revelation
- COMMENT BAIT ending ("What would YOU do?")

## Original Script:
{script}

## Video Subject: {video_subject}

## Rules:
- Return ONLY the rewritten script — no labels, no formatting
- Keep under 150 words
- Keep the same language as the original

Rewrite now.
""".strip()

    try:
        response = _generate_response(prompt)
        if response and "Error: " not in response:
            # Clean response
            rewritten = response.strip().replace("*", "").replace("#", "")
            rewritten = re.sub(r"\[.*?\]", "", rewritten)
            if len(rewritten) > 50:
                logger.info("LLM viral rewrite successful")
                return rewritten
    except Exception as e:
        logger.warning(f"LLM viral rewrite failed: {e}")

    # Fallback to template-based injection
    logger.info("falling back to template viral rewrite")
    return rewrite_for_virality(script, video_style)


# ── Elite Script Psychology (GOD MODE) ───────────────────────────────────────

BELIEF_BREAK_STATEMENTS = [
    "Everything you were taught about this is wrong.",
    "The opposite is actually true.",
    "Most experts have been lying about this.",
    "Science recently proved the conventional wisdom is backwards.",
    "The real answer is the one nobody wants to hear.",
    "What if the solution was the exact opposite of what you think?",
    "Here's the uncomfortable truth nobody admits.",
    "The data shows the exact opposite of what you'd expect.",
]

POLARIZING_STATEMENTS = [
    "Most people won't agree with this. And that's exactly why it works.",
    "This is controversial. But the numbers don't lie.",
    "You're either going to love this or hate it. There's no middle ground.",
    "This goes against everything you've been told. But hear me out.",
    "Only a few people will understand this. Most will dismiss it.",
    "I know this sounds extreme. But it's backed by evidence.",
    "People get angry when they hear this. But it's the truth.",
    "Unpopular opinion: everything mainstream says about this is wrong.",
]

MICRO_MYSTERY_INJECTIONS = [
    "And here's where it gets strange.",
    "Now, this is the part they never tell you.",
    "There's a hidden detail most people miss.",
    "But there's a catch nobody sees coming.",
    "This is where the story takes a dark turn.",
]

ESCALATION_PHRASES = [
    "It's even more extreme than that.",
    "And that's just the surface.",
    "But it goes much deeper.",
    "Now multiply that by ten.",
    "This is only the beginning.",
]


def enforce_script_structure(script: str, video_style: str = "") -> str:
    """
    Validate and fix the viral beat structure post-LLM generation.

    Target structure:
      HOOK → micro mystery → escalation → false belief break
      → emotional peak → unresolved ending + comment bait

    Ensures:
    - Open loops every 5-7 sentences
    - At least one belief-violating statement
    - At least one polarizing line
    - Unresolved ending with comment bait
    """
    if not script or len(script) < 50:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if len(lines) < 4:
        return script

    original_count = len(lines)

    # 1. Ensure micro mystery (after hook, ~15% into script)
    if not _has_mystery_element(lines):
        mystery_pos = max(1, len(lines) // 6)
        mystery = random.choice(MICRO_MYSTERY_INJECTIONS)
        lines.insert(mystery_pos, mystery)

    # 2. Ensure escalation (~30% into script)
    if not _has_escalation(lines):
        esc_pos = max(2, len(lines) // 3)
        escalation = random.choice(ESCALATION_PHRASES)
        lines.insert(esc_pos, escalation)

    # 3. Ensure false belief break (~40% into script)
    lines = inject_belief_break(lines)

    # 4. Ensure polarizing element
    lines = ensure_polarizing_element(lines)

    # 5. Ensure open loops every 5-7 sentences
    lines = _enforce_open_loop_cadence(lines)

    # 6. Ensure unresolved ending
    lines = _inject_comment_bait(lines, video_style)

    result = "\n\n".join(lines)
    injected = len(lines) - original_count
    logger.info(
        f"script structure enforced: {original_count} → {len(lines)} lines "
        f"(+{injected} psychology elements injected)"
    )
    return result


def inject_belief_break(lines: list) -> list:
    """
    Insert a 'false belief break' at ~40% of the script if missing.
    A belief break challenges what the viewer assumed to be true.
    """
    result = list(lines)

    # Check if already present
    text = " ".join(result).lower()
    belief_indicators = ["wrong", "opposite", "lying", "backwards", "nobody admits",
                         "uncomfortable truth", "conventional wisdom"]
    if any(ind in text for ind in belief_indicators):
        return result

    # Insert at ~40%
    pos = max(3, int(len(result) * 0.4))
    statement = random.choice(BELIEF_BREAK_STATEMENTS)
    result.insert(pos, statement)
    return result


def ensure_polarizing_element(lines: list) -> list:
    """
    Ensure at least one polarizing statement exists in the script.
    Inserts at ~70% if missing.
    """
    result = list(lines)

    text = " ".join(result).lower()
    polarizing_indicators = ["controversial", "unpopular opinion", "won't agree",
                            "hate it", "angry", "extreme", "no middle ground"]
    if any(ind in text for ind in polarizing_indicators):
        return result

    pos = max(3, int(len(result) * 0.7))
    statement = random.choice(POLARIZING_STATEMENTS)
    result.insert(pos, statement)
    return result


def _has_mystery_element(lines: list) -> bool:
    """Check if script already contains a micro mystery element."""
    text = " ".join(lines).lower()
    mystery_indicators = ["strange", "never tell", "hidden detail", "catch", "dark turn",
                          "secret", "nobody knows", "mystery"]
    return any(ind in text for ind in mystery_indicators)


def _has_escalation(lines: list) -> bool:
    """Check if script already contains escalation."""
    text = " ".join(lines).lower()
    escalation_indicators = ["even more", "just the surface", "goes deeper",
                            "multiply", "only the beginning", "gets worse"]
    return any(ind in text for ind in escalation_indicators)


def _enforce_open_loop_cadence(lines: list) -> list:
    """
    Ensure an open loop exists every 5-7 sentences.
    If a stretch of 7+ lines has no open loop, inject one.
    """
    result = list(lines)
    if len(result) < 7:
        return result

    loop_text_lower = [ol.lower() for ol in OPEN_LOOP_INJECTIONS]

    # Find positions of existing open loops
    loop_positions = set()
    for i, line in enumerate(result):
        line_lower = line.lower()
        for ol in loop_text_lower:
            if ol[:20] in line_lower:  # partial match
                loop_positions.add(i)
                break

    # Check for gaps > 7 lines without an open loop
    injections = []
    last_loop = -1
    for i in range(len(result)):
        if i in loop_positions:
            last_loop = i
        elif i - last_loop >= 7:
            injections.append(i)
            last_loop = i

    # Insert loops in reverse to preserve indices
    for pos in reversed(injections):
        if pos < len(result):
            loop = random.choice(OPEN_LOOP_INJECTIONS)
            result.insert(pos, loop)

    return result


# ── Utility ──────────────────────────────────────────────────────────────────

def count_open_loops(script: str) -> int:
    """Count the number of open loop indicators in a script."""
    indicators = [
        "but that's not", "it gets worse", "what happens next",
        "gets interesting", "nobody talks about", "blow your mind",
        "real question", "just the beginning", "gets even", "won't believe",
        "wait until", "here's the twist", "hold on",
    ]
    text = script.lower()
    return sum(1 for ind in indicators if ind in text)


def has_comment_bait(script: str) -> bool:
    """Check if the script has a comment-bait ending."""
    if not script:
        return False
    last_line = script.strip().split("\n")[-1].lower()
    bait_indicators = [
        "?", "comment", "agree", "disagree", "you do",
        "your take", "prove me", "dare you", "send this",
        "save this", "tell me",
    ]
    return any(ind in last_line for ind in bait_indicators)


def validate_script_psychology(script: str) -> Dict[str, Any]:
    """
    Score a script on psychology elements.
    Returns a dict with scores and issues.
    """
    if not script:
        return {"score": 0, "issues": ["empty script"]}

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    issues = []
    score = 0

    # Check for open loops
    loop_count = count_open_loops(script)
    if loop_count >= 2:
        score += 25
    elif loop_count >= 1:
        score += 15
    else:
        issues.append("no open loops detected")

    # Check for belief break
    text_lower = script.lower()
    belief_indicators = ["wrong", "opposite", "lying", "backwards",
                         "uncomfortable truth", "conventional wisdom"]
    if any(ind in text_lower for ind in belief_indicators):
        score += 25
    else:
        issues.append("no belief break found")

    # Check for polarizing element
    polarizing_indicators = ["controversial", "unpopular", "won't agree",
                            "hate it", "angry", "extreme", "no middle ground"]
    if any(ind in text_lower for ind in polarizing_indicators):
        score += 25
    else:
        issues.append("no polarizing element")

    # Check for comment bait ending
    if has_comment_bait(script):
        score += 25
    else:
        issues.append("no comment bait ending")

    return {"score": score, "issues": issues, "open_loops": loop_count}
