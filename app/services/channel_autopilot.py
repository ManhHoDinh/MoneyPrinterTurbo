"""
Channel Autopilot — Autonomous channel creation and lifecycle management.

SINGULARITY LEVEL capabilities:
  1. Auto-create channels with generated identities when opportunities arise
  2. Monitor channel performance and health
  3. Auto-kill (pause/archive) underperforming channels
  4. Scale up high-performing channels automatically

The autopilot reads from niche intelligence, evolution engine, and content
genome to make autonomous decisions about the channel fleet.

Usage:
    from app.services.channel_autopilot import ChannelAutopilot
    pilot = ChannelAutopilot()

    # Discover opportunity and spawn a channel
    spawned = pilot.auto_create_channel(niche="ai_technology")

    # Run health check across all channels
    report = pilot.health_check(channel_ids=["ch-01", "ch-02"])

    # Auto-kill underperformers
    killed = pilot.auto_kill(channel_ids=["ch-01", "ch-02"])
"""

import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from loguru import logger


# ── Configuration ────────────────────────────────────────────────────────────

KILL_THRESHOLD_SCORE = 30.0         # Channels below this get killed
WARN_THRESHOLD_SCORE = 45.0         # Channels below this get warned
BOOST_THRESHOLD_SCORE = 75.0        # Channels above this get boosted
MIN_GENOMES_FOR_JUDGMENT = 10       # Don't judge channels with < N videos
COOLDOWN_DAYS = 7                   # Grace period before kill takes effect


# ── Channel Identity Generator ──────────────────────────────────────────────

IDENTITY_TEMPLATES = {
    "dark_psychology": {
        "name_patterns": [
            "Mind {Adjective}", "{Adjective} Psychology", "The {Adjective} Mind",
            "{Noun} Psychology", "Dark {Noun}", "Inner {Noun}",
        ],
        "adjectives": ["Dark", "Hidden", "Shadow", "Deep", "Silent", "Toxic", "Raw"],
        "nouns": ["Minds", "Signals", "Truths", "Layers", "Patterns", "Code"],
        "pacing": "accelerating",
        "visual_tone": "dark_cinematic",
        "hook_archetype": "fear",
        "subtitle_style": "bold_highlight",
    },
    "motivation": {
        "name_patterns": [
            "{Adjective} Mindset", "The {Noun} Path", "{Adjective} {Noun}",
            "Rise {Noun}", "Level {Noun}", "Peak {Noun}",
        ],
        "adjectives": ["Elite", "Relentless", "Unbreakable", "Iron", "Peak", "Apex"],
        "nouns": ["Grind", "Discipline", "Vision", "Drive", "Forge", "Summit"],
        "pacing": "steady_build",
        "visual_tone": "warm_motivational",
        "hook_archetype": "aspiration",
        "subtitle_style": "clean_centered",
    },
    "luxury_lifestyle": {
        "name_patterns": [
            "{Adjective} Living", "The {Noun} Life", "{Adjective} {Noun}",
            "Ultra {Noun}", "Opulent {Noun}", "The {Adjective} Club",
        ],
        "adjectives": ["Opulent", "Elite", "Prestige", "Golden", "Ultra", "Refined"],
        "nouns": ["Empire", "Legacy", "Crown", "Standard", "Circle", "League"],
        "pacing": "slow_reveal",
        "visual_tone": "luxury_polish",
        "hook_archetype": "authority",
        "subtitle_style": "minimal_elegant",
    },
    "viral_facts": {
        "name_patterns": [
            "{Adjective} Facts", "Fact {Noun}", "{Adjective} {Noun}",
            "Brain {Noun}", "Mind {Noun}", "The {Noun} File",
        ],
        "adjectives": ["Insane", "Unreal", "Wild", "Crazy", "Mega", "Supreme"],
        "nouns": ["Blast", "Bomb", "Vault", "Overload", "Rush", "Storm"],
        "pacing": "rapid_fire",
        "visual_tone": "bright_energetic",
        "hook_archetype": "curiosity",
        "subtitle_style": "animated_pop",
    },
    "stoic_philosophy": {
        "name_patterns": [
            "The {Adjective} Stoic", "Stoic {Noun}", "{Adjective} Wisdom",
            "The {Noun} Mind", "{Adjective} {Noun}", "Ancient {Noun}",
        ],
        "adjectives": ["Quiet", "Unshaken", "Eternal", "Calm", "Iron", "Ancient"],
        "nouns": ["Fortress", "Pillar", "Temple", "Shield", "Path", "Stone"],
        "pacing": "deliberate",
        "visual_tone": "muted_cinematic",
        "hook_archetype": "wisdom",
        "subtitle_style": "serif_classic",
    },
    "finance": {
        "name_patterns": [
            "{Adjective} Finance", "Money {Noun}", "The {Noun} Fund",
            "{Adjective} Wealth", "Capital {Noun}", "{Adjective} Money",
        ],
        "adjectives": ["Smart", "Hidden", "Silent", "Strategic", "Bold", "Sharp"],
        "nouns": ["Moves", "Signals", "Vault", "Edge", "Blueprint", "Code"],
        "pacing": "analytical",
        "visual_tone": "corporate_dark",
        "hook_archetype": "authority",
        "subtitle_style": "clean_data",
    },
    "ai_technology": {
        "name_patterns": [
            "AI {Noun}", "The {Adjective} Machine", "{Adjective} AI",
            "Neural {Noun}", "Cyber {Noun}", "The {Noun} Algorithm",
        ],
        "adjectives": ["Future", "Neural", "Synthetic", "Quantum", "Deep", "Hyper"],
        "nouns": ["Core", "Pulse", "Grid", "Signal", "Matrix", "Nexus"],
        "pacing": "rapid_fire",
        "visual_tone": "tech_neon",
        "hook_archetype": "curiosity",
        "subtitle_style": "monospace_tech",
    },
    "relationships": {
        "name_patterns": [
            "{Adjective} Love", "The {Noun} Rule", "{Adjective} Attraction",
            "Real {Noun}", "Love {Noun}", "The {Adjective} Signal",
        ],
        "adjectives": ["Raw", "Real", "Brutal", "Hidden", "Unfiltered", "Deep"],
        "nouns": ["Truth", "Signals", "Games", "Rules", "Code", "Dynamics"],
        "pacing": "conversational",
        "visual_tone": "intimate_dark",
        "hook_archetype": "shock",
        "subtitle_style": "bold_highlight",
    },
}


