"""
Trend-Aware Topic Generation System — GOD MODE.

Provides LLM-powered topic generation, emotion profiling, controversy scoring,
and viral score gating. Only top-scoring topics enter production.
"""

import json
import os
import random
from typing import Dict, List, Optional, Any

from loguru import logger

from app.utils import utils


# ── Emotion Signal Mapping ──────────────────────────────────────────────────

EMOTION_SIGNALS = {
    "fear": {
        "keywords": ["danger", "warning", "risk", "threat", "scary", "terrif", "dark",
                      "death", "kill", "destroy", "toxic", "poison", "trap"],
        "weight": 0.15,
    },
    "curiosity": {
        "keywords": ["secret", "hidden", "mystery", "unknown", "why", "how", "what",
                      "truth", "reveal", "discover", "strange", "weird", "bizarre"],
        "weight": 0.12,
    },
    "desire": {
        "keywords": ["rich", "money", "wealth", "success", "luxury", "dream", "freedom",
                      "power", "elite", "million", "billion", "lifestyle"],
        "weight": 0.10,
    },
    "shock": {
        "keywords": ["shocking", "unbelievable", "insane", "crazy", "mind-blowing",
                      "impossible", "banned", "forbidden", "exposed", "never"],
        "weight": 0.13,
    },
    "tension": {
        "keywords": ["manipulat", "control", "exploit", "hack", "trick", "lie",
                      "betray", "conflict", "battle", "war", "fight"],
        "weight": 0.11,
    },
}


# ── Trend Source Abstraction ─────────────────────────────────────────────────


