"""
Trend Intelligence Engine — Topic pool generation with multi-signal scoring.

Scores each candidate topic across three dimensions:
  - Novelty:             How unique vs. recent topics (0-100)
  - Emotional Intensity: Strength of emotional trigger words (0-100)
  - Curiosity Potential:   Open loops / mystery / information gaps (0-100)

Combines with existing viral_score and archetype systems for a unified
intelligence layer that feeds the scheduler and batch generator.

Usage:
    from app.services.trend_intelligence import generate_scored_topics
    topics = generate_scored_topics(niche="psychology", count=20)
    # Returns sorted by composite score, each with full breakdown
"""

import hashlib
import os
import json
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


# ── Scoring Weights ──────────────────────────────────────────────────────────

SCORE_WEIGHTS = {
    "novelty": 0.30,
    "emotional_intensity": 0.35,
    "curiosity_potential": 0.35,
}

# ── Keyword Libraries ────────────────────────────────────────────────────────

EMOTION_TRIGGERS = {
    "high": [
        "terrifying", "shocking", "devastating", "heartbreaking", "explosive",
        "life-changing", "mind-blowing", "dangerous", "forbidden", "outrageous",
        "unbelievable", "devastating", "brutal", "ruthless", "deadly",
        "nightmare", "trauma", "rage", "obsession", "panic",
    ],
    "medium": [
        "surprising", "important", "powerful", "intense", "dramatic",
        "controversial", "hidden", "secret", "unknown", "overlooked",
        "underrated", "misunderstood", "ignored", "disrupting", "changing",
    ],
    "low": [
        "interesting", "cool", "nice", "good", "useful",
        "helpful", "simple", "basic", "common", "popular",
    ],
}

CURIOSITY_HOOKS = [
    "nobody tells you", "the truth about", "what they don't want",
    "the real reason", "you won't believe", "most people don't know",
    "the secret behind", "what happens when", "why nobody talks about",
    "the one thing", "before it's too late", "what they hide",
    "the hidden", "they never tell you", "the untold",
    "what really happens", "the dark side of", "the shocking truth",
    "the mistake everyone makes", "the lie you've been told",
]

NOVELTY_PENALTY_PHRASES = [
    "top 10", "top 5", "you need to know", "beginner's guide",
    "how to start", "for beginners", "step by step", "tutorial",
    "in 2024", "in 2025", "in 2026",
]


# ── Topic Scoring ────────────────────────────────────────────────────────────

@dataclass
class ScoredTopic:
    """A topic with full multi-signal score breakdown."""
    topic: str = ""
    niche: str = ""
    novelty: float = 0.0
    emotional_intensity: float = 0.0
    curiosity_potential: float = 0.0
    composite_score: float = 0.0
    archetype: str = ""
    emotion_tags: List[str] = field(default_factory=list)
    source: str = "generated"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_novelty(topic: str, recent_topics: List[str] = None) -> float:
    """
    Score topic novelty (0-100).

    Higher for:
      - Unique phrasing not seen in recent topics
      - Absence of overused template phrases
      - Longer, more specific topics

    Lower for:
      - Close similarity to recent topics
      - Generic "top X" or "beginner" patterns
    """
    score = 70.0  # Base novelty

    # Penalty for overused patterns
    topic_lower = topic.lower()
    for phrase in NOVELTY_PENALTY_PHRASES:
        if phrase in topic_lower:
            score -= 12.0

    # Bonus for specificity (longer = more specific)
    word_count = len(topic.split())
    if word_count >= 8:
        score += 10
    elif word_count >= 5:
        score += 5
    elif word_count <= 3:
        score -= 15

    # Deduplicate against recent topics
    if recent_topics:
        for recent in recent_topics:
            similarity = _jaccard_similarity(topic_lower, recent.lower())
            if similarity > 0.6:
                score -= 30  # Heavy penalty for near-duplicate
            elif similarity > 0.3:
                score -= 10

    return max(0.0, min(100.0, score))


