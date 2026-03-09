"""
Batch Video Generator — GOD MODE Scale System.

Supports batch generation of 50-100 videos/day with:
- Automatic trend-based topic generation
- Style rotation across presets
- Concurrent task execution
- Quality consistency validation
"""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable

from loguru import logger


# ── Batch Configuration ──────────────────────────────────────────────────────

AVAILABLE_STYLES = [
    "dark_psychology",
    "motivation",
    "luxury_lifestyle",
    "stoic_philosophy",
    "viral_facts",
]


@dataclass
class BatchConfig:
    """Configuration for a batch video generation run."""
    topics_count: int = 50
    styles: List[str] = field(default_factory=lambda: AVAILABLE_STYLES.copy())
    max_concurrent: int = 3
    quality_threshold: float = 70.0  # minimum retention score
    niche: str = ""
    viral_score_threshold: float = 0.7
    voice_name: str = "en-US-EmmaMultilingualNeural-Female"
    video_language: str = "en"
    enable_ab_hooks: bool = True
    enable_viral_rewrite: bool = True
    enable_retention_optimizer: bool = True
    stealth_mode: bool = True
    channel_profiles: List[str] = field(default_factory=list)


@dataclass
class BatchTaskItem:
    """A single task within a batch run."""
    topic: str = ""
    style: str = ""
    task_id: str = ""
    status: str = "pending"  # pending, running, completed, failed
    viral_score: float = 0.0
    emotion_profile: List[str] = field(default_factory=list)
    hook_variants: List[Dict] = field(default_factory=list)
    retention_score: float = 0.0
    engagement_score: float = 0.0
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    output_path: str = ""


@dataclass
class BatchReport:
    """Summary report for a completed batch run."""
    total_topics: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    avg_viral_score: float = 0.0
    avg_retention_score: float = 0.0
    avg_engagement_score: float = 0.0
    styles_used: Dict[str, int] = field(default_factory=dict)
    duration_seconds: float = 0.0
    items: List[BatchTaskItem] = field(default_factory=list)


# ── Batch Topic Generation ───────────────────────────────────────────────────

def generate_batch_topics(
    niche: str = "",
    count: int = 50,
    viral_threshold: float = 0.7,
    styles: List[str] = None,
) -> List[Dict[str, Any]]:
    """
    Generate a batch of topics using the trend engine,
    filtered by viral score threshold.

    Each topic is assigned a style from the rotation.

    Returns list of dicts:
        [{
            "topic": "...",
            "style": "dark_psychology",
            "viral_score": 0.85,
            "emotion_profile": ["curiosity", "tension"],
            "risk_level": "medium"
        }]
    """
    from app.services import trends

    if styles is None:
        styles = AVAILABLE_STYLES.copy()

    # Generate more topics than needed, then filter
    raw_topics = trends.suggest_topics(
        niche=niche,
        count=count * 2,
        viral_threshold=viral_threshold,
    )

    if not raw_topics:
        logger.warning("no topics generated for batch, falling back to niche keywords")
        raw_topics = _fallback_topics(niche, count)

    # Assign styles in rotation
    result = []
    for i, topic in enumerate(raw_topics[:count]):
        style = styles[i % len(styles)]
        result.append({
            "topic": topic.get("topic", ""),
            "style": style,
            "viral_score": topic.get("score", 0.5),
            "emotion_profile": topic.get("emotion_profile", ["curiosity"]),
            "risk_level": topic.get("risk_level", "low"),
        })

    logger.info(f"generated {len(result)} batch topics (threshold={viral_threshold})")
    return result