class TrendSource:
    """Base class for trend data sources."""

    def fetch_trends(self, niche: str = "", count: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch trending topics. Returns list of dicts with:
        - topic: str
        - score: float (0-1 viral potential)
        - niche: str
        - source: str
        - emotion_profile: List[str]
        - risk_level: str
        """
        raise NotImplementedError


class KeywordListSource(TrendSource):
    """
    Reads trending topics from a local file.
    Simple but effective — allows manual curation of high-performing topics.
    """

    def __init__(self, file_path: str = ""):
        if not file_path:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(root_dir, "resource", "trending_topics.txt")
        self.file_path = file_path

    def fetch_trends(self, niche: str = "", count: int = 10) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            logger.warning(f"trending topics file not found: {self.file_path}")
            return []

        topics = []
        current_niche = "general"

        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Lines starting with [category] define the niche
                if line.startswith("[") and line.endswith("]"):
                    current_niche = line[1:-1].strip().lower()
                    continue

                topics.append({
                    "topic": line,
                    "score": 0.5,
                    "niche": current_niche,
                    "source": "keyword_list",
                })

        # Filter by niche if specified
        if niche:
            niche_lower = niche.lower()
            filtered = [t for t in topics if niche_lower in t["niche"] or t["niche"] == "general"]
            if filtered:
                topics = filtered

        # Score, profile, and return top results
        scored = score_topics(topics)
        for t in scored:
            profile = score_emotion_profile(t["topic"])
            t["emotion_profile"] = profile["emotions"]
            t["risk_level"] = profile["risk_level"]
        return scored[:count]


class LLMTopicSource(TrendSource):
    """
    Uses LLM to generate niche-specific viral topic ideas with
    emotion profiling and controversy scoring.
    """

    def fetch_trends(self, niche: str = "", count: int = 10) -> List[Dict[str, Any]]:
        try:
            from app.services import llm as llm_service
        except ImportError:
            logger.warning("LLM service not available for topic generation")
            return []

        niche_text = niche if niche else "general viral content"
        prompt = f"""Generate {count} highly viral short-form video topic ideas for the niche: "{niche_text}".

Each topic must be:
- Emotionally charged (trigger curiosity, fear, desire, or shock)
- Controversy-adjacent (provoke debate without being offensive)
- Optimized for short-form video (TikTok/Reels/Shorts)

Return ONLY a JSON array of objects with these fields:
- "topic": the video title/subject (5-12 words)
- "emotion_profile": array of 1-3 emotions from [fear, curiosity, desire, shock, tension]
- "risk_level": one of "low", "medium", "high"

Example:
[
  {{"topic": "dark psychology tricks used by billionaires", "emotion_profile": ["curiosity", "tension"], "risk_level": "medium"}},
  {{"topic": "why 95% of people will never be rich", "emotion_profile": ["shock", "desire"], "risk_level": "high"}}
]

Return ONLY the JSON array, no explanation."""

        try:
            response = llm_service._generate_response(prompt)
            if not response:
                return []

            # Extract JSON array from response
            parsed = _extract_json_from_llm(response)
            if not parsed:
                return []

            topics = []
            for item in parsed:
                if not isinstance(item, dict) or "topic" not in item:
                    continue
                topic_text = item["topic"].strip()
                emotion_profile = item.get("emotion_profile", [])
                risk_level = item.get("risk_level", "medium")

                # Validate emotion_profile
                valid_emotions = {"fear", "curiosity", "desire", "shock", "tension"}
                emotion_profile = [e for e in emotion_profile if e in valid_emotions]
                if not emotion_profile:
                    profile = score_emotion_profile(topic_text)
                    emotion_profile = profile["emotions"]

                # Validate risk_level
                if risk_level not in ("low", "medium", "high"):
                    risk_level = "medium"

                topics.append({
                    "topic": topic_text,
                    "score": 0.5,
                    "niche": niche or "general",
                    "source": "llm",
                    "emotion_profile": emotion_profile,
                    "risk_level": risk_level,
                })

            scored = score_topics(topics)
            logger.info(f"LLM generated {len(scored)} viral topics for niche '{niche_text}'")
            return scored[:count]

        except Exception as e:
            logger.error(f"LLM topic generation failed: {e}")
            return []


# ── Scoring Logic ────────────────────────────────────────────────────────────

VIRAL_BOOSTERS = [
    "secret", "truth", "hidden", "never", "always", "hack", "trick",
    "mistake", "rule", "psychology", "science", "money", "brain",
    "rich", "power", "change", "dark", "shocking", "best", "worst",
    "why", "how", "what", "stop", "start", "before", "after",
]


def score_topics(topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Score topics based on viral potential indicators:
    - Presence of viral booster keywords
    - Question format (higher engagement)
    - Length optimization (not too short, not too long)
    - Emotion signal strength
    """
    for topic in topics:
        score = topic.get("score", 0.5)
        text = topic["topic"].lower()

        # Boost for viral keywords
        keyword_hits = sum(1 for kw in VIRAL_BOOSTERS if kw in text)
        score += min(keyword_hits * 0.1, 0.3)

        # Boost for question format
        if "?" in topic["topic"]:
            score += 0.1

        # Boost for optimal length (5-12 words optimal for titles)
        word_count = len(text.split())
        if 5 <= word_count <= 12:
            score += 0.1
        elif word_count < 3 or word_count > 20:
            score -= 0.1

        # Boost for number presence (e.g., "5 tricks", "3 secrets")
        if any(c.isdigit() for c in text):
            score += 0.05

        # Boost for emotion signal strength
        emotion_score = _calculate_emotion_score(text)
        score += emotion_score

        topic["score"] = min(max(score, 0.0), 1.0)

    topics.sort(key=lambda t: t["score"], reverse=True)
    return topics


def _calculate_emotion_score(text: str) -> float:
    """Calculate emotion-based score boost from text content."""
    text_lower = text.lower()
    total = 0.0
    for emotion, data in EMOTION_SIGNALS.items():
        hits = sum(1 for kw in data["keywords"] if kw in text_lower)
        if hits > 0:
            total += min(hits * data["weight"], 0.2)
    return min(total, 0.3)


def score_emotion_profile(topic_text: str) -> Dict[str, Any]:
    """
    Score a topic for emotional polarity and risk level.
    
    Returns:
        {
            "emotions": ["curiosity", "tension"],
            "risk_level": "high" | "medium" | "low",
            "emotion_scores": {"curiosity": 0.3, "tension": 0.2, ...}
        }
    """
    text_lower = topic_text.lower()
    emotion_scores = {}

    for emotion, data in EMOTION_SIGNALS.items():
        hits = sum(1 for kw in data["keywords"] if kw in text_lower)
        emotion_scores[emotion] = min(hits * data["weight"], 1.0)

    # Top emotions (those with score > 0)
    sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
    top_emotions = [e for e, s in sorted_emotions if s > 0][:3]

    # If no emotions detected, default to curiosity
    if not top_emotions:
        top_emotions = ["curiosity"]

    # Risk level based on controversy indicators
    controversy_keywords = [
        "manipulat", "exploit", "dark", "toxic", "kill", "destroy",
        "banned", "forbidden", "lie", "cheat", "steal", "controversial",
    ]
    controversy_hits = sum(1 for kw in controversy_keywords if kw in text_lower)
    if controversy_hits >= 3:
        risk_level = "high"
    elif controversy_hits >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "emotions": top_emotions,
        "risk_level": risk_level,
        "emotion_scores": emotion_scores,
    }


def filter_top_scoring(
    topics: List[Dict[str, Any]],
    threshold: float = 0.7,
) -> List[Dict[str, Any]]:
    """
    Filter topics by viral score threshold.
    Only topics scoring >= threshold enter production.
    
    If no topics pass the threshold, returns the top 3 regardless.
    """
    passing = [t for t in topics if t.get("score", 0) >= threshold]
    if passing:
        logger.info(f"{len(passing)}/{len(topics)} topics passed viral threshold {threshold}")
        return passing

    # Fallback: return top 3 even if below threshold
    logger.warning(f"no topics passed threshold {threshold}, returning top 3")
    return sorted(topics, key=lambda t: t.get("score", 0), reverse=True)[:3]


