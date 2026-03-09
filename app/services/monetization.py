"""
Monetization Layer — Affiliate links, CTA generation, description optimization.

Generates revenue-optimized metadata for each uploaded video:
  - Video description with SEO keywords, affiliate links, and CTAs
  - Pinned comment templates with engagement hooks
  - End screen CTA text
  - Tags optimized for monetization-friendly discovery

Does NOT modify the video itself — only generates upload metadata.

Usage:
    from app.services.monetization import generate_monetization_metadata
    meta = generate_monetization_metadata(
        topic="5 Dark Psychology Tricks",
        niche="dark_psychology",
        style="dark_psychology",
    )
    print(meta.description)
    print(meta.tags)
"""

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from loguru import logger


# ── Affiliate Link Templates ────────────────────────────────────────────────

AFFILIATE_TEMPLATES: Dict[str, List[Dict[str, str]]] = {
    "books": [
        {"label": "📚 Best psychology books", "placeholder": "[YOUR_AMAZON_LINK]"},
        {"label": "📖 Books that changed my life", "placeholder": "[YOUR_AMAZON_LINK]"},
    ],
    "courses": [
        {"label": "🎓 Master this skill", "placeholder": "[YOUR_COURSE_LINK]"},
        {"label": "💡 Free training on this topic", "placeholder": "[YOUR_COURSE_LINK]"},
    ],
    "self-improvement": [
        {"label": "🧠 Tools I use daily", "placeholder": "[YOUR_LINK]"},
        {"label": "⚡ Level up your mindset", "placeholder": "[YOUR_LINK]"},
    ],
    "finance": [
        {"label": "💰 Start investing here", "placeholder": "[YOUR_BROKERAGE_LINK]"},
        {"label": "📊 Best finance tools", "placeholder": "[YOUR_LINK]"},
    ],
    "supplements": [
        {"label": "💊 What I take daily", "placeholder": "[YOUR_SUPPLEMENT_LINK]"},
    ],
    "tools": [
        {"label": "🛠️ Tools mentioned in this video", "placeholder": "[YOUR_LINK]"},
    ],
    "software": [
        {"label": "💻 Try it free", "placeholder": "[YOUR_SOFTWARE_LINK]"},
    ],
}

# ── CTA Templates ────────────────────────────────────────────────────────────

CTA_HOOKS = {
    "dark_psychology": [
        "💀 Follow for more dark psychology secrets most people never learn.",
        "🧠 Subscribe if you want to understand the mind games around you.",
        "⚠️ Don't scroll — the next video reveals something even darker.",
    ],
    "motivation": [
        "🔥 Subscribe for daily motivation that actually works.",
        "💪 Follow to stop making the mistakes that hold you back.",
        "📈 Hit subscribe — your future self will thank you.",
    ],
    "luxury_lifestyle": [
        "💎 Subscribe for the blueprint to a luxury life.",
        "🏆 Follow for wealth strategies the 1% uses daily.",
    ],
    "stoic_philosophy": [
        "🏛️ Subscribe for ancient wisdom that solves modern problems.",
        "⚔️ Follow for daily stoic lessons that build mental strength.",
    ],
    "viral_facts": [
        "🤯 Subscribe for facts that will blow your mind every day.",
        "🔬 Follow for the most insane facts you've never heard.",
    ],
    "finance": [
        "💰 Subscribe to learn what schools never teach about money.",
        "📊 Follow for finance secrets the wealthy don't share.",
    ],
    "relationships": [
        "💔 Subscribe for relationship truths nobody talks about.",
        "❤️ Follow for psychology-backed relationship advice.",
    ],
    "health": [
        "🧬 Subscribe for health hacks backed by science.",
        "💪 Follow for the truth about fitness and health.",
    ],
    "ai_technology": [
        "🤖 Subscribe for AI news that actually matters.",
        "⚡ Follow before AI changes everything.",
    ],
    "true_crime": [
        "🔍 Subscribe for stories that will keep you up at night.",
        "💀 Follow for the darkest true crime cases ever documented.",
    ],
}

PINNED_COMMENT_TEMPLATES = [
    "What surprised you the most? Drop your answer below 👇",
    "Which part of this video hit you the hardest? Let me know 🎯",
    "Did you already know about this? Be honest 👀",
    "Tag someone who NEEDS to see this 🫵",
    "What topic should I cover next? Best suggestion gets pinned 📌",
    "Do you agree with this? The comments are going crazy 🔥",
]


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class MonetizationMetadata:
    """Revenue-optimized upload metadata for a single video."""
    title: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    pinned_comment: str = ""
    end_screen_cta: str = ""
    affiliate_links: List[Dict[str, str]] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    seo_keywords: List[str] = field(default_factory=list)
    estimated_cpm: float = 0.0
    thumbnail_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


