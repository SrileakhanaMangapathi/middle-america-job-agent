"""NLP-based skill extractor for job descriptions."""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Curated skill catalogue (60+ AI/ML/Data Engineering skills)
# ---------------------------------------------------------------------------

_SKILL_CATALOGUE: List[str] = [
    # Languages
    "python",
    "r",
    "scala",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "c++",
    "c#",
    "sql",
    "bash",
    "shell",
    # ML / DL frameworks
    "tensorflow",
    "pytorch",
    "keras",
    "scikit-learn",
    "xgboost",
    "lightgbm",
    "catboost",
    "jax",
    "onnx",
    # LLM / NLP
    "llm",
    "nlp",
    "langchain",
    "llamaindex",
    "huggingface",
    "transformers",
    "openai",
    "gpt",
    "bert",
    "spacy",
    "nltk",
    "rag",
    "vector database",
    "embedding",
    # Data engineering
    "spark",
    "pyspark",
    "kafka",
    "airflow",
    "dbt",
    "flink",
    "hadoop",
    "hive",
    "presto",
    "trino",
    "databricks",
    "snowflake",
    "redshift",
    "bigquery",
    # Cloud & infra
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "terraform",
    "mlflow",
    "kubeflow",
    "sagemaker",
    "vertex ai",
    # General ML concepts
    "machine learning",
    "deep learning",
    "computer vision",
    "reinforcement learning",
    "feature engineering",
    "model deployment",
    "data pipeline",
    # Databases / search
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "pinecone",
    "weaviate",
    "chroma",
    # Tools / practices
    "git",
    "ci/cd",
    "rest api",
    "graphql",
    "pandas",
    "numpy",
    "matplotlib",
    "jupyter",
]

# Pre-compile a regex for each skill (word-boundary aware, case-insensitive).
_SKILL_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    (skill, re.compile(r"\b" + re.escape(skill) + r"\b", re.IGNORECASE))
    for skill in _SKILL_CATALOGUE
]

# ---------------------------------------------------------------------------
# Lazy-load spaCy model
# ---------------------------------------------------------------------------

_nlp: Optional[Any] = None  # lazily set to a spaCy model or False (unavailable)


def _get_nlp():  # type: ignore[return]
    """Return a spaCy Language model, loading it lazily on first call.

    Tries ``en_core_web_sm`` first; falls back to ``spacy.blank("en")`` if
    the model is not installed.  Returns ``None`` if spaCy is not available
    at all, so callers can skip NLP-based extraction gracefully.
    """
    global _nlp
    if _nlp is None:
        try:
            import spacy

            _nlp = spacy.load("en_core_web_sm")
        except (ImportError, OSError):
            try:
                import spacy

                _nlp = spacy.blank("en")
            except ImportError:
                _nlp = False  # spaCy not available at all
    return _nlp if _nlp is not False else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_skills(description: str) -> Tuple[List[str], List[str]]:
    """Extract required and preferred skills from a job description.

    Skills mentioned in the first 40% of the text are classified as
    *required*; skills that appear **only** in the remaining 60% are
    classified as *preferred*.

    Args:
        description: Raw job description text.

    Returns:
        A tuple ``(required_skills, preferred_skills)``.
    """
    if not description or not description.strip():
        return [], []

    cutoff = max(1, int(len(description) * 0.4))
    early_text = description[:cutoff]
    full_text = description

    required: List[str] = []
    preferred: List[str] = []

    for skill, pattern in _SKILL_PATTERNS:
        in_full = bool(pattern.search(full_text))
        if not in_full:
            continue
        if pattern.search(early_text):
            required.append(skill)
        else:
            preferred.append(skill)

    # Bonus pass: spaCy noun-chunk extraction for multi-word technical terms
    nlp = _get_nlp()
    if nlp is not None:
        doc = nlp(description)
        catalogue_lower = {s.lower() for s in _SKILL_CATALOGUE}
        required_set = set(required)
        preferred_set = set(preferred)
        for chunk in doc.noun_chunks:
            term = chunk.text.strip().lower()
            if (
                term not in catalogue_lower
                and term not in required_set
                and term not in preferred_set
                and len(term.split()) > 1
                and re.search(r"[a-z]", term)
            ):
                chunk_start = chunk.start_char
                if chunk_start < cutoff:
                    required.append(term)
                    required_set.add(term)
                else:
                    preferred.append(term)
                    preferred_set.add(term)

    return required, preferred