# ── Topic Clustering ─────────────────────────────────────────────────────────

TOPIC_CLUSTER_SEEDS = {
    "fear_finance": {
        "keywords": ["money", "debt", "broke", "crash", "recession", "poverty", "scam"],
        "emotion_wave": "fear-based finance",
    },
    "dark_self_improvement": {
        "keywords": ["manipulation", "dark", "psychology", "control", "exploit", "hack", "mind"],
        "emotion_wave": "dark self-improvement",
    },
    "stoic_masculinity": {
        "keywords": ["stoic", "discipline", "masculine", "strength", "warrior", "mindset", "grind"],
        "emotion_wave": "stoic masculinity",
    },
    "hidden_psychology": {
        "keywords": ["psychology", "brain", "cognitive", "bias", "trick", "subconscious", "influence"],
        "emotion_wave": "hidden psychology truths",
    },
    "conspiracy_tech": {
        "keywords": ["algorithm", "surveillance", "data", "privacy", "tracking", "ai", "control"],
        "emotion_wave": "tech paranoia",
    },
    "wealth_secrets": {
        "keywords": ["millionaire", "rich", "wealth", "passive", "invest", "compound", "freedom"],
        "emotion_wave": "wealth obsession",
    },
}


def generate_topic_clusters(
    niche: str = "",
    count: int = 5,
) -> List[Dict[str, Any]]:
    """
    Group related topics into thematic clusters.
    Each cluster has a name, related keywords, and emotional wave label.

    Returns list of clusters with generated topic ideas per cluster.
    """
    clusters = []
    niche_lower = niche.lower() if niche else ""

    for cluster_name, cluster_data in TOPIC_CLUSTER_SEEDS.items():
        # Filter by niche if specified
        if niche_lower and not any(kw in niche_lower for kw in cluster_data["keywords"][:3]):
            continue

        # Generate topic ideas from cluster keywords
        keywords = cluster_data["keywords"]
        topic_combos = []
        for i in range(min(count, 3)):
            kw_sample = random.sample(keywords, min(3, len(keywords)))
            topic_combos.append(" ".join(kw_sample))

        clusters.append({
            "cluster_name": cluster_name,
            "emotion_wave": cluster_data["emotion_wave"],
            "keywords": keywords,
            "sample_topics": topic_combos,
        })

    if not clusters:
        # Default: return all clusters if niche didn't match
        for cluster_name, cluster_data in list(TOPIC_CLUSTER_SEEDS.items())[:count]:
            clusters.append({
                "cluster_name": cluster_name,
                "emotion_wave": cluster_data["emotion_wave"],
                "keywords": cluster_data["keywords"],
                "sample_topics": [" ".join(random.sample(cluster_data["keywords"], 3))],
            })

    logger.info(f"generated {len(clusters)} topic clusters for niche '{niche}'")
    return clusters[:count]


def score_novelty_vs_saturation(topic: str) -> float:
    """
    Score a topic on novelty (0.0 = saturated, 1.0 = fresh).
    Checks inverse frequency against genome store history.
    """
    try:
        from app.services.content_genome import _get_store as get_genome_store
        store = get_genome_store()
        genomes = store.load_all(limit=100)
    except Exception:
        return 0.8  # default high novelty if no history

    if not genomes:
        return 1.0  # everything is novel with no history

    topic_lower = topic.lower()
    topic_words = set(topic_lower.split())

    match_count = 0
    for genome in genomes:
        niche = getattr(genome, "niche_category", "").lower()
        if not niche:
            continue
        niche_words = set(niche.split())
        overlap = len(topic_words & niche_words)
        if overlap >= 2 or topic_lower in niche or niche in topic_lower:
            match_count += 1

    # Inverse frequency: more matches = lower novelty
    novelty = max(0.0, 1.0 - (match_count / max(len(genomes), 1)) * 5)
    return round(novelty, 3)


