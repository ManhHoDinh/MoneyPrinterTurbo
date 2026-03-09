"""
Cinematic Hook Generator — GOD MODE A/B Testing Engine.

Generates 3-5 hook variants per topic, each using a different psychological
trigger (fear, curiosity, shock, desire, authority). Each variant is tagged
with metadata for future feedback loop integration.
"""

import random
from typing import List, Dict, Optional
from loguru import logger


# ── Psychological Trigger Templates ──────────────────────────────────────────

PSYCHOLOGICAL_TRIGGERS = {
    "curiosity_gap": {
        "templates": [
            "There's ONE thing about {topic} that changes everything.",
            "Nobody talks about this side of {topic}.",
            "What if everything you know about {topic} is wrong?",
            "The secret behind {topic} will shock you.",
        ],
        "tone": "mysterious, intriguing",
    },
    "controversial_opinion": {
        "templates": [
            "Everything you learned about {topic} is a lie.",
            "Stop doing {topic}. You're wasting time.",
            "I'm going to trigger people: {topic} is dead.",
            "{topic} is actually the worst thing you can do.",
        ],
        "tone": "polarizing, assertive",
    },
    "counterintuitive_statement": {
        "templates": [
            "Want to succeed at {topic}? Do the exact opposite.",
            "The lazy way to master {topic} actually works.",
            "Less effort actually gets you more {topic}.",
            "Stop trying so hard at {topic}. Do this instead.",
        ],
        "tone": "surprising, educational",
    },
    "hidden_truth": {
        "templates": [
            "The elites don't want you to know about {topic}.",
            "This secret {topic} trick is practically illegal.",
            "Here's the {topic} secret they tried to ban.",
            "The industry is hiding this {topic} from you.",
        ],
        "tone": "conspiratorial, urgent",
    },
    "mistake_revelation": {
        "templates": [
            "You are doing {topic} completely wrong.",
            "This {topic} mistake is costing you everything.",
            "Avoid this fatal {topic} mistake at all costs.",
            "If you do this during {topic}, you've already lost.",
        ],
        "tone": "urgent, warning",
    },
    "dark_psychology_insight": {
        "templates": [
            "Your brain is being manipulated by {topic}.",
            "They use {topic} to control how you think.",
            "The dark reason why you're addicted to {topic}.",
            "This {topic} trick forces people to agree with you.",
        ],
        "tone": "manipulative, psychological",
    },
}

# ── Hook Templates (legacy, still used for single hook generation) ───────────

HOOK_STRUCTURES = {
    "pattern_interrupt": [
        "Stop scrolling. {unexpected_statement}",
        "Wait. {unexpected_statement}",
        "Don't skip this. {unexpected_statement}",
        "Pause everything. {unexpected_statement}",
    ],
    "curiosity_gap": [
        "{shocking_claim} And nobody talks about it.",
        "{shocking_claim} Here's what they won't tell you.",
        "{shocking_claim} The reason will surprise you.",
        "There's ONE thing about {topic} that changes everything.",
    ],
    "emotional_trigger": [
        "This {topic} fact will make you rethink everything.",
        "I wish someone told me this about {topic} sooner.",
        "Most people get {topic} completely wrong.",
        "The truth about {topic} is uncomfortable.",
    ],
    "bold_question": [
        "What if everything you know about {topic} is wrong?",
        "Why does nobody talk about this side of {topic}?",
        "Can you handle the truth about {topic}?",
        "What would you do if {topic} disappeared tomorrow?",
    ],
}

