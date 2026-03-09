"""
Duplicate Avoidance & Rewrite Engine — Prevents content duplication signals.

Implements:
- Semantic similarity detection (TF-IDF cosine)
- Hook mutation logic
- Structure mutation engine
- Phrasing entropy injection
- Configurable similarity threshold
"""

import re
import math
import random
from collections import Counter
from typing import Dict, List, Tuple, Optional
from loguru import logger


# ── TF-IDF Cosine Similarity ────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple word tokenizer — lowercase, alpha-only."""
    return re.findall(r'[a-z]+', text.lower())


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Compute term frequency for a token list."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {word: count / total for word, count in counts.items()}


def _compute_idf(doc_token_lists: List[List[str]]) -> Dict[str, float]:
    """Compute inverse document frequency across documents."""
    n_docs = len(doc_token_lists)
    if n_docs == 0:
        return {}
    df = Counter()
    for tokens in doc_token_lists:
        for word in set(tokens):
            df[word] += 1
    # Smoothed IDF: avoids log(1)=0 when all docs contain the same terms
    return {word: math.log((n_docs + 1) / (count + 1)) + 1 for word, count in df.items()}


def compute_semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Compute semantic similarity between two texts using TF-IDF cosine similarity.
    Returns 0.0 (completely different) to 1.0 (identical).
    """
    if not text_a or not text_b:
        return 0.0

    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    # Compute IDF across both documents
    idf = _compute_idf([tokens_a, tokens_b])

    # Compute TF-IDF vectors
    tf_a = _compute_tf(tokens_a)
    tf_b = _compute_tf(tokens_b)

    all_words = set(tf_a.keys()) | set(tf_b.keys())

    vec_a = [tf_a.get(w, 0) * idf.get(w, 0) for w in all_words]
    vec_b = [tf_b.get(w, 0) * idf.get(w, 0) for w in all_words]

    # Cosine similarity
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return round(dot / (mag_a * mag_b), 4)


def compute_structural_similarity(genome_a, genome_b) -> float:
    """
    Compute structural similarity between two VideoGenome objects.
    Delegates to genome's built-in similarity method.
    """
    if hasattr(genome_a, 'similarity_to'):
        return genome_a.similarity_to(genome_b)
    return 0.0


# ── Hook Mutation ────────────────────────────────────────────────────────────

SYNONYM_MAP = {
    "secret": ["hidden", "concealed", "buried", "unknown"],
    "truth": ["reality", "fact", "revelation", "discovery"],
    "dangerous": ["risky", "deadly", "lethal", "hazardous"],
    "powerful": ["potent", "mighty", "dominant", "formidable"],
    "shocking": ["stunning", "jaw-dropping", "mind-blowing", "explosive"],
    "nobody": ["no one", "not a single person", "zero people", "hardly anyone"],
    "everything": ["all of it", "every single thing", "the whole picture", "every aspect"],
    "wrong": ["mistaken", "incorrect", "flawed", "off-base"],
    "change": ["transform", "revolutionize", "reshape", "alter"],
    "stop": ["halt", "pause", "freeze", "hold on"],
    "never": ["not once", "at no point", "not ever", "under no circumstances"],
    "always": ["constantly", "perpetually", "without exception", "every single time"],
    "money": ["wealth", "fortune", "cash", "capital"],
    "brain": ["mind", "psychology", "cognition", "mental wiring"],
    "manipulate": ["influence", "control", "exploit", "engineer"],
    "hack": ["trick", "exploit", "shortcut", "workaround"],
}

STRUCTURE_TRANSFORMS = [
    # (pattern, replacement) - for hook restructuring
    (r"^(Stop\.|Wait\.|Hold on\.)\s*", ""),  # Remove pattern interrupt prefix
    (r"\?$", "."),  # Question → statement
    (r"\.$", "?"),  # Statement → question
]


def mutate_hook(hook_text: str) -> str:
    """
    Mutate a hook via synonym replacement and structure reordering.
    Returns a semantically similar but lexically different hook.
    """
    if not hook_text:
        return hook_text

    words = hook_text.split()
    mutated_words = []

    for word in words:
        word_lower = word.lower().strip(".,!?;:")
        if word_lower in SYNONYM_MAP and random.random() < 0.4:
            synonym = random.choice(SYNONYM_MAP[word_lower])
            # Preserve capitalization
            if word[0].isupper():
                synonym = synonym.capitalize()
            mutated_words.append(synonym)
        else:
            mutated_words.append(word)

    result = " ".join(mutated_words)

    # Apply one random structure transform
    if random.random() < 0.3 and STRUCTURE_TRANSFORMS:
        pattern, replacement = random.choice(STRUCTURE_TRANSFORMS)
        result = re.sub(pattern, replacement, result)

    return result.strip()


# ── Structure Mutation ───────────────────────────────────────────────────────

def mutate_structure(script: str) -> str:
    """
    Mutate script structure via paragraph reordering and phrasing variation.
    Keeps hook (first paragraph) and ending (last paragraph) in place.
    Reorders middle sections for structural uniqueness.
    """
    if not script:
        return script

    paragraphs = [p.strip() for p in script.split("\n") if p.strip()]

    if len(paragraphs) <= 3:
        return script

    # Keep first and last, shuffle middle
    hook = paragraphs[0]
    ending = paragraphs[-1]
    middle = paragraphs[1:-1]

    # Shuffle middle with constraints (don't reverse, just swap adjacent pairs)
    for i in range(len(middle) - 1):
        if random.random() < 0.3:
            middle[i], middle[i + 1] = middle[i + 1], middle[i]

    return "\n".join([hook] + middle + [ending])


# ── Phrasing Entropy Injection ───────────────────────────────────────────────

FILLER_VARIATIONS = {
    "However,": ["But here's the thing —", "Yet,", "On the flip side,", "Except —"],
    "In fact,": ["Actually,", "Here's the kicker:", "The data shows:", "Surprisingly,"],
    "For example,": ["Take this:", "Consider:", "Here's proof:", "Look at this:"],
    "This means": ["What this tells us is", "The implication?", "Translation:", "In other words,"],
    "Most people": ["The majority", "Nearly everyone", "99% of people", "Almost nobody realizes"],
}


def inject_entropy(text: str, level: float = 0.3) -> str:
    """
    Word-level phrasing randomization.
    Level 0.0 = no change, 1.0 = maximum variation.
    """
    if not text or level <= 0:
        return text

    result = text
    for phrase, alternatives in FILLER_VARIATIONS.items():
        if phrase in result and random.random() < level:
            replacement = random.choice(alternatives)
            result = result.replace(phrase, replacement, 1)

    # Inject word-level synonyms at controlled rate
    words = result.split()
    for i, word in enumerate(words):
        word_lower = word.lower().strip(".,!?;:")
        if word_lower in SYNONYM_MAP and random.random() < level * 0.3:
            synonym = random.choice(SYNONYM_MAP[word_lower])
            if word[0].isupper():
                synonym = synonym.capitalize()
            words[i] = synonym

    return " ".join(words)


# ── Master Duplication Check ─────────────────────────────────────────────────

def check_duplication(
    script: str,
    genome=None,
    existing_scripts: List[str] = None,
    existing_genomes: List = None,
    max_similarity: float = 0.40,
) -> Dict:
    """
    Check if content is too similar to existing content.

    Returns:
        {
            "passed": True/False,
            "max_semantic_similarity": 0.35,
            "max_structural_similarity": 0.28,
            "most_similar_id": "genome_xxx",
            "threshold": 0.40,
        }
    """
    result = {
        "passed": True,
        "max_semantic_similarity": 0.0,
        "max_structural_similarity": 0.0,
        "most_similar_id": "",
        "threshold": max_similarity,
    }

    # Check semantic similarity against existing scripts
    if existing_scripts:
        for i, existing in enumerate(existing_scripts):
            sim = compute_semantic_similarity(script, existing)
            if sim > result["max_semantic_similarity"]:
                result["max_semantic_similarity"] = sim
                result["most_similar_id"] = f"script_{i}"

    # Check structural similarity against existing genomes
    if genome and existing_genomes:
        for existing_g in existing_genomes:
            sim = compute_structural_similarity(genome, existing_g)
            gid = getattr(existing_g, 'genome_id', 'unknown')
            if sim > result["max_structural_similarity"]:
                result["max_structural_similarity"] = sim
                if sim > result["max_semantic_similarity"]:
                    result["most_similar_id"] = gid

    # Combined score (weighted average)
    combined = max(result["max_semantic_similarity"], result["max_structural_similarity"])

    if combined >= max_similarity:
        result["passed"] = False
        logger.warning(
            f"duplication detected: combined={combined:.2f} >= threshold={max_similarity}. "
            f"Most similar: {result['most_similar_id']}"
        )
    else:
        logger.info(f"duplication check passed: max_similarity={combined:.2f}")

    return result


def auto_rewrite_for_uniqueness(
    script: str,
    existing_scripts: List[str] = None,
    max_attempts: int = 3,
    max_similarity: float = 0.40,
) -> Tuple[str, bool]:
    """
    Automatically rewrite script until it passes duplication check.
    Returns (rewritten_script, passed).
    """
    current = script

    for attempt in range(max_attempts):
        check = check_duplication(current, existing_scripts=existing_scripts, max_similarity=max_similarity)
        if check["passed"]:
            return current, True

        # Apply increasing entropy
        level = 0.3 + (attempt * 0.2)
        current = inject_entropy(current, level=level)
        current = mutate_structure(current)
        logger.info(f"rewrite attempt {attempt + 1}: entropy_level={level:.1f}")

    # Final check
    check = check_duplication(current, existing_scripts=existing_scripts, max_similarity=max_similarity)
    return current, check["passed"]
