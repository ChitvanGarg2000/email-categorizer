"""
Hybrid classifier: cheap rule-based pass first (catches obvious cases for
free), falls back to an LLM call for anything ambiguous. This is the
"tier 1 + tier 3" hybrid approach from the architecture discussion --
tier 2 (embeddings/clustering) is a reasonable v2 addition, skipped here
to keep the MVP scope tight.
"""
import json
import re

from .config import CATEGORIES
from .llm_client import chat_json

# --- Tier 1: rule-based fast path -------------------------------------------------

_SENDER_RULES = [
    (r"noreply@.*(newsletter|substack|medium)", "Newsletter/Promotions"),
    (r"@linkedin\.com", "Job/Interview"),
    (r"@naukri\.com|@indeed\.com|talent\.|recruit", "Job/Interview"),
]

_SUBJECT_RULES = [
    (r"\b(interview|application received|offer letter|hiring)\b", "Job/Interview"),
    (r"\b(invoice|bill due|payment (due|received)|autopay|statement)\b", "Bills/Payments"),
    (r"\b(unsubscribe|% off|sale ends|newsletter)\b", "Newsletter/Promotions"),
]

_SNIPPET_LLM_MAX = 150
_BATCH_SIZE = 10


def normalize_sender(sender: str) -> str:
    """Extract the email address from a From header, ignoring display name and casing."""
    match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", sender)
    return match.group(0).lower() if match else sender.lower().strip()


def build_sender_history(emails: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    """Map normalized sender -> {category: count} from prior classified rows."""
    history: dict[str, dict[str, int]] = {}
    for sender, category in emails:
        norm = normalize_sender(sender)
        history.setdefault(norm, {})
        history[norm][category] = history[norm].get(category, 0) + 1
    return history


def sender_cache_lookup(
    sender_history: dict[str, dict[str, int]], sender: str
) -> str | None:
    """Return a cached category when the same sender was classified >=2 times."""
    counts = sender_history.get(normalize_sender(sender), {})
    best_category = None
    best_count = 0
    for category, count in counts.items():
        if count >= 2 and count > best_count:
            best_category = category
            best_count = count
    return best_category


def rule_based_classify(subject: str, sender: str) -> str | None:
    subject_l = subject.lower()
    sender_l = sender.lower()

    for pattern, category in _SENDER_RULES:
        if re.search(pattern, sender_l):
            return category
    for pattern, category in _SUBJECT_RULES:
        if re.search(pattern, subject_l):
            return category
    return None


# --- Tier 3: LLM classification for anything the rules didn't catch ---------------

_SYSTEM_PROMPT = f"""You classify emails into exactly one of these categories:
{", ".join(CATEGORIES)}

Respond with ONLY a JSON object, no other text, in this exact shape:
{{"category": "<one of the categories above>", "confidence": <0.0-1.0>}}"""

_BATCH_SYSTEM_PROMPT = f"""You classify emails into exactly one of these categories:
{", ".join(CATEGORIES)}

Respond with ONLY a JSON array, no other text. Each object must have:
{{"id": "<message id>", "category": "<one of the categories above>", "confidence": <0.0-1.0>}}

The array must contain exactly one object per email, in the same order as provided."""


def _trim_snippet_for_llm(snippet: str) -> str:
    return snippet[:_SNIPPET_LLM_MAX]


def _parse_single_llm_result(raw: str) -> tuple[str, float]:
    try:
        parsed = json.loads(raw)
        category = parsed["category"]
        confidence = float(parsed["confidence"])
        if category not in CATEGORIES:
            category = "Other"
        return category, confidence
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return "Other", 0.0


def llm_classify(subject: str, sender: str, snippet: str) -> tuple[str, float]:
    user_content = (
        f"Subject: {subject}\n"
        f"From: {sender}\n"
        f"Snippet: {_trim_snippet_for_llm(snippet)}"
    )

    raw = chat_json(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
    )
    return _parse_single_llm_result(raw)


def _build_batch_user_content(batch: list[dict]) -> str:
    parts = []
    for i, email in enumerate(batch, start=1):
        parts.append(
            f"Email {i} (id: {email['id']}):\n"
            f"Subject: {email['subject']}\n"
            f"From: {email['sender']}\n"
            f"Snippet: {_trim_snippet_for_llm(email['snippet'])}"
        )
    return "\n\n".join(parts)


def _parse_batch_llm_result(raw: str, batch: list[dict]) -> list[tuple[str, float]]:
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or len(parsed) != len(batch):
        raise ValueError("batch response length mismatch")

    by_id: dict[str, dict] = {}
    for item in parsed:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError("invalid batch item")
        by_id[item["id"]] = item

    results: list[tuple[str, float]] = []
    for email in batch:
        item = by_id.get(email["id"])
        if item is None:
            raise ValueError("missing message id in batch response")
        category = item["category"]
        confidence = float(item["confidence"])
        if category not in CATEGORIES:
            category = "Other"
        results.append((category, confidence))
    return results


def _llm_classify_batch(batch: list[dict]) -> list[tuple[str, float]]:
    if not batch:
        return []
    if len(batch) == 1:
        email = batch[0]
        return [llm_classify(email["subject"], email["sender"], email["snippet"])]

    user_content = _build_batch_user_content(batch)
    try:
        raw = chat_json(
            [
                {"role": "system", "content": _BATCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]
        )
        return _parse_batch_llm_result(raw, batch)
    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        return [
            llm_classify(email["subject"], email["sender"], email["snippet"])
            for email in batch
        ]


def classify_email(subject: str, sender: str, snippet: str) -> tuple[str, float, str]:
    """Returns (category, confidence, method)."""
    rule_category = rule_based_classify(subject, sender)
    if rule_category:
        return rule_category, 1.0, "rule"

    category, confidence = llm_classify(subject, sender, snippet)
    return category, confidence, "llm"


def classify_batch(
    emails: list[dict],
    sender_history: dict[str, dict[str, int]] | None = None,
) -> dict[str, tuple[str, float, str]]:
    """
    Classify a list of emails using rules, sender cache, then batched LLM calls.

    Each email dict must have keys: id, subject, sender, snippet.
    Returns {message_id: (category, confidence, method)}.
    """
    if sender_history is None:
        sender_history = {}

    results: dict[str, tuple[str, float, str]] = {}
    llm_queue: list[dict] = []

    for email in emails:
        rule_category = rule_based_classify(email["subject"], email["sender"])
        if rule_category:
            results[email["id"]] = (rule_category, 1.0, "rule")
            continue

        cached_category = sender_cache_lookup(sender_history, email["sender"])
        if cached_category:
            results[email["id"]] = (cached_category, 1.0, "sender_cache")
            continue

        llm_queue.append(email)

    for i in range(0, len(llm_queue), _BATCH_SIZE):
        batch = llm_queue[i : i + _BATCH_SIZE]
        batch_results = _llm_classify_batch(batch)
        for email, (category, confidence) in zip(batch, batch_results):
            results[email["id"]] = (category, confidence, "llm")

    return results


# Public aliases for reuse by application_extractor (same LLM settings/tuning).
BATCH_SIZE = _BATCH_SIZE
trim_snippet_for_llm = _trim_snippet_for_llm
llm_chat_json = chat_json