# Style-specific hook starters
STYLE_HOOKS = {
    "dark_psychology": {
        "unexpected_statements": [
            "Your brain is being hacked right now.",
            "You've already been manipulated today. Three times.",
            "There's a reason you can't stop watching this.",
            "Every choice you made today was engineered by someone else.",
        ],
        "shocking_claims": [
            "90% of your decisions aren't actually yours.",
            "Your phone knows your next thought before you do.",
            "We're all subjects in the largest psychology experiment ever.",
        ],
    },
    "motivation": {
        "unexpected_statements": [
            "The person you'll become in 6 months is watching you right now.",
            "Pain is temporary. Regret lasts forever.",
            "You're one decision away from a completely different life.",
            "Nobody is coming to save you. That's the good news.",
        ],
        "shocking_claims": [
            "95% of people give up RIGHT before the breakthrough.",
            "The most successful people failed more than you've tried.",
            "Your comfort zone is slowly killing your potential.",
        ],
    },
    "luxury_lifestyle": {
        "unexpected_statements": [
            "Rich people don't work harder. They think differently.",
            "This one habit separates millionaires from everyone else.",
            "Money doesn't buy happiness. It buys freedom.",
            "The wealthy use a different playbook entirely.",
        ],
        "shocking_claims": [
            "The top 1% share one invisible habit.",
            "Your morning routine determines your net worth.",
            "Most millionaires built their fortune on one simple rule.",
        ],
    },
    "stoic_philosophy": {
        "unexpected_statements": [
            "Marcus Aurelius faced this exact same struggle 2000 years ago.",
            "The ancient Stoics solved modern anxiety centuries ago.",
            "Everything you're chasing is already within you.",
            "Suffering is optional. The Stoics proved it.",
        ],
        "shocking_claims": [
            "One Stoic principle can eliminate 80% of your stress.",
            "Ancient Roman emperors used this mental trick daily.",
            "The Stoic secret to happiness has zero side effects.",
        ],
    },
    "viral_facts": {
        "unexpected_statements": [
            "This fact literally rewires how you see the world.",
            "Scientists can't explain this yet.",
            "Your brain is about to be blown.",
            "This changes everything we thought we knew.",
        ],
        "shocking_claims": [
            "There are more trees on Earth than stars in the Milky Way.",
            "Your body replaces itself every 7 years. You're not the same person.",
            "Honey never expires. They found 3000-year-old honey and it was edible.",
        ],
    },
}

DEFAULT_HOOKS = {
    "unexpected_statements": [
        "This will change how you think about everything.",
        "Nobody is talking about this. But they should be.",
        "You need to hear this. Right now.",
        "The truth is hiding in plain sight.",
    ],
    "shocking_claims": [
        "Most people fail because of ONE hidden habit.",
        "The biggest lie you've been told is that you can't change.",
        "Everything popular is wrong. Here's proof.",
    ],
}


# ── A/B Hook Variant Generation (GOD MODE) ──────────────────────────────────


def generate_hook_variants(
    video_subject: str,
    video_style: str = "",
    variant_count: int = 5,
) -> List[Dict[str, str]]:
    """
    Generate 3-5 hook variants for A/B testing.

    Each variant uses a different psychological trigger:
    - fear: urgent, alarming
    - curiosity: mysterious, intriguing
    - shock: explosive, disbelief
    - desire: aspirational, exclusive
    - authority: credible, authoritative

    Returns list of dicts:
        [{
            "hook_text": "...",
            "psych_type": "fear",
            "variant_id": 0,
            "word_count": 12,
            "structure": "pattern_interrupt"
        }]
    """
    triggers = list(PSYCHOLOGICAL_TRIGGERS.keys())
    random.shuffle(triggers)
    selected_triggers = triggers[:min(variant_count, len(triggers))]

    variants = []
    for idx, trigger_name in enumerate(selected_triggers):
        trigger = PSYCHOLOGICAL_TRIGGERS[trigger_name]
        template = random.choice(trigger["templates"])
        hook_text = template.format(topic=video_subject)

        # Keep hooks strictly under 8 words (≈ 2 seconds spoken)
        words = hook_text.split()
        if len(words) > 8:
            hook_text = " ".join(words[:8]) + "..."

        variants.append({
            "hook_text": hook_text,
            "psych_type": trigger_name,
            "variant_id": idx,
            "word_count": len(hook_text.split()),
            "structure": trigger_name,
        })

    logger.info(
        f"generated {len(variants)} hook variants for '{video_subject}': "
        f"{[v['psych_type'] for v in variants]}"
    )
    return variants