def detect_emotional_waves() -> List[Dict[str, Any]]:
    """
    Identify emerging emotional patterns from recent genome data.
    Detects trends like 'fear-based finance', 'dark self-improvement', etc.

    Returns list of detected waves with strength scores.
    """
    try:
        from app.services.content_genome import _get_store as get_genome_store
        store = get_genome_store()
        genomes = store.load_all(limit=100)
    except Exception:
        genomes = []

    wave_scores: Dict[str, float] = {}

    for cluster_name, cluster_data in TOPIC_CLUSTER_SEEDS.items():
        wave_label = cluster_data["emotion_wave"]
        keywords = cluster_data["keywords"]
        match_strength = 0.0

        for genome in genomes:
            niche = getattr(genome, "niche_category", "").lower()
            emotion_arc = getattr(genome, "emotion_arc", [])
            hits = sum(1 for kw in keywords if kw in niche)
            if hits > 0:
                # Weight by performance
                score = getattr(genome, "viral_score", 0)
                match_strength += hits * (1 + score / 100)

        wave_scores[wave_label] = round(match_strength, 2)

    # Sort by strength and return emerging waves
    sorted_waves = sorted(wave_scores.items(), key=lambda x: x[1], reverse=True)
    result = [{"wave": name, "strength": strength} for name, strength in sorted_waves if strength > 0]

    if result:
        logger.info(f"detected {len(result)} emotional waves, top: {result[0]['wave']}")

    return result


def gate_topic(
    topic: str,
    min_novelty: float = 0.3,
    min_emotion: float = 0.1,
) -> Dict[str, Any]:
    """
    Composite gate: only high novelty + high emotional score topics pass.

    Returns:
        {
            "passed": True/False,
            "novelty_score": 0.85,
            "emotion_score": 0.65,
            "composite_score": 0.75,
            "reason": "" or description of why it failed,
        }
    """
    novelty = score_novelty_vs_saturation(topic)
    emotion_data = score_emotion_profile(topic)
    emotion_score = sum(emotion_data.get("emotion_scores", {}).values())
    emotion_score = min(emotion_score, 1.0)

    composite = (novelty * 0.5) + (emotion_score * 0.5)

    result = {
        "passed": True,
        "novelty_score": novelty,
        "emotion_score": round(emotion_score, 3),
        "composite_score": round(composite, 3),
        "reason": "",
    }

    if novelty < min_novelty:
        result["passed"] = False
        result["reason"] = f"novelty too low: {novelty:.2f} < {min_novelty}"
    elif emotion_score < min_emotion:
        result["passed"] = False
        result["reason"] = f"emotion score too low: {emotion_score:.2f} < {min_emotion}"

    if result["passed"]:
        logger.info(f"topic GATED IN: '{topic}' (novelty={novelty:.2f}, emotion={emotion_score:.2f})")
    else:
        logger.warning(f"topic GATED OUT: '{topic}' — {result['reason']}")

    return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_json_from_llm(text: str) -> Optional[list]:
    """Extract a JSON array from LLM response text."""
    if not text:
        return None
    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    import re
    patterns = [
        r'```json\s*(.*?)```',
        r'```\s*(.*?)```',
        r'\[.*\]',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1) if match.lastindex else match.group(0))
                if isinstance(result, list):
                    return result
            except (json.JSONDecodeError, IndexError):
                continue
    return None


# ── Public API ───────────────────────────────────────────────────────────────

_sources: List[TrendSource] = []


def _ensure_sources():
    """Initialize default sources if none registered."""
    global _sources
    if not _sources:
        _sources.append(KeywordListSource())
        _sources.append(LLMTopicSource())


def register_source(source: TrendSource):
    """Register a new trend data source."""
    _sources.append(source)


def suggest_topics(
    niche: str = "",
    count: int = 5,
    viral_threshold: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Suggest trending topics across all registered sources.
    
    Returns list of dicts:
        [{
            "topic": "...",
            "score": 0.85,
            "niche": "...",
            "source": "...",
            "emotion_profile": ["curiosity", "tension"],
            "risk_level": "medium"
        }]
    """
    _ensure_sources()

    all_topics = []
    for source in _sources:
        try:
            topics = source.fetch_trends(niche=niche, count=count * 2)
            all_topics.extend(topics)
        except Exception as e:
            logger.error(f"failed to fetch trends from {type(source).__name__}: {e}")

    if not all_topics:
        logger.warning("no trending topics found from any source")
        return []

    # De-duplicate by topic text
    seen = set()
    unique = []
    for t in all_topics:
        key = t["topic"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(t)

    # Ensure all topics have emotion profiles
    for t in unique:
        if "emotion_profile" not in t:
            profile = score_emotion_profile(t["topic"])
            t["emotion_profile"] = profile["emotions"]
            t["risk_level"] = profile.get("risk_level", "low")

    # Re-score the merged list
    scored = score_topics(unique)

    # Apply viral threshold gating
    if viral_threshold > 0:
        scored = filter_top_scoring(scored, threshold=viral_threshold)

    # Add some randomness to prevent always showing the same topics
    top_half = scored[:max(count * 2, len(scored))]
    random.shuffle(top_half)
    result = score_topics(top_half)

    return result[:count]


def suggest_topic_subjects(niche: str = "", count: int = 5) -> List[str]:
    """
    Simplified API: returns just the topic strings.
    Convenience wrapper around suggest_topics().
    """
    topics = suggest_topics(niche=niche, count=count)
    return [t["topic"] for t in topics]
