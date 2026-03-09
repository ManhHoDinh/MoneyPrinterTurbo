"""
Loop Addiction Design — Engineering for rewatch probability.

Implements:
- Beginning-ending callback logic
- Unresolved final line generation
- Implicit moral tension injection
- Replay encouragement design
"""

import random
import re
from typing import Optional
from loguru import logger


# ── Callback Loop Templates ─────────────────────────────────────────────────

CALLBACK_OPENERS = [
    "Remember this moment. It comes back later.",
    "Pay attention to this detail. You'll need it.",
    "Keep this in mind. It changes everything at the end.",
    "This is the part most people miss the first time.",
    "You'll want to come back to this line.",
]

CALLBACK_CLOSERS = [
    "Now go back to the beginning. See it differently.",
    "Remember what I said at the start? Now you understand.",
    "Watch it again. The meaning changes completely.",
    "The first line hits different now, doesn't it?",
    "Go back to the start. You missed the real message.",
]


# ── Unresolved Endings ───────────────────────────────────────────────────────

UNRESOLVED_ENDINGS = {
    "dark_psychology": [
        "And the worst part? You're already doing it.",
        "But the real question is... who's doing it to YOU?",
        "The scariest part hasn't even happened yet.",
        "And that's only the first layer. The deeper truth? That's for next time.",
        "You think you're safe now? Look closer.",
    ],
    "motivation": [
        "But this is just the beginning of the journey.",
        "The real question is: what are you going to do RIGHT NOW?",
        "Tomorrow is too late. The clock is already ticking.",
        "This was the easy part. The real challenge starts... now.",
        "Most people will close this and do nothing. Will you?",
    ],
    "luxury_lifestyle": [
        "But the real secret to wealth? That's a different conversation entirely.",
        "Money changes everything. But not in the way you think.",
        "The richest people know something else. Something I can't say here.",
        "This is level one. The people at the top play a completely different game.",
        "Luxury isn't the goal. What comes AFTER luxury... that's the real prize.",
    ],
    "stoic_philosophy": [
        "But the final lesson? You have to discover it yourself.",
        "Marcus Aurelius knew one more thing. But he never wrote it down.",
        "The deepest wisdom can't be taught. It can only be lived.",
        "This is the surface. The real depth? That takes a lifetime.",
        "Seneca had one final lesson. But he saved it for the very end.",
    ],
    "viral_facts": [
        "But there's ONE fact I left out. The one that changes everything.",
        "And the craziest part? Scientists still can't explain WHY.",
        "But the real mystery hasn't been solved yet.",
        "There's a fact about THIS fact that nobody knows.",
        "Wait until you hear what they discovered AFTER this.",
    ],
}

DEFAULT_UNRESOLVED = [
    "But that's only half the story.",
    "The real truth goes deeper than this.",
    "And the most important part? I haven't even said it yet.",
    "But what happens next... that's the real question.",
    "This changes everything. But not in the way you expect.",
]


# ── Moral Tension Templates ─────────────────────────────────────────────────

MORAL_TENSION_INSERTS = [
    "Is this even ethical? That's for you to decide.",
    "Some would call this manipulation. Others call it awareness.",
    "The line between knowledge and exploitation is thinner than you think.",
    "Knowing this gives you power. What you do with it defines you.",
    "This information is dangerous in the wrong hands.",
    "Use this wisely. Not everyone deserves to know.",
    "The question isn't whether this is true. It's whether you're ready for it.",
    "Some truths are better left hidden. This isn't one of them.",
]


# ── Replay Encouragement ────────────────────────────────────────────────────

REPLAY_PROMPTS = [
    "Watch this again. You missed something.",
    "There's a hidden detail in this video. Can you spot it?",
    "The second time you watch this, the meaning completely changes.",
    "90% of people miss the real message on the first watch.",
    "Rewatch from the beginning. Everything looks different now.",
]


# ── Core Functions ───────────────────────────────────────────────────────────

def add_callback_loop(script: str) -> str:
    """
    Inject beginning-ending callback reference.
    Adds a callback opener near the start and a closer at the end.
    """
    if not script:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if len(lines) < 4:
        return script

    # Insert callback opener after the hook (line 1 or 2)
    insert_pos = min(2, len(lines) - 1)
    opener = random.choice(CALLBACK_OPENERS)

    # Check if callback already exists
    if any(opener_part in script for opener_part in ["Remember this moment", "Pay attention to this detail", "Keep this in mind"]):
        return script

    lines.insert(insert_pos, opener)

    # Replace or append callback closer at the end
    closer = random.choice(CALLBACK_CLOSERS)
    lines.append(closer)

    logger.debug("injected callback loop (opener + closer)")
    return "\n".join(lines)


def add_unresolved_ending(script: str, style: str = "") -> str:
    """
    Replace final line with an open-ended cliffhanger.
    Preserves the rest of the script intact.
    """
    if not script:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if not lines:
        return script

    # Select style-appropriate ending
    endings = UNRESOLVED_ENDINGS.get(style, DEFAULT_UNRESOLVED)
    ending = random.choice(endings)

    # Check if already has an unresolved ending
    last_line = lines[-1].lower()
    unresolved_indicators = ["half the story", "deeper than", "haven't even", "real question",
                             "changes everything", "next time", "can't explain"]
    if any(ind in last_line for ind in unresolved_indicators):
        return script

    lines.append(ending)

    logger.debug(f"added unresolved ending: {ending[:40]}...")
    return "\n".join(lines)


def inject_moral_tension(script: str) -> str:
    """
    Add implicit moral dilemma element at ~60-70% of the script.
    Creates internal conflict that increases engagement.
    """
    if not script:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if len(lines) < 5:
        return script

    # Check if moral tension already exists
    tension_indicators = ["ethical", "manipulation", "exploitation", "dangerous", "wrong hands"]
    if any(ind in script.lower() for ind in tension_indicators):
        return script

    # Insert at ~65% of script
    insert_pos = int(len(lines) * 0.65)
    tension = random.choice(MORAL_TENSION_INSERTS)
    lines.insert(insert_pos, tension)

    logger.debug(f"injected moral tension at position {insert_pos}")
    return "\n".join(lines)


def design_replay_encouragement(script: str) -> str:
    """
    Add subtle replay prompts that encourage rewatching.
    """
    if not script:
        return script

    lines = [line.strip() for line in script.split("\n") if line.strip()]
    if len(lines) < 4:
        return script

    # Check if replay prompt already exists
    if any("watch" in line.lower() and "again" in line.lower() for line in lines):
        return script

    prompt = random.choice(REPLAY_PROMPTS)

    # Add near the end (but before the final line)
    insert_pos = max(1, len(lines) - 1)
    lines.insert(insert_pos, prompt)

    logger.debug("added replay encouragement prompt")
    return "\n".join(lines)


# ── Master Function ──────────────────────────────────────────────────────────

def apply_loop_addiction(
    script: str,
    style: str = "",
    enable_callback: bool = True,
    enable_unresolved: bool = True,
    enable_tension: bool = True,
    enable_replay: bool = True,
) -> str:
    """
    Master function applying all loop addiction techniques.

    Applies in order:
    1. Moral tension injection
    2. Callback loop (opener + closer)
    3. Unresolved ending
    4. Replay encouragement

    Each can be individually disabled.
    """
    if not script:
        return script

    result = script

    if enable_tension:
        result = inject_moral_tension(result)

    if enable_callback:
        result = add_callback_loop(result)

    if enable_unresolved:
        result = add_unresolved_ending(result, style)

    if enable_replay:
        result = design_replay_encouragement(result)

    logger.info("applied loop addiction design to script")
    return result