def generate_hook_variants_via_llm(
    video_subject: str,
    video_style: str = "",
    variant_count: int = 5,
) -> List[Dict[str, str]]:
    """
    Use LLM to generate diverse hook variants.
    Falls back to template-based generation if LLM fails.
    """
    try:
        from app.services.llm import _generate_response
        import json

        prompt = f"""Generate {variant_count} completely different opening hooks for a viral short-form video.

Topic: "{video_subject}"

Each hook MUST:
- Be under 8 words (≈2 seconds spoken)
- Use a DIFFERENT psychological trigger
- Create an unresolved curiosity gap
- Start with a pattern interrupt

Trigger types to use:
1. CURIOSITY GAP — mysterious, intriguing
2. CONTROVERSIAL OPINION — polarizing, assertive
3. COUNTERINTUITIVE STATEMENT — surprising, educational
4. HIDDEN TRUTH — conspiratorial, urgent
5. MISTAKE REVELATION — urgent, warning
6. DARK PSYCHOLOGY INSIGHT — manipulative, psychological

Return ONLY a JSON array:
[
  {{"hook_text": "...", "psych_type": "curiosity_gap"}},
  {{"hook_text": "...", "psych_type": "controversial_opinion"}}
]"""

        response = _generate_response(prompt)
        if response:
            import re
            # Try to extract JSON
            for pattern in [r'```json\s*(.*?)```', r'```\s*(.*?)```', r'\[.*\]']:
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1) if match.lastindex else match.group(0))
                        if isinstance(data, list) and len(data) > 0:
                            variants = []
                            for idx, item in enumerate(data):
                                if isinstance(item, dict) and "hook_text" in item:
                                    text = item["hook_text"].strip()
                                    variants.append({
                                        "hook_text": text,
                                        "psych_type": item.get("psych_type", "curiosity_gap"),
                                        "variant_id": idx,
                                        "word_count": len(text.split()),
                                        "structure": "llm_generated",
                                    })
                            if variants:
                                logger.info(f"LLM generated {len(variants)} hook variants")
                                return variants
                    except (json.JSONDecodeError, IndexError):
                        continue
    except Exception as e:
        logger.warning(f"LLM hook variant generation failed: {e}")

    return generate_hook_variants(video_subject, video_style, variant_count)


def select_best_hook(
    variants: List[Dict[str, str]],
    preferred_type: str = "",
    feedback_weights: Dict[str, float] = None,
) -> Dict[str, str]:
    """
    Select the best hook from variants.

    If feedback_weights are provided (from feedback loop), use them.
    Otherwise, prefer the specified type, or pick randomly.

    feedback_weights format: {"fear": 0.8, "curiosity": 1.2, ...}
    """
    if not variants:
        return {"hook_text": "", "psych_type": "none", "variant_id": -1,
                "word_count": 0, "structure": "none"}

    if feedback_weights:
        # Score variants by feedback weights
        scored = []
        for v in variants:
            weight = feedback_weights.get(v["psych_type"], 1.0)
            scored.append((weight, v))
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = scored[0][1]
        logger.info(f"selected hook via feedback weights: {selected['psych_type']}")
        return selected

    if preferred_type:
        matching = [v for v in variants if v["psych_type"] == preferred_type]
        if matching:
            return matching[0]

    return random.choice(variants)


# ── Single Hook Generation (legacy API) ─────────────────────────────────────

def generate_hook(
    video_subject: str,
    video_style: str = "",
) -> str:
    """
    Generate an ultra-strong opening hook for the video.

    Structure: [pattern interrupt] → [unexpected statement] → [open loop]

    Returns a 1-3 sentence hook optimized for the first 3 seconds.
    """
    style_data = STYLE_HOOKS.get(video_style, DEFAULT_HOOKS)

    structure_type = random.choice(list(HOOK_STRUCTURES.keys()))
    templates = HOOK_STRUCTURES[structure_type]
    template = random.choice(templates)

    hook = template.format(
        topic=video_subject,
        unexpected_statement=random.choice(style_data["unexpected_statements"]),
        shocking_claim=random.choice(style_data["shocking_claims"]),
    )

    logger.info(f"generated hook ({structure_type}): {hook[:80]}...")
    return hook