# ── Data Structures ──────────────────────────────────────────────────────────

@dataclass
class GeneratedIdentity:
    """Auto-generated channel identity."""
    channel_id: str = ""
    channel_name: str = ""
    niche: str = ""
    pacing: str = ""
    visual_tone: str = ""
    hook_archetype: str = ""
    subtitle_style: str = ""
    created_by: str = "autopilot"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChannelHealth:
    """Health assessment for a single channel."""
    channel_id: str = ""
    status: str = "healthy"     # healthy, warning, critical, killed
    score: float = 0.0
    genome_count: int = 0
    avg_viral: float = 0.0
    avg_retention: float = 0.0
    quality_pass_rate: float = 0.0
    trend: str = "stable"       # improving, stable, declining
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LifecycleAction:
    """An action taken by the autopilot on a channel."""
    channel_id: str = ""
    action: str = ""            # "create", "boost", "warn", "reduce", "kill"
    reason: str = ""
    score: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Channel Autopilot ────────────────────────────────────────────────────────

class ChannelAutopilot:

    def __init__(self):
        from app.services.content_genome import GenomeStore
        self.genome_store = GenomeStore()

    # ── Auto-Create ──────────────────────────────────────────────────

    def auto_create_channel(
        self,
        niche: str = "",
        force_name: str = "",
    ) -> GeneratedIdentity:
        """
        Automatically generate a complete channel identity for a niche.

        If no niche is specified, picks the highest-scoring available niche
        from niche_intelligence.
        """
        # Pick niche if not specified
        if not niche:
            niche = self._pick_best_niche()

        # Generate identity
        identity = self._generate_identity(niche, force_name)

        logger.info(
            f"[Autopilot] Created channel '{identity.channel_name}' "
            f"niche={niche} hook={identity.hook_archetype} "
            f"pacing={identity.pacing}"
        )

        return identity

    def auto_create_fleet(
        self,
        count: int = 3,
        strategy: str = "balanced",
    ) -> List[GeneratedIdentity]:
        """
        Create a fleet of channels with differentiated identities.

        Strategy:
          - "balanced": Mix niches from portfolio recommendation
          - "niche_focus": All channels in same niche, different identities
          - "opportunity": Pick niches based on Opportunity Detector
        """
        identities = []

        if strategy == "balanced":
            try:
                from app.services.niche_intelligence import recommend_channel_portfolio
                portfolio = recommend_channel_portfolio(count, "balanced")
                for item in portfolio:
                    identity = self.auto_create_channel(niche=item["niche"])
                    identities.append(identity)
            except Exception:
                # Fallback: round-robin top niches
                niches = list(IDENTITY_TEMPLATES.keys())[:count]
                for niche in niches:
                    identities.append(self.auto_create_channel(niche=niche))

        elif strategy == "opportunity":
            top_niches = self._detect_opportunities(count)
            for niche in top_niches:
                identities.append(self.auto_create_channel(niche=niche))

        else:  # niche_focus
            niche = self._pick_best_niche()
            for _ in range(count):
                identities.append(self.auto_create_channel(niche=niche))

        logger.info(
            f"[Autopilot] Fleet created: {count} channels, "
            f"strategy={strategy}, niches={[i.niche for i in identities]}"
        )

        return identities

    # ── Health Check ─────────────────────────────────────────────────

    def health_check(self, channel_ids: List[str]) -> List[ChannelHealth]:
        """Assess health of all channels in the fleet."""
        results = []
        for cid in channel_ids:
            health = self._assess_channel(cid)
            results.append(health)

        healthy = sum(1 for h in results if h.status == "healthy")
        warning = sum(1 for h in results if h.status == "warning")
        critical = sum(1 for h in results if h.status == "critical")

        logger.info(
            f"[Autopilot] Health check: {healthy} healthy, "
            f"{warning} warning, {critical} critical"
        )

        return results

    # ── Auto Kill ────────────────────────────────────────────────────

    def auto_kill(self, channel_ids: List[str]) -> List[LifecycleAction]:
        """
        Evaluate channels and take lifecycle actions:
          - Score > BOOST:  Increase production frequency
          - Score < WARN:   Reduce frequency, flag for review
          - Score < KILL:   Stop production entirely
        """
        actions = []

        for cid in channel_ids:
            health = self._assess_channel(cid)

            if health.genome_count < MIN_GENOMES_FOR_JUDGMENT:
                actions.append(LifecycleAction(
                    channel_id=cid,
                    action="observe",
                    reason=f"Insufficient data ({health.genome_count}/{MIN_GENOMES_FOR_JUDGMENT})",
                    score=health.score,
                ))
                continue

            if health.score >= BOOST_THRESHOLD_SCORE:
                actions.append(LifecycleAction(
                    channel_id=cid,
                    action="boost",
                    reason=f"High performer (score={health.score:.0f}). Increase frequency.",
                    score=health.score,
                ))

            elif health.score >= WARN_THRESHOLD_SCORE:
                actions.append(LifecycleAction(
                    channel_id=cid,
                    action="maintain",
                    reason=f"Adequate performance (score={health.score:.0f}). Continue.",
                    score=health.score,
                ))

            elif health.score >= KILL_THRESHOLD_SCORE:
                actions.append(LifecycleAction(
                    channel_id=cid,
                    action="reduce",
                    reason=f"Below warning threshold (score={health.score:.0f}). Reduce frequency.",
                    score=health.score,
                ))

            else:
                actions.append(LifecycleAction(
                    channel_id=cid,
                    action="kill",
                    reason=f"Critical underperformance (score={health.score:.0f}). Stop production.",
                    score=health.score,
                ))

        killed = sum(1 for a in actions if a.action == "kill")
        boosted = sum(1 for a in actions if a.action == "boost")

        if killed or boosted:
            logger.warning(
                f"[Autopilot] Lifecycle actions: "
                f"{boosted} boosted, {killed} killed, "
                f"{len(actions) - killed - boosted} maintained"
            )

        return actions

    # ── Opportunity Detection ────────────────────────────────────────

    def detect_opportunities(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Evaluate niche opportunities by combining:
          - Niche intelligence scores
          - Current fleet coverage (gaps)
          - Competition density estimate
        """
        opportunities = []

        try:
            from app.services.niche_intelligence import discover_niches
            niches = discover_niches(count=count * 2)

            # Check which niches are already covered
            existing_topics = self.genome_store.get_recent_topics(50)
            existing_lower = " ".join(existing_topics).lower()

            for niche in niches:
                # Rough competition check: how much of our genome is in this niche
                coverage = existing_lower.count(niche.niche_key.replace("_", " "))
                competition = "low" if coverage < 3 else "medium" if coverage < 10 else "high"

                opportunity_score = niche.composite_score
                if competition == "low":
                    opportunity_score *= 1.2  # Boost uncovered niches
                elif competition == "high":
                    opportunity_score *= 0.8  # Penalize saturated niches

                opportunities.append({
                    "niche": niche.niche_key,
                    "display_name": niche.display_name,
                    "opportunity_score": round(opportunity_score, 1),
                    "base_score": niche.composite_score,
                    "competition": competition,
                    "cpm_range": niche.cpm_range,
                    "recommendation": (
                        "EXPAND" if competition == "low" and opportunity_score > 70
                        else "CONSIDER" if opportunity_score > 55
                        else "SKIP"
                    ),
                })
        except Exception as e:
            logger.warning(f"[Autopilot] Opportunity detection failed: {e}")

        opportunities.sort(key=lambda x: x.get("opportunity_score", 0), reverse=True)
        return opportunities[:count]

    # ── Internal Methods ─────────────────────────────────────────────

    def _generate_identity(self, niche: str, force_name: str = "") -> GeneratedIdentity:
        """Generate a channel identity from templates."""
        template = IDENTITY_TEMPLATES.get(niche, IDENTITY_TEMPLATES.get("dark_psychology", {}))
        rng = random.Random(time.time_ns())

        if force_name:
            name = force_name
        else:
            pattern = rng.choice(template.get("name_patterns", ["{Adjective} Channel"]))
            adj = rng.choice(template.get("adjectives", ["Dark"]))
            noun = rng.choice(template.get("nouns", ["Content"]))
            name = pattern.replace("{Adjective}", adj).replace("{Noun}", noun)

        return GeneratedIdentity(
            channel_id=f"auto-{uuid.uuid4().hex[:8]}",
            channel_name=name,
            niche=niche,
            pacing=template.get("pacing", "moderate"),
            visual_tone=template.get("visual_tone", "default"),
            hook_archetype=template.get("hook_archetype", "curiosity"),
            subtitle_style=template.get("subtitle_style", "default"),
        )

    def _assess_channel(self, channel_id: str) -> ChannelHealth:
        """Score a channel's health from genome data."""
        genomes = self.genome_store.query(
            channel_id=channel_id, limit=50, sort_by="created_at"
        )

        if not genomes:
            return ChannelHealth(
                channel_id=channel_id,
                status="unknown",
                recommendation="No data — continue generating",
            )

        viral = [g.viral_score for g in genomes if g.viral_score > 0]
        ret = [g.retention_score for g in genomes if g.retention_score > 0]
        passed = sum(1 for g in genomes if g.quality_passed)

        avg_v = sum(viral) / len(viral) if viral else 50
        avg_r = sum(ret) / len(ret) if ret else 50
        pass_rate = passed / len(genomes) * 100

        score = avg_v * 0.4 + avg_r * 0.35 + pass_rate * 0.25

        # Trend detection (compare recent half vs older half)
        trend = "stable"
        if len(genomes) >= 6:
            mid = len(genomes) // 2
            recent_scores = [g.viral_score for g in genomes[:mid] if g.viral_score > 0]
            older_scores = [g.viral_score for g in genomes[mid:] if g.viral_score > 0]
            if recent_scores and older_scores:
                recent_avg = sum(recent_scores) / len(recent_scores)
                older_avg = sum(older_scores) / len(older_scores)
                if recent_avg > older_avg * 1.1:
                    trend = "improving"
                elif recent_avg < older_avg * 0.9:
                    trend = "declining"

        # Status
        if score >= BOOST_THRESHOLD_SCORE:
            status = "healthy"
            rec = "High performer — consider increasing frequency"
        elif score >= WARN_THRESHOLD_SCORE:
            status = "healthy"
            rec = "Adequate — maintain current strategy"
        elif score >= KILL_THRESHOLD_SCORE:
            status = "warning"
            rec = "Underperforming — review content strategy"
        else:
            status = "critical"
            rec = "Critical — consider pausing or pivoting niche"

        return ChannelHealth(
            channel_id=channel_id,
            status=status,
            score=round(score, 1),
            genome_count=len(genomes),
            avg_viral=round(avg_v, 1),
            avg_retention=round(avg_r, 1),
            quality_pass_rate=round(pass_rate, 1),
            trend=trend,
            recommendation=rec,
        )

    def _pick_best_niche(self) -> str:
        """Pick the highest-scoring available niche."""
        try:
            from app.services.niche_intelligence import discover_niches
            niches = discover_niches(count=1)
            return niches[0].niche_key if niches else "dark_psychology"
        except Exception:
            return "dark_psychology"

    def _detect_opportunities(self, count: int) -> List[str]:
        """Get top opportunity niches."""
        opps = self.detect_opportunities(count)
        return [o["niche"] for o in opps if o.get("recommendation") != "SKIP"][:count]