# ── Public API ───────────────────────────────────────────────────────────────

def generate_monetization_metadata(
    topic: str,
    niche: str = "dark_psychology",
    style: str = "",
    channel_name: str = "",
    affiliate_overrides: Dict[str, str] = None,
) -> MonetizationMetadata:
    """
    Generate complete monetization metadata for a video.

    Args:
        topic:               Video topic
        niche:               Content niche
        style:               Style preset
        channel_name:        Channel display name (for branding)
        affiliate_overrides: Override affiliate link placeholders with real URLs

    Returns:
        MonetizationMetadata with title, description, tags, CTA, affiliate links.
    """
    rng = random.Random(hash(topic) & 0xFFFFFFFF)

    # Title optimization
    title = _generate_title(topic, niche, rng)

    # SEO keywords
    seo_keywords = _extract_seo_keywords(topic, niche)

    # Tags
    tags = _generate_tags(topic, niche, seo_keywords)

    # Hashtags
    hashtags = _generate_hashtags(niche, seo_keywords[:5])

    # Affiliate links
    affiliate_links = _select_affiliate_links(niche, affiliate_overrides)

    # Description
    description = _build_description(
        topic, niche, channel_name, seo_keywords, affiliate_links, hashtags
    )

    # CTA
    niche_ctas = CTA_HOOKS.get(niche, CTA_HOOKS.get("dark_psychology", []))
    end_cta = rng.choice(niche_ctas) if niche_ctas else ""

    # Pinned comment
    pinned = rng.choice(PINNED_COMMENT_TEMPLATES)

    # CPM estimate
    from app.services.niche_intelligence import NICHE_DATABASE
    niche_data = NICHE_DATABASE.get(niche, {})
    cpm_range = niche_data.get("cpm_range", [5, 15])
    estimated_cpm = sum(cpm_range) / 2

    meta = MonetizationMetadata(
        title=title,
        description=description,
        tags=tags,
        pinned_comment=pinned,
        end_screen_cta=end_cta,
        affiliate_links=affiliate_links,
        hashtags=hashtags,
        seo_keywords=seo_keywords,
        estimated_cpm=estimated_cpm,
    )

    logger.debug(
        f"[Monetization] Generated metadata for '{topic[:40]}' "
        f"niche={niche} tags={len(tags)} affiliates={len(affiliate_links)}"
    )

    return meta


def batch_generate_metadata(
    items: List[Dict[str, str]],
    affiliate_overrides: Dict[str, str] = None,
) -> List[Dict[str, Any]]:
    """Generate metadata for a batch of videos."""
    results = []
    for item in items:
        meta = generate_monetization_metadata(
            topic=item.get("topic", ""),
            niche=item.get("niche", "dark_psychology"),
            style=item.get("style", ""),
            channel_name=item.get("channel_name", ""),
            affiliate_overrides=affiliate_overrides,
        )
        results.append(meta.to_dict())
    return results


# ── Internal Generators ──────────────────────────────────────────────────────

def _generate_title(topic: str, niche: str, rng: random.Random) -> str:
    """Generate a click-optimized title from the topic."""
    # Clean and capitalize
    title = topic.strip()
    if not title[0].isupper():
        title = title[0].upper() + title[1:]

    # Add emotional prefix occasionally
    prefixes = {
        "dark_psychology": ["⚠️", "💀", "🧠"],
        "motivation": ["🔥", "💪", "📈"],
        "luxury_lifestyle": ["💎", "🏆", "💰"],
        "viral_facts": ["🤯", "🔬", "😱"],
        "true_crime": ["🔍", "💀", "⚠️"],
    }
    niche_prefixes = prefixes.get(niche, [""])
    if rng.random() < 0.6 and niche_prefixes:
        title = f"{rng.choice(niche_prefixes)} {title}"

    # Truncate for YouTube (100 char limit, but 60-70 is optimal)
    if len(title) > 70:
        title = title[:67] + "..."

    return title