def generate_hook_via_llm(
    video_subject: str,
    video_style: str = "",
    video_script: str = "",
) -> str:
    """
    Use the LLM to generate a cinematic hook for the video.
    Falls back to template-based generation if LLM fails.
    """
    from app.services.llm import _generate_response

    style_instruction = ""
    if video_style:
        from app.services import style_presets
        preset = style_presets.get_preset(video_style)
        if preset:
            style_instruction = f"\nStyle: {preset.get('script_tone', '')}"

    prompt = f"""
# Role: Elite Viral Video Hook Generator

## Task:
Generate a SINGLE ultra-strong opening hook (1-3 sentences, under 25 words total) for a short-form video.

## Hook MUST follow this structure:
1. [PATTERN INTERRUPT] — a jarring statement that stops the scroll
2. [UNEXPECTED STATEMENT] — a counterintuitive or shocking claim
3. [OPEN LOOP] — create unresolved curiosity so they MUST keep watching

## Rules:
1. Return ONLY the hook text — no labels, no formatting
2. Under 25 words total
3. Must be spoken naturally (conversational tone)
4. Must create a curiosity gap — viewer needs to watch to get resolution
5. First 3 words must grab attention (pattern interrupt)
6. DO NOT use: "hey guys", "welcome", "in this video"
7. DO NOT reveal the answer in the hook — leave it OPEN
{style_instruction}

## Video Subject: {video_subject}

## Context (if applicable):
{video_script[:200] if video_script else 'N/A'}

Generate the hook now. Return ONLY the raw text.
""".strip()

    try:
        response = _generate_response(prompt)
        if response and "Error: " not in response:
            hook = response.strip().strip("\"'").strip()
            if len(hook) > 10:
                logger.info(f"LLM hook generated: {hook[:80]}...")
                return hook
    except Exception as e:
        logger.warning(f"LLM hook generation failed: {e}")

    logger.info("falling back to template hook generation")
    return generate_hook(video_subject, video_style)


# ── Hook Visual Enhancement ─────────────────────────────────────────────────

HOOK_VISUAL_RULES = {
    "max_scene_duration": 2.0,
    "min_scene_duration": 0.8,
    "preferred_shot_type": "motion",
    "require_high_contrast": True,
    "require_motion": True,
    "search_modifiers": [
        "dramatic lighting", "high contrast", "dynamic motion",
        "cinematic slow motion", "fast movement",
    ],
}


def enhance_hook_visuals(scenes: list, hook_scene_count: int = 2) -> list:
    """
    Mark the first N scenes as hook scenes with aggressive visual rules.
    """
    if not scenes:
        return scenes

    count = min(hook_scene_count, len(scenes))

    for i in range(count):
        scene = scenes[i]
        scene.narrative_role = "hook"
        scene.shot_type = "motion"
        scene.intensity = max(scene.intensity, 0.9)

        modifier = random.choice(HOOK_VISUAL_RULES["search_modifiers"])
        if modifier not in scene.search_query:
            words = scene.search_query.split()
            words.insert(0, modifier.split()[0])
            scene.search_query = " ".join(words[:8])

    logger.info(f"enhanced {count} hook scenes with cinematic visual rules")
    return scenes


def get_hook_clip_duration(scene_index: int, total_hook_scenes: int = 2) -> float:
    """
    Get the ideal clip duration for a hook scene.
    """
    if scene_index == 0:
        return random.uniform(1.5, 2.0)
    elif scene_index < total_hook_scenes:
        return random.uniform(0.8, 1.5)
    return HOOK_VISUAL_RULES["max_scene_duration"]
