"""
Strategic Viral Archetype Library — Predefined viral content structures.

Defines 5+ viral archetypes with intelligent rotation:
- Dark psychological revelation
- Counterintuitive truth
- Success myth destruction
- Secret rule explanation
- Hidden danger warning

Each archetype includes script structure, hook templates, emotion arc,
and controversy level guide.
"""

import random
import time
from typing import Dict, List, Optional, Any
from loguru import logger


# ── Archetype Library ────────────────────────────────────────────────────────

ARCHETYPE_LIBRARY: Dict[str, Dict[str, Any]] = {
    "dark_psychological_revelation": {
        "name": "Dark Psychological Revelation",
        "description": "Reveals hidden psychological mechanisms that control behavior",
        "script_structure": [
            "HOOK: Shocking claim about hidden manipulation",
            "REVEAL: Name the psychological principle",
            "EVIDENCE: Show 2-3 real-world examples",
            "TWIST: Show how the viewer is already affected",
            "MORAL_TENSION: Is knowing this ethical?",
            "CLIFFHANGER: The deeper truth you haven't heard",
        ],
        "hook_templates": [
            "Your brain is being hacked right now. And you don't even know it.",
            "There's a psychological trick that controls 90% of your decisions.",
            "Everything you believe about free will is a carefully designed illusion.",
            "They're using YOUR psychology against you. Here's how.",
        ],
        "emotion_arc": ["shock", "curiosity", "tension", "fear", "revelation", "unresolved"],
        "target_emotions": ["fear", "curiosity", "tension"],
        "controversy_range": [0.5, 0.8],
        "best_niches": ["psychology", "self-improvement", "business", "technology"],
        "pacing": "accelerating",
        "recommended_hook_type": "fear",
    },

    "counterintuitive_truth": {
        "name": "Counterintuitive Truth",
        "description": "Presents evidence that contradicts common beliefs",
        "script_structure": [
            "HOOK: State the common belief, then destroy it",
            "SHOCK: Present the counterintuitive truth",
            "PROOF: Data, studies, or historical evidence",
            "IMPLICATIONS: What this means for the viewer",
            "REFRAME: New way to think about the topic",
            "OPEN_QUESTION: Challenge the viewer to reconsider",
        ],
        "hook_templates": [
            "Everything you were taught about {topic} is backwards.",
            "The opposite of what you think about {topic} is actually true.",
            "Scientists just proved that {topic} works the OPPOSITE way.",
            "What if I told you {topic} is a complete lie? Here's the proof.",
        ],
        "emotion_arc": ["curiosity", "shock", "intrigue", "revelation", "wonder", "questioning"],
        "target_emotions": ["curiosity", "shock"],
        "controversy_range": [0.4, 0.7],
        "best_niches": ["science", "health", "finance", "education"],
        "pacing": "moderate",
        "recommended_hook_type": "curiosity",
    },

    "success_myth_destruction": {
        "name": "Success Myth Destruction",
        "description": "Tears down popular success narratives with harsh reality",
        "script_structure": [
            "HOOK: Name the myth everyone believes",
            "EXPOSURE: Why the myth exists (who benefits)",
            "REALITY: The uncomfortable truth behind success",
            "CASE_STUDY: Real example of myth vs reality",
            "POLARIZE: Divide audience — comfortable lie vs harsh truth",
            "CHALLENGE: Dare the viewer to face reality",
        ],
        "hook_templates": [
            "The #1 success rule is actually destroying your chances.",
            "Every billionaire knows this. But they'll never say it publicly.",
            "The 'hustle culture' is a scam. And the proof is everywhere.",
            "They sold you a dream. Here's what they didn't tell you.",
        ],
        "emotion_arc": ["tension", "anger", "revelation", "empowerment", "determination", "challenge"],
        "target_emotions": ["tension", "motivation"],
        "controversy_range": [0.6, 0.9],
        "best_niches": ["business", "entrepreneurship", "self-improvement", "finance"],
        "pacing": "accelerating",
        "recommended_hook_type": "shock",
    },

    "secret_rule_explanation": {
        "name": "Secret Rule Explanation",
        "description": "Reveals hidden rules that govern systems and success",
        "script_structure": [
            "HOOK: There's a rule nobody talks about",
            "CONTEXT: Why this rule is hidden",
            "EXPLAIN: Break down the rule simply",
            "EXAMPLES: Show the rule in action (3 examples)",
            "APPLICATION: How the viewer can use it",
            "TEASE: The next rule is even more powerful",
        ],
        "hook_templates": [
            "There's an unwritten rule about {topic} that changes everything.",
            "The top 1% follow ONE rule about {topic}. And they never share it.",
            "I discovered a hidden rule about {topic}. It's almost unfair.",
            "The most powerful rule about {topic} was deliberately kept secret.",
        ],
        "emotion_arc": ["curiosity", "intrigue", "revelation", "excitement", "empowerment", "anticipation"],
        "target_emotions": ["curiosity", "desire"],
        "controversy_range": [0.3, 0.6],
        "best_niches": ["business", "psychology", "relationships", "finance", "career"],
        "pacing": "moderate",
        "recommended_hook_type": "curiosity",
    },

    "hidden_danger_warning": {
        "name": "Hidden Danger Warning",
        "description": "Warns about unseen threats to create urgency",
        "script_structure": [
            "HOOK: Urgent warning about something viewer does daily",
            "DANGER: Describe the hidden threat",
            "EVIDENCE: Show proof / statistics / research",
            "SCALE: How widespread the danger is",
            "PROTECTION: What the viewer can do about it",
            "URGENCY: Time is running out",
        ],
        "hook_templates": [
            "WARNING: Something you do every day is silently destroying you.",
            "Stop what you're doing. This affects every single person watching.",
            "There's a danger hiding in {topic} that nobody is talking about.",
            "By the time most people realize THIS about {topic}, it's too late.",
        ],
        "emotion_arc": ["fear", "concern", "alarm", "urgency", "relief", "vigilance"],
        "target_emotions": ["fear", "tension"],
        "controversy_range": [0.4, 0.7],
        "best_niches": ["health", "technology", "finance", "lifestyle", "psychology"],
        "pacing": "fast",
        "recommended_hook_type": "fear",
    },

    "forbidden_knowledge": {
        "name": "Forbidden Knowledge",
        "description": "Presents information as restricted or suppressed",
        "script_structure": [
            "HOOK: This information was meant to stay hidden",
            "BACKSTORY: Why it was suppressed",
            "REVEAL: The forbidden knowledge itself",
            "PROOF: Why it's real and verifiable",
            "POWER: What knowing this gives you",
            "WARNING: Use responsibly",
        ],
        "hook_templates": [
            "This was never supposed to go public.",
            "I'm probably going to get in trouble for sharing this about {topic}.",
            "The information I'm about to share about {topic} was deliberately hidden.",
            "What you're about to learn about {topic} could change everything.",
        ],
        "emotion_arc": ["intrigue", "tension", "revelation", "empowerment", "caution", "mystery"],
        "target_emotions": ["curiosity", "mystery"],
        "controversy_range": [0.5, 0.8],
        "best_niches": ["psychology", "history", "business", "technology", "science"],
        "pacing": "moderate",
        "recommended_hook_type": "authority",
    },

    "identity_challenge": {
        "name": "Identity Challenge",
        "description": "Challenges the viewer's self-image to drive engagement",
        "script_structure": [
            "HOOK: Direct challenge to viewer's identity",
            "MIRROR: Show the behavior pattern",
            "PAIN_POINT: Why this matters deeply",
            "TRANSFORMATION: What the shift looks like",
            "PROOF: Others who made the change",
            "ULTIMATUM: Choose now or stay stuck",
        ],
        "hook_templates": [
            "You're not {positive_trait}. You're just comfortable being average.",
            "The person you think you are and the person you actually are... aren't the same.",
            "Here's the hard truth about {topic} that most people can't handle.",
            "If this video makes you uncomfortable, that's exactly the point.",
        ],
        "emotion_arc": ["discomfort", "recognition", "pain", "hope", "determination", "resolve"],
        "target_emotions": ["tension", "motivation"],
        "controversy_range": [0.5, 0.8],
        "best_niches": ["self-improvement", "fitness", "career", "relationships"],
        "pacing": "accelerating",
        "recommended_hook_type": "shock",
    },
}