def _extract_seo_keywords(topic: str, niche: str) -> List[str]:
    """Extract SEO-relevant keywords from topic and niche."""
    # Topic words (excluding stop words)
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
        "to", "for", "of", "with", "by", "from", "that", "this", "it",
        "and", "or", "but", "not", "you", "your", "they", "their",
    }
    topic_words = [
        w.lower().strip(".,!?\"'")
        for w in topic.split()
        if w.lower() not in stop_words and len(w) > 2
    ]

    # Add niche keywords
    niche_keywords = {
        "dark_psychology": ["psychology", "manipulation", "mind", "behavior", "cognitive"],
        "motivation": ["success", "mindset", "goals", "habits", "discipline"],
        "luxury_lifestyle": ["wealth", "luxury", "rich", "millionaire", "lifestyle"],
        "stoic_philosophy": ["stoicism", "philosophy", "marcus aurelius", "wisdom"],
        "viral_facts": ["facts", "science", "amazing", "incredible", "discovery"],
        "finance": ["money", "investing", "financial", "wealth", "savings"],
        "relationships": ["relationships", "dating", "love", "attraction"],
        "health": ["health", "fitness", "wellness", "biohacking"],
        "ai_technology": ["AI", "artificial intelligence", "technology", "future"],
        "true_crime": ["true crime", "mystery", "investigation", "unsolved"],
    }

    keywords = topic_words + niche_keywords.get(niche, [])
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    return unique[:20]


def _generate_tags(topic: str, niche: str, seo_keywords: List[str]) -> List[str]:
    """Generate YouTube tags (max 500 chars total)."""
    tags = list(seo_keywords[:10])

    # Add broad niche tags
    broad_tags = {
        "dark_psychology": ["dark psychology", "psychology facts", "mind tricks"],
        "motivation": ["motivation", "self improvement", "success mindset"],
        "luxury_lifestyle": ["luxury lifestyle", "wealth", "rich mindset"],
        "viral_facts": ["amazing facts", "did you know", "science facts"],
        "finance": ["personal finance", "investing", "money tips"],
    }
    tags.extend(broad_tags.get(niche, [niche]))

    # Add format tags
    tags.extend(["shorts", "viral", "trending"])

    return tags[:30]  # YouTube allows max ~30 effective tags


def _generate_hashtags(niche: str, keywords: List[str]) -> List[str]:
    """Generate hashtags for description and title."""
    base_hashtags = {
        "dark_psychology": ["#psychology", "#darkpsychology", "#mindgames"],
        "motivation": ["#motivation", "#success", "#mindset"],
        "luxury_lifestyle": ["#luxury", "#wealth", "#millionaire"],
        "viral_facts": ["#facts", "#didyouknow", "#science"],
        "finance": ["#finance", "#investing", "#money"],
    }

    hashtags = base_hashtags.get(niche, [f"#{niche}"])

    # Add keyword-based hashtags
    for kw in keywords[:3]:
        tag = f"#{kw.replace(' ', '').lower()}"
        if tag not in hashtags:
            hashtags.append(tag)

    hashtags.append("#shorts")
    return hashtags[:8]


def _select_affiliate_links(
    niche: str,
    overrides: Dict[str, str] = None,
) -> List[Dict[str, str]]:
    """Select relevant affiliate link templates for the niche."""
    from app.services.niche_intelligence import NICHE_DATABASE
    niche_data = NICHE_DATABASE.get(niche, {})
    categories = niche_data.get("affiliate_categories", ["books"])

    links = []
    for cat in categories[:3]:
        templates = AFFILIATE_TEMPLATES.get(cat, [])
        if templates:
            template = templates[0].copy()
            # Apply overrides if provided
            if overrides and cat in overrides:
                template["url"] = overrides[cat]
            else:
                template["url"] = template.pop("placeholder", "[YOUR_LINK]")
            links.append(template)

    return links


def _build_description(
    topic: str,
    niche: str,
    channel_name: str,
    seo_keywords: List[str],
    affiliate_links: List[Dict[str, str]],
    hashtags: List[str],
) -> str:
    """Build a monetization-optimized YouTube description."""
    lines = []

    # Hook line (first line visible before "Show More")
    lines.append(f"🎯 {topic}")
    lines.append("")

    # Affiliate section
    if affiliate_links:
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("📌 RESOURCES & LINKS:")
        for link in affiliate_links:
            lines.append(f"  ▸ {link['label']}: {link.get('url', '[LINK]')}")
        lines.append("")

    # CTA section
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔔 Don't forget to SUBSCRIBE and enable notifications!")
    lines.append("👍 LIKE this video if you learned something")
    lines.append("💬 COMMENT your thoughts below")
    lines.append("")

    # SEO keyword paragraph
    if seo_keywords:
        seo_text = ", ".join(seo_keywords[:12])
        lines.append(f"Topics covered: {seo_text}")
        lines.append("")

    # Hashtags (YouTube shows first 3 hashtags above title)
    if hashtags:
        lines.append(" ".join(hashtags))

    # Channel branding
    if channel_name:
        lines.append("")
        lines.append(f"© {channel_name}")

    return "\n".join(lines)