def _fallback_topics(niche: str, count: int) -> List[Dict[str, Any]]:
    """Fallback topic generation when LLM/trend sources fail."""
    fallback_niches = {
        "dark_psychology": [
            "dark psychology tricks that control your mind",
            "manipulation tactics used by social media",
            "why you can't stop scrolling explained",
            "cognitive biases that ruin your decisions",
            "psychology tricks billionaires use daily",
        ],
        "motivation": [
            "why most people never achieve their goals",
            "the morning routine that changed everything",
            "how successful people think differently",
            "the one habit that separates winners from losers",
            "why pain is the secret to success",
        ],
        "luxury_lifestyle": [
            "habits that separate the wealthy from everyone else",
            "why rich people never work for money",
            "the invisible rules of the top one percent",
            "luxury items that are actually worth the investment",
            "how to think like a millionaire starting today",
        ],
        "stoic_philosophy": [
            "stoic philosophy that cured my anxiety",
            "Marcus Aurelius wisdom for modern life",
            "how the Stoics mastered emotional control",
            "ancient wisdom that still works today",
            "the stoic secret to bulletproof confidence",
        ],
        "viral_facts": [
            "mind-blowing facts that change how you see the world",
            "scientific facts that sound completely fake",
            "facts your teachers never told you about",
            "the most unbelievable facts about the human body",
            "facts about space that will break your brain",
        ],
    }

    niche_lower = niche.lower() if niche else "general"
    selected_topics = []

    for style_name, topics in fallback_niches.items():
        if niche_lower in style_name or niche_lower == "general" or not niche:
            for t in topics:
                from app.services.trends import score_emotion_profile
                profile = score_emotion_profile(t)
                selected_topics.append({
                    "topic": t,
                    "score": 0.6,
                    "niche": style_name,
                    "source": "fallback",
                    "emotion_profile": profile["emotions"],
                    "risk_level": profile["risk_level"],
                })

    return selected_topics[:count]


# ── Batch Task Creation ──────────────────────────────────────────────────────

def create_batch_tasks(
    topics: List[Dict[str, Any]],
    config: BatchConfig,
) -> List[BatchTaskItem]:
    """
    Create BatchTaskItem objects for each topic.
    Each gets a unique task_id and inherits style + metadata.
    """
    tasks = []
    for topic_data in topics:
        task_id = f"batch_{uuid.uuid4().hex[:12]}"
        item = BatchTaskItem(
            topic=topic_data.get("topic", ""),
            style=topic_data.get("style", ""),
            task_id=task_id,
            viral_score=topic_data.get("viral_score", 0.5),
            emotion_profile=topic_data.get("emotion_profile", []),
        )
        tasks.append(item)

    logger.info(f"created {len(tasks)} batch task items")
    return tasks


def create_video_params(item: BatchTaskItem, config: BatchConfig, index: int = 0) -> Dict[str, Any]:
    """Convert a BatchTaskItem into VideoParams-compatible dict with rotations."""
    
    # Niche Rotation Engine (Voice rotation when stealth mode enabled)
    voices = [
        "en-US-EmmaMultilingualNeural-Female", 
        "en-US-AndrewMultilingualNeural-Male",
        "en-US-BrianMultilingualNeural-Male",
        "en-US-AvaMultilingualNeural-Female"
    ]
    voice = voices[index % len(voices)] if getattr(config, 'stealth_mode', False) else config.voice_name

    channel = None
    if getattr(config, 'channel_profiles', None) and len(config.channel_profiles) > 0:
        channel = config.channel_profiles[index % len(config.channel_profiles)]

    return {
        "video_subject": item.topic,
        "video_style": item.style,
        "voice_name": voice,
        "video_language": config.video_language,
        "enable_hook_generator": True,
        "enable_viral_rewrite": config.enable_viral_rewrite,
        "enable_retention_optimizer": config.enable_retention_optimizer,
        "enable_ab_hooks": config.enable_ab_hooks,
        "stealth_mode": getattr(config, 'stealth_mode', False),
        "channel_profile": channel,
    }


# ── Batch Execution ──────────────────────────────────────────────────────────

def run_batch(
    config: BatchConfig,
    task_runner: Callable = None,
) -> BatchReport:
    """
    Orchestrate a full batch generation run.

    Args:
        config: BatchConfig with topics_count, styles, concurrency, etc.
        task_runner: Callable that takes (task_id, params_dict) and runs a video task.
                     If None, tasks are created but not executed (dry run).

    Returns:
        BatchReport with summary statistics and per-item results.
    """
    start_time = time.time()

    # 1. Generate topics
    topics = generate_batch_topics(
        niche=config.niche,
        count=config.topics_count,
        viral_threshold=config.viral_score_threshold,
        styles=config.styles,
    )

    # 2. Create task items
    tasks = create_batch_tasks(topics, config)

    # 3. Generate hook variants for each task
    if config.enable_ab_hooks:
        try:
            from app.services.hook_generator import generate_hook_variants
            for item in tasks:
                item.hook_variants = generate_hook_variants(
                    video_subject=item.topic,
                    video_style=item.style,
                    variant_count=5,
                )
        except Exception as e:
            logger.warning(f"hook variant generation failed for batch: {e}")

    # 4. Execute tasks
    if task_runner:
        _execute_batch(tasks, config, task_runner)
    else:
        logger.info("dry run mode — tasks created but not executed")

    # 5. Build report
    report = _build_report(tasks, start_time)

    logger.info(
        f"batch complete: {report.total_completed}/{report.total_topics} succeeded, "
        f"{report.total_failed} failed, {report.duration_seconds:.0f}s elapsed"
    )

    return report


