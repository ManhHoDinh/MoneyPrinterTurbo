"""
Stealth and Anti-Shadowban Engine — BLACK OPS Quality Filter

Implements uniqueness tracking, history checking, and quality scoring 
to prevent algorithm penalties and shadowbans.
"""

from typing import Dict, Any
from difflib import SequenceMatcher
from loguru import logger

from app.services import state as sm
from app.models.schema import VideoParams
from app.models import const


class QualityFilter:
    @staticmethod
    def calculate_uniqueness(current_script: str, max_history: int = 20) -> float:
        """
        Calculates uniqueness score against recent completed tasks.
        0.0 = completely identical, 1.0 = completely unique
        """
        try:
            recent_tasks, _ = sm.state.get_all_tasks(page=1, page_size=max_history * 2)
            if not recent_tasks:
                return 1.0

            lowest_uniqueness = 1.0
            
            for task in recent_tasks:
                if task.get("state") == const.TASK_STATE_COMPLETE and task.get("script"):
                    similarity = SequenceMatcher(None, current_script, task.get("script")).ratio()
                    uniqueness = 1.0 - similarity
                    lowest_uniqueness = min(lowest_uniqueness, uniqueness)
            
            logger.info(f"script uniqueness score: {lowest_uniqueness:.2f}")
            return lowest_uniqueness
        except Exception as e:
            logger.warning(f"failed to calculate uniqueness: {e}")
            return 1.0

    @staticmethod
    def evaluate_video_quality(params: VideoParams, script: str, scenes: list) -> Dict[str, Any]:
        """
        Evaluates visual diversity, emotional variance, and uniqueness.
        Returns a dict containing scores and a 'passed' boolean.
        """
        scores = {
            "uniqueness": QualityFilter.calculate_uniqueness(script),
            "visual_diversity": 1.0,
            "emotional_variance": 1.0,
            "passed": True,
            "reason": ""
        }

        # Evaluate visual diversity and emotional variance
        if scenes:
            queries = set([s.search_query for s in scenes if hasattr(s, 'search_query') and s.search_query])
            if len(scenes) > 0:
                scores["visual_diversity"] = len(queries) / len(scenes)
            
            emotions = set([s.emotion for s in scenes if hasattr(s, 'emotion') and s.emotion])
            if len(scenes) > 0:
                scores["emotional_variance"] = len(emotions) / len(scenes)
        
        # Enforce rejection thresholds
        # In stealth_mode, requirements are stricter to avoid algorithm patterns
        thresholds = {
            "uniqueness": 0.3 if getattr(params, 'stealth_mode', False) else 0.1,
            "visual_diversity": 0.4 if getattr(params, 'stealth_mode', False) else 0.2,
        }

        if scores["uniqueness"] < thresholds["uniqueness"]:
            scores["passed"] = False
            scores["reason"] = f"uniqueness score {scores['uniqueness']:.2f} below threshold {thresholds['uniqueness']}"
            logger.warning(f"auto-fail triggered: {scores['reason']}")
        elif scores["visual_diversity"] < thresholds["visual_diversity"]:
            scores["passed"] = False
            scores["reason"] = f"visual diversity {scores['visual_diversity']:.2f} below threshold {thresholds['visual_diversity']}"
            logger.warning(f"auto-fail triggered: {scores['reason']}")
        else:
            logger.success("passed pre-publish quality analyzer")

        return scores