def score_emotional_intensity(topic: str) -> float:
    """
    Score emotional trigger strength (0-100).

    Scans for emotion trigger words at three intensity tiers.
    """
    topic_lower = topic.lower()
    score = 30.0  # Base

    high_count = sum(1 for w in EMOTION_TRIGGERS["high"] if w in topic_lower)
    med_count = sum(1 for w in EMOTION_TRIGGERS["medium"] if w in topic_lower)
    low_count = sum(1 for w in EMOTION_TRIGGERS["low"] if w in topic_lower)

    score += high_count * 20
    score += med_count * 10
    score += low_count * 3

    # Bonus for question marks and exclamation marks
    score += topic.count("?") * 8
    score += topic.count("!") * 5

    # Bonus for ALL CAPS words
    caps_words = sum(1 for w in topic.split() if w.isupper() and len(w) > 2)
    score += caps_words * 6

    return max(0.0, min(100.0, score))


def score_curiosity_potential(topic: str) -> float:
    """
    Score curiosity gap / open loop density (0-100).

    Higher for topics that create information gaps
    the viewer needs to resolve by watching.
    """
    topic_lower = topic.lower()
    score = 25.0  # Base

    hook_count = sum(1 for h in CURIOSITY_HOOKS if h in topic_lower)
    score += hook_count * 18

    # Questions are inherently curiosity-creating
    if "?" in topic:
        score += 15
    if topic_lower.startswith("why"):
        score += 12
    if topic_lower.startswith("how"):
        score += 8
    if topic_lower.startswith("what"):
        score += 10

    # Negation creates curiosity ("never", "don't", "can't")
    negations = ["never", "don't", "can't", "won't", "shouldn't", "not"]
    negation_count = sum(1 for n in negations if n in topic_lower)
    score += negation_count * 7

    # Numbers create specificity and curiosity
    import re
    numbers = re.findall(r'\d+', topic)
    if numbers:
        score += 8

    return max(0.0, min(100.0, score))


def score_topic(
    topic: str,
    niche: str = "",
    recent_topics: List[str] = None,
) -> ScoredTopic:
    """Score a single topic across all dimensions and compute composite."""
    novelty = score_novelty(topic, recent_topics)
    emotional = score_emotional_intensity(topic)
    curiosity = score_curiosity_potential(topic)

    composite = (
        novelty * SCORE_WEIGHTS["novelty"]
        + emotional * SCORE_WEIGHTS["emotional_intensity"]
        + curiosity * SCORE_WEIGHTS["curiosity_potential"]
    )

    # Detect emotion tags
    emotion_tags = []
    topic_lower = topic.lower()
    tag_map = {
        "fear": ["terrifying", "dangerous", "nightmare", "panic", "deadly"],
        "curiosity": ["secret", "hidden", "truth", "nobody", "mystery"],
        "anger": ["outrageous", "rage", "unfair", "injustice"],
        "surprise": ["shocking", "unbelievable", "mind-blowing", "explosive"],
        "aspiration": ["success", "wealthy", "powerful", "achieve", "millionaire"],
    }
    for tag, keywords in tag_map.items():
        if any(k in topic_lower for k in keywords):
            emotion_tags.append(tag)
    if not emotion_tags:
        emotion_tags = ["neutral"]

    return ScoredTopic(
        topic=topic,
        niche=niche,
        novelty=round(novelty, 1),
        emotional_intensity=round(emotional, 1),
        curiosity_potential=round(curiosity, 1),
        composite_score=round(composite, 1),
        emotion_tags=emotion_tags,
    )


# ── Topic Pool Generation ────────────────────────────────────────────────────

