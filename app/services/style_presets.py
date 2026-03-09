"""
Style Presets for Viral Video Generation.

Each preset defines tone, hooks, pacing, caption style, and BGM mood
to create distinctly different video styles optimized for engagement.
"""

from typing import Dict, Any, Optional
from loguru import logger


# ── Channel Profiles (Multi-Channel Behavior) ───────────────────────────────

CHANNEL_PROFILES = {
    "channel_a": {
        "visual_modifier": "dark",
        "pacing_multiplier": 1.2,
    },
    "channel_b": {
        "visual_modifier": "bright",
        "pacing_multiplier": 0.8,
    }
}

# ── Preset Definitions ──────────────────────────────────────────────────────

STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
    "dark_psychology": {
        "script_tone": (
            "Use a dark, mysterious, and provocative tone. "
            "Leverage dark psychology principles: manipulation awareness, "
            "cognitive biases, hidden persuasion techniques. "
            "Make the viewer feel like they're learning forbidden knowledge. "
            "CRITICAL: Do NOT use overused openers like 'they don't want you to know' or "
            "'nobody is talking about this'. Instead, use SPECIFIC hooks that reference "
            "real brands (Amazon, Netflix, Apple), real studies, or vivid personal scenarios. "
            "Name specific techniques by their scientific names (anchoring, reciprocity, "
            "intermittent reinforcement) for credibility."
        ),
        "hook_examples": [
            "A Harvard study proved 73% of your daily choices aren't actually yours...",
            "Stop scrolling. That urge you just felt? That wasn't you. That was a system.",
            "Amazon, Netflix, and TikTok all use THIS exact psychological exploit...",
            "Your brain just made 3 decisions in the last 10 seconds. None were yours.",
        ],
        "bgm_mood": "dark",
        "caption_style": {
            "power_word_color": "#FF4444",
            "emphasis_words": [
                "manipulation", "manipulat", "control", "secret", "hidden", "dark",
                "trick", "narcissist", "forbidden", "dangerous", "toxic",
                "power", "mind", "psychology", "never", "always",
                "scarcity", "exploit", "panic", "addic", "obsess",
                "calcul", "trap", "victim", "comply", "oblig",
                "brain", "scariest", "darkest", "invisible",
            ],
        },
        "pacing": {
            "hook_cut_duration": 1.5,
            "body_cut_duration": 3,
            "max_scene_duration": 4,
        },
        "comment_bait": [
            "Have you ever been manipulated like this? Comment below…",
            "Which one shocked you the most?",
            "Tag someone who NEEDS to see this…",
            "Do you agree or am I wrong? 👇",
        ],
        "visual_profile": {
            "search_modifiers": ["dark", "shadows", "mysterious"],
            "preferred_shots": ["closeup", "wide"],
            "max_scene_duration": 4,
            "min_scene_duration": 1.5,
            "transition_style": "hard_cut",
        },
    },
    "motivation": {
        "script_tone": (
            "Use an intense, empowering, and motivational tone. "
            "Channel energy like David Goggins, Tony Robbins, or Les Brown. "
            "Use short punchy sentences. Build emotional crescendo. "
            "Make the viewer feel unstoppable. Use phrases like 'stop making excuses', "
            "'grind now, shine later', 'your future self is watching'."
        ),
        "hook_examples": [
            "While you're scrolling, someone is outworking you…",
            "This is the wake-up call you NEED right now…",
            "Your excuses are killing your dreams. Here's why…",
            "In 5 years you'll wish you started TODAY…",
        ],
        "bgm_mood": "epic",
        "caption_style": {
            "power_word_color": "#FFD700",
            "emphasis_words": [
                "grind", "hustle", "unstoppable", "win", "success",
                "failure", "excuses", "discipline", "champion", "strong",
                "never", "give up", "rise", "power", "dream",
            ],
        },
        "pacing": {
            "hook_cut_duration": 1.5,
            "body_cut_duration": 2.5,
            "max_scene_duration": 4,
        },
        "comment_bait": [
            "Save this for when you need motivation 💪",
            "If you needed this today, type 'YES' below 👇",
            "Tag someone who needs to hear this RIGHT NOW…",
            "What's YOUR excuse? Be honest… 👇",
        ],
        "visual_profile": {
            "search_modifiers": ["epic", "powerful", "dynamic"],
            "preferred_shots": ["wide", "motion"],
            "max_scene_duration": 4,
            "min_scene_duration": 1.5,
            "transition_style": "hard_cut",
        },
    },
    "luxury_lifestyle": {
        "script_tone": (
            "Use a sophisticated, aspirational, and luxurious tone. "
            "Describe wealth, success markers, and high-end experiences. "
            "Create desire and aspiration. Use vivid sensory language. "
            "Reference luxury brands, exclusive experiences, and wealth mindset. "
            "Make the viewer crave this lifestyle."
        ),
        "hook_examples": [
            "This is what a $10 million morning routine looks like…",
            "Rich people do THIS every day and you don't…",
            "The habits that separate millionaires from everyone else…",
            "You'll never be rich if you keep doing THIS…",
        ],
        "bgm_mood": "luxury",
        "caption_style": {
            "power_word_color": "#C9A96E",
            "emphasis_words": [
                "luxury", "million", "billion", "exclusive", "premium",
                "wealth", "rich", "expensive", "gold", "diamond",
                "elite", "success", "empire", "freedom", "lifestyle",
            ],
        },
        "pacing": {
            "hook_cut_duration": 2,
            "body_cut_duration": 3.5,
            "max_scene_duration": 5,
        },
        "comment_bait": [
            "Would you live this lifestyle? 💰",
            "Which luxury item is your dream? Comment below…",
            "When I make my first million, I'm buying _____ 👇",
            "Rich or famous? You can only pick one…",
        ],
        "visual_profile": {
            "search_modifiers": ["luxury", "gold", "elegant"],
            "preferred_shots": ["wide", "medium"],
            "max_scene_duration": 5,
            "min_scene_duration": 2.0,
            "transition_style": "fade",
        },
    },
    "stoic_philosophy": {
        "script_tone": (
            "Use a calm, wise, and profound tone inspired by Stoic philosophy. "
            "Reference Marcus Aurelius, Seneca, Epictetus. "
            "Deliver timeless wisdom about emotional control, virtue, and inner peace. "
            "Use contemplative language. "
            "Make the viewer reflect deeply on their life choices."
        ),
        "hook_examples": [
            "Marcus Aurelius wrote this 2000 years ago and it's still true…",
            "A Stoic philosopher said something that will change your life…",
            "The ancient secret to never being angry again…",
            "If you master THIS, nothing can hurt you…",
        ],
        "bgm_mood": "calm",
        "caption_style": {
            "power_word_color": "#A0C4E8",
            "emphasis_words": [
                "wisdom", "virtue", "peace", "control", "stoic",
                "ancient", "philosopher", "truth", "mind", "soul",
                "master", "endure", "courage", "discipline", "silence",
            ],
        },
        "pacing": {
            "hook_cut_duration": 2,
            "body_cut_duration": 4,
            "max_scene_duration": 5,
        },
        "comment_bait": [
            "Which Stoic lesson resonated with you most?",
            "Save this for when life gets hard 🙏",
            "If you needed this today, you're not alone…",
            "What's one thing you need to let go of? 👇",
        ],
        "visual_profile": {
            "search_modifiers": ["ancient", "calm", "contemplative"],
            "preferred_shots": ["wide", "medium"],
            "max_scene_duration": 5,
            "min_scene_duration": 2.0,
            "transition_style": "fade",
        },
    },
    "viral_facts": {
        "script_tone": (
            "Use an energetic, surprising, and fact-driven tone. "
            "Deliver mind-blowing facts that make people share. "
            "Use 'Did you know…', 'Scientists discovered…', '99% of people don't know…'. "
            "Each fact should be genuinely surprising and backed by real data. "
            "Make the viewer feel smarter for watching."
        ),
        "hook_examples": [
            "99% of people don't know this about their own body…",
            "Scientists just discovered something that changes EVERYTHING…",
            "This fact will make you question reality…",
            "I bet you didn't know THIS about the ocean…",
        ],
        "bgm_mood": "upbeat",
        "caption_style": {
            "power_word_color": "#00DDFF",
            "emphasis_words": [
                "fact", "science", "discovered", "impossible", "mind-blowing",
                "percent", "billion", "million", "actually", "truth",
                "real", "shocking", "unbelievable", "research", "proven",
            ],
        },
        "pacing": {
            "hook_cut_duration": 1.5,
            "body_cut_duration": 2.5,
            "max_scene_duration": 3,
        },
        "comment_bait": [
            "Which fact blew your mind? Comment the number 👇",
            "Did you know ALL of these? Be honest…",
            "Share this with someone who loves random facts!",
            "Follow for more mind-blowing facts 🧠",
        ],
        "visual_profile": {
            "search_modifiers": ["science", "colorful", "bright"],
            "preferred_shots": ["closeup", "motion"],
            "max_scene_duration": 3,
            "min_scene_duration": 1.5,
            "transition_style": "hard_cut",
        },
    },
    "minimal_calm": {
        "script_tone": (
            "Use a serene, reflective, and gentle tone. "
            "Speak slowly and let the words breathe. "
            "Use imagery of nature, stillness, and quiet strength. "
            "Make the viewer feel peaceful and present."
        ),
        "hook_examples": [
            "Close your eyes for a moment and just breathe…",
            "In a world of noise, silence is power…",
            "What if the answer was to simply slow down?",
        ],
        "bgm_mood": "ambient",
        "caption_style": {
            "power_word_color": "#88CCAA",
            "emphasis_words": [
                "peace", "breath", "stillness", "calm", "gentle",
                "silence", "presence", "slow", "quiet", "nature",
            ],
        },
        "pacing": {
            "hook_cut_duration": 3,
            "body_cut_duration": 5,
            "max_scene_duration": 6,
        },
        "comment_bait": [
            "Did this bring you peace? 🕊️",
            "Save this for a hard day 💚",
            "What gives you calm? Share below…",
        ],
        "visual_profile": {
            "search_modifiers": ["peaceful", "soft", "minimal"],
            "preferred_shots": ["wide", "medium"],
            "max_scene_duration": 6,
            "min_scene_duration": 3.0,
            "transition_style": "fade",
        },
    },
    "high_energy": {
        "script_tone": (
            "Use explosive, high-octane energy. "
            "Rapid-fire delivery. Every sentence hits like a punch. "
            "Use action words, urgency, and adrenaline. "
            "Make the viewer's heart race."
        ),
        "hook_examples": [
            "STOP scrolling. You need to see this NOW.",
            "This changes EVERYTHING and nobody is talking about it…",
            "You have 3 seconds to decide your future…",
        ],
        "bgm_mood": "intense",
        "caption_style": {
            "power_word_color": "#FF3333",
            "emphasis_words": [
                "now", "stop", "go", "run", "fight",
                "win", "destroy", "crush", "dominate", "attack",
                "explode", "fire", "insane", "crazy", "massive",
            ],
        },
        "pacing": {
            "hook_cut_duration": 1.0,
            "body_cut_duration": 1.5,
            "max_scene_duration": 2.5,
        },
        "comment_bait": [
            "Type 🔥 if this hit HARD",
            "Send this to someone who needs a WAKE UP CALL",
            "Are you IN or are you OUT? 👇",
        ],
        "visual_profile": {
            "search_modifiers": ["action", "fast", "dynamic"],
            "preferred_shots": ["motion", "closeup"],
            "max_scene_duration": 2.5,
            "min_scene_duration": 1.0,
            "transition_style": "hard_cut",
        },
    },
}