# ── Archetype Selection ──────────────────────────────────────────────────────

def get_all_archetypes() -> List[str]:
    """Return all available archetype names."""
    return list(ARCHETYPE_LIBRARY.keys())


def get_archetype(name: str) -> Optional[Dict]:
    """Get a specific archetype definition."""
    return ARCHETYPE_LIBRARY.get(name)


def select_archetype(
    niche: str = "",
    recent_used: List[str] = None,
    preferred_emotions: List[str] = None,
) -> str:
    """
    Intelligently select an archetype, avoiding recent repeats
    and preferring niches/emotions that match.

    Returns archetype name.
    """
    recent = recent_used or []
    candidates = list(ARCHETYPE_LIBRARY.keys())

    # Remove recently used (last 3)
    recent_set = set(recent[-3:])
    filtered = [a for a in candidates if a not in recent_set]
    if not filtered:
        filtered = candidates  # all used recently, reset

    # Score by niche match
    scored = []
    niche_lower = niche.lower() if niche else ""

    for archetype_name in filtered:
        archetype = ARCHETYPE_LIBRARY[archetype_name]
        score = 1.0

        # Niche match bonus
        if niche_lower:
            best_niches = archetype.get("best_niches", [])
            if any(n in niche_lower for n in best_niches):
                score += 2.0
            elif any(niche_lower in n for n in best_niches):
                score += 1.0

        # Emotion match bonus
        if preferred_emotions:
            target_emos = archetype.get("target_emotions", [])
            overlap = len(set(preferred_emotions) & set(target_emos))
            score += overlap * 0.5

        # Add randomness to prevent deterministic patterns
        score += random.uniform(0, 1.0)

        scored.append((archetype_name, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    selected = scored[0][0]

    logger.info(f"selected archetype: {selected} (niche={niche}, avoided={recent_set})")
    return selected


# ── Archetype Application ────────────────────────────────────────────────────

def apply_archetype(
    archetype_name: str,
    topic: str = "",
) -> Dict[str, Any]:
    """
    Apply an archetype to a topic.
    Returns script prompt components and genome seed data.
    """
    archetype = ARCHETYPE_LIBRARY.get(archetype_name)
    if not archetype:
        logger.warning(f"unknown archetype: {archetype_name}, using default")
        archetype_name = "counterintuitive_truth"
        archetype = ARCHETYPE_LIBRARY[archetype_name]

    # Build script structure prompt
    structure_lines = archetype["script_structure"]
    structure_prompt = "\n".join(f"  {i+1}. {line}" for i, line in enumerate(structure_lines))

    # Select a hook template
    hook_templates = archetype["hook_templates"]
    hook = random.choice(hook_templates)
    if "{topic}" in hook:
        hook = hook.replace("{topic}", topic or "this")

    # Emotion arc
    emotion_arc = archetype["emotion_arc"]

    # Controversy range
    controversy = random.uniform(*archetype["controversy_range"])

    result = {
        "archetype_name": archetype_name,
        "archetype_display": archetype["name"],
        "script_structure_prompt": structure_prompt,
        "selected_hook": hook,
        "emotion_arc": emotion_arc,
        "target_emotions": archetype["target_emotions"],
        "controversy_level": round(controversy, 2),
        "recommended_hook_type": archetype.get("recommended_hook_type", "curiosity"),
        "pacing": archetype.get("pacing", "moderate"),
        # Genome seed
        "genome_seed": {
            "archetype": archetype_name,
            "hook_type": archetype.get("recommended_hook_type", "curiosity"),
            "pacing_pattern": archetype.get("pacing", "moderate"),
            "emotion_arc": emotion_arc,
            "controversy_level": round(controversy, 2),
        },
    }

    logger.info(f"applied archetype '{archetype_name}' to topic '{topic}': hook_type={result['recommended_hook_type']}")
    return result


# ── Archetype Performance Tracking ───────────────────────────────────────────

_usage_history: List[Dict] = []


def record_archetype_usage(archetype_name: str, viral_score: float = 0.0):
    """Record that an archetype was used and its resulting score."""
    _usage_history.append({
        "archetype": archetype_name,
        "viral_score": viral_score,
        "timestamp": time.time(),
    })


def get_archetype_performance() -> Dict[str, Dict]:
    """
    Get performance stats for each archetype.
    Returns {archetype_name: {uses, avg_score, last_used}}.
    """
    stats: Dict[str, Dict] = {}

    for entry in _usage_history:
        name = entry["archetype"]
        if name not in stats:
            stats[name] = {"uses": 0, "total_score": 0.0, "last_used": 0}
        stats[name]["uses"] += 1
        stats[name]["total_score"] += entry["viral_score"]
        stats[name]["last_used"] = max(stats[name]["last_used"], entry["timestamp"])

    for name in stats:
        stats[name]["avg_score"] = round(
            stats[name]["total_score"] / max(stats[name]["uses"], 1), 2
        )
        del stats[name]["total_score"]

    return stats