def _execute_batch(
    tasks: List[BatchTaskItem],
    config: BatchConfig,
    task_runner: Callable,
):
    """Execute batch tasks with thread pool concurrency."""
    max_workers = min(config.max_concurrent, len(tasks))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {}
        for index, item in enumerate(tasks):
            params = create_video_params(item, config, index)
            item.status = "running"
            item.started_at = time.time()
            future = executor.submit(task_runner, item.task_id, params)
            future_to_item[future] = item

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                result = future.result()
                item.status = "completed"
                item.completed_at = time.time()
                if isinstance(result, dict):
                    item.output_path = str(result.get("videos", [""])[0]) if result.get("videos") else ""
            except Exception as e:
                item.status = "failed"
                item.error = str(e)
                item.completed_at = time.time()
                logger.error(f"batch task {item.task_id} failed: {e}")


def _build_report(tasks: List[BatchTaskItem], start_time: float) -> BatchReport:
    """Build a BatchReport from completed task items."""
    completed = [t for t in tasks if t.status == "completed"]
    failed = [t for t in tasks if t.status == "failed"]
    skipped = [t for t in tasks if t.status == "pending"]

    styles_used: Dict[str, int] = {}
    for t in tasks:
        styles_used[t.style] = styles_used.get(t.style, 0) + 1

    avg_viral = sum(t.viral_score for t in tasks) / len(tasks) if tasks else 0
    avg_retention = sum(t.retention_score for t in completed) / len(completed) if completed else 0
    avg_engagement = sum(t.engagement_score for t in completed) / len(completed) if completed else 0

    return BatchReport(
        total_topics=len(tasks),
        total_completed=len(completed),
        total_failed=len(failed),
        total_skipped=len(skipped),
        avg_viral_score=round(avg_viral, 3),
        avg_retention_score=round(avg_retention, 1),
        avg_engagement_score=round(avg_engagement, 1),
        styles_used=styles_used,
        duration_seconds=round(time.time() - start_time, 1),
        items=tasks,
    )


# ── Quality Validation ──────────────────────────────────────────────────────

def validate_batch_quality(
    tasks: List[BatchTaskItem],
    quality_threshold: float = 70.0,
) -> Dict[str, Any]:
    """
    Post-generation quality check for a batch run.

    Checks:
    - Retention score >= threshold
    - Engagement trifecta present
    - No consecutive duplicate topics

    Returns:
        {
            "passed": 42,
            "failed": 8,
            "issues": ["task_xxx: low retention (55.0)", ...]
        }
    """
    passed = 0
    failed = 0
    issues = []

    for item in tasks:
        if item.status != "completed":
            continue

        item_issues = []

        # Check retention score
        if item.retention_score < quality_threshold:
            item_issues.append(
                f"{item.task_id}: low retention ({item.retention_score:.0f})"
            )

        # Check engagement score
        if item.engagement_score < quality_threshold:
            item_issues.append(
                f"{item.task_id}: low engagement ({item.engagement_score:.0f})"
            )

        if item_issues:
            failed += 1
            issues.extend(item_issues)
        else:
            passed += 1

    # Check for duplicate topics
    topics_seen = set()
    for item in tasks:
        topic_key = item.topic.lower().strip()
        if topic_key in topics_seen:
            issues.append(f"{item.task_id}: duplicate topic '{item.topic[:50]}'")
        topics_seen.add(topic_key)

    return {
        "passed": passed,
        "failed": failed,
        "total_checked": passed + failed,
        "issues": issues,
    }