# ── Public API ───────────────────────────────────────────────────────────────


def get_preset(style_name: str) -> Optional[Dict[str, Any]]:
    """Get a style preset by name. Returns None if not found."""
    preset = STYLE_PRESETS.get(style_name)
    if not preset:
        logger.warning(f"style preset '{style_name}' not found, available: {list(STYLE_PRESETS.keys())}")
    return preset


def get_all_preset_names() -> list:
    """Return list of all available preset names."""
    return list(STYLE_PRESETS.keys())


def get_preset_display_names() -> Dict[str, str]:
    """Return mapping of preset keys to human-readable display names."""
    return {
        "dark_psychology": "🧠 Dark Psychology",
        "motivation": "🔥 Motivation",
        "luxury_lifestyle": "💎 Luxury Lifestyle",
        "stoic_philosophy": "📜 Stoic Philosophy",
        "viral_facts": "🤯 Viral Facts",
        "minimal_calm": "🕊️ Minimal Calm",
        "high_energy": "⚡ High Energy",
    }


def get_pacing(style_name: str, channel_profile: str = None) -> Dict[str, float]:
    """Get pacing config for a style, applying channel profile overrides if specified. Falls back to defaults if not found."""
    default_pacing = {
        "hook_cut_duration": 2.0,
        "body_cut_duration": 3.0,
        "max_scene_duration": 5.0,
    }
    preset = get_preset(style_name)
    pacing = preset.get("pacing", default_pacing) if preset else default_pacing

    if channel_profile and channel_profile in CHANNEL_PROFILES:
        mult = CHANNEL_PROFILES[channel_profile]["pacing_multiplier"]
        pacing = {
            "hook_cut_duration": max(0.5, pacing.get("hook_cut_duration", 2) * mult),
            "body_cut_duration": max(0.5, pacing.get("body_cut_duration", 3) * mult),
            "max_scene_duration": max(0.5, pacing.get("max_scene_duration", 5) * mult),
        }
        logger.info(f"applied channel profile '{channel_profile}' to pacing: mult={mult}")

    return pacing