def generate_scored_topics(
    niche: str = "psychology",
    count: int = 20,
    min_score: float = 40.0,
    recent_topics: List[str] = None,
) -> List[ScoredTopic]:
    """
    Generate a scored topic pool.

    Uses batch_generator's topic system, then scores each topic.
    Returns topics sorted by composite score (descending), filtered by min_score.
    """
    # Get raw topics from existing batch system
    try:
        from app.services.batch_generator import generate_batch_topics
        raw_topics = generate_batch_topics(niche=niche, count=count * 2)
        topic_strings = [t.get("topic", "") for t in raw_topics if t.get("topic")]
    except Exception as e:
        logger.warning(f"[TrendIntel] Batch topic generation failed: {e}")
        topic_strings = _emergency_topics(niche, count * 2)

    # Score each topic
    scored = []
    for topic_str in topic_strings:
        st = score_topic(topic_str, niche=niche, recent_topics=recent_topics)
        if st.composite_score >= min_score:
            scored.append(st)

    # Sort by composite score
    scored.sort(key=lambda x: x.composite_score, reverse=True)

    # Assign archetypes from existing library
    try:
        from app.services.viral_archetypes import select_archetype
        used_archetypes = []
        for st in scored:
            arch = select_archetype(
                niche=niche,
                recent_used=used_archetypes[-3:],
                preferred_emotions=st.emotion_tags,
            )
            st.archetype = arch
            used_archetypes.append(arch)
    except Exception as e:
        logger.warning(f"[TrendIntel] Archetype assignment failed: {e}")

    result = scored[:count]
    logger.info(
        f"[TrendIntel] Generated {len(result)} topics "
        f"(niche={niche}, min_score={min_score}, "
        f"avg={sum(t.composite_score for t in result)/len(result):.1f})"
        if result else f"[TrendIntel] No topics above threshold {min_score}"
    )
    return result


def distribute_to_channels(
    topics: List[ScoredTopic],
    channel_ids: List[str],
    channel_niches: Dict[str, str] = None,
) -> Dict[str, List[ScoredTopic]]:
    """
    Distribute scored topics across channels.

    Strategy:
      - Match topic emotion tags to channel niche when possible
      - Round-robin for remaining topics
      - Ensure no channel gets >60% of topics
    """
    if not channel_ids:
        return {}

    assignment: Dict[str, List[ScoredTopic]] = {cid: [] for cid in channel_ids}
    max_per_channel = max(1, int(len(topics) * 0.6))

    # Phase 1: Niche-affinity matching
    unassigned = []
    if channel_niches:
        for topic in topics:
            best_channel = None
            best_overlap = 0
            for cid, niche in channel_niches.items():
                if cid not in assignment:
                    continue
                overlap = len(set(topic.emotion_tags) & {niche}) + (
                    1 if topic.niche == niche else 0
                )
                if overlap > best_overlap and len(assignment[cid]) < max_per_channel:
                    best_overlap = overlap
                    best_channel = cid
            if best_channel and best_overlap > 0:
                assignment[best_channel].append(topic)
            else:
                unassigned.append(topic)
    else:
        unassigned = list(topics)

    # Phase 2: Round-robin for remaining
    idx = 0
    for topic in unassigned:
        for _ in range(len(channel_ids)):
            cid = channel_ids[idx % len(channel_ids)]
            idx += 1
            if len(assignment[cid]) < max_per_channel:
                assignment[cid].append(topic)
                break

    return assignment


# ── Helpers ──────────────────────────────────────────────────────────────────

def _jaccard_similarity(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _emergency_topics(niche: str, count: int) -> List[str]:
    """Last-resort topics when all generation systems fail."""
    templates = [
        f"the dark truth about {niche} nobody talks about",
        f"why everything you know about {niche} is wrong",
        f"the hidden rules of {niche} that change everything",
        f"shocking facts about {niche} that will surprise you",
        f"{niche} secrets the experts don't want you to know",
        f"the biggest mistake people make with {niche}",
        f"how {niche} actually works behind the scenes",
        f"the uncomfortable truth about {niche} in modern life",
    ]
    return (templates * ((count // len(templates)) + 1))[:count]