def get_comment_bait(style_name: str) -> list:
    """Get comment bait phrases for a style."""
    preset = get_preset(style_name)
    if preset:
        return preset.get("comment_bait", [])
    return [
        "What do you think? Comment below 👇",
        "Do you agree?",
        "Save this for later ❤️",
    ]


def get_caption_style(style_name: str) -> Dict[str, Any]:
    """Get caption styling config for a style."""
    default_style = {
        "power_word_color": "#FFFF00",
        "emphasis_words": [],
    }
    preset = get_preset(style_name)
    if preset:
        return preset.get("caption_style", default_style)
    return default_style


def get_visual_profile(style_name: str, channel_profile: str = None) -> Optional[Dict[str, Any]]:
    """Get visual search profile for a style. Applies channel profile overrides. Used by emotion-aware visual matching."""
    default_profile = {
        "search_modifiers": ["cinematic"],
        "preferred_shots": ["wide", "medium", "closeup", "motion"],
        "max_scene_duration": 5,
        "min_scene_duration": 1.5,
        "transition_style": "shuffle",
    }
    preset = get_preset(style_name)
    profile = preset.get("visual_profile", default_profile) if preset else default_profile

    if channel_profile and channel_profile in CHANNEL_PROFILES:
        vis_mod = CHANNEL_PROFILES[channel_profile]["visual_modifier"]
        # prepend the visual modifier from the channel
        mods = profile.get("search_modifiers", []).copy()
        if vis_mod not in mods:
            mods.insert(0, vis_mod)
        profile["search_modifiers"] = mods
        logger.info(f"applied channel profile '{channel_profile}' to visual_profile: added modifier '{vis_mod}'")

    return profile
