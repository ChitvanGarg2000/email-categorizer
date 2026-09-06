"""
Extract job-application metadata (company, role, stage) from emails already
classified as Job/Interview. Reuses the LLM client/tuning from classifier.py.
"""
import json

import httpx

from .classifier import BATCH_SIZE, llm_chat_json, trim_snippet_for_llm

APPLICATION_STAGES = ["Applied", "Interview", "Offer", "Rejected", "Unknown"]

DEFAULT_DETAILS = {"company": None, "role": None, "stage": "Unknown"}

_SYSTEM_PROMPT = """Extract job application details from the email.
Respond with ONLY a JSON object:
{"company": string or null, "role": string or null, "stage": one of ["Applied","Interview","Offer","Rejected","Unknown"]}"""

_BATCH_SYSTEM_PROMPT = """Extract job application details from each email.
Respond with ONLY a JSON array. Each object must have:
{"id": "<message id>", "company": string or null, "role": string or null, "stage": one of ["Applied","Interview","Offer","Rejected","Unknown"]}
The array must contain exactly one object per email, in the same order as provided."""


def _normalize_details(raw: dict) -> dict:
    stage = raw.get("stage", "Unknown")
    if stage not in APPLICATION_STAGES:
        stage = "Unknown"
    company = raw.get("company")
    role = raw.get("role")
    return {
        "company": company if company else None,
        "role": role if role else None,
        "stage": stage,
    }


def _llm_chat(system_prompt: str, user_content: str) -> str:
    return llm_chat_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
    )


def _build_user_content(subject: str, sender: str, snippet: str) -> str:
    return (
        f"Subject: {subject}\n"
        f"From: {sender}\n"
        f"Snippet: {trim_snippet_for_llm(snippet)}"
    )


def extract_application_details(subject: str, sender: str, snippet: str) -> dict:
    user_content = _build_user_content(subject, sender, snippet)
    try:
        raw = _llm_chat(_SYSTEM_PROMPT, user_content)
        return _normalize_details(json.loads(raw))
    except (json.JSONDecodeError, ValueError, KeyError, TypeError, httpx.HTTPError):
        return dict(DEFAULT_DETAILS)


def _build_batch_user_content(batch: list[dict]) -> str:
    parts = []
    for i, email in enumerate(batch, start=1):
        parts.append(
            f"Email {i} (id: {email['id']}):\n"
            + _build_user_content(email["subject"], email["sender"], email["snippet"])
        )
    return "\n\n".join(parts)


def _parse_batch_result(raw: str, batch: list[dict]) -> list[dict]:
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or len(parsed) != len(batch):
        raise ValueError("batch response length mismatch")

    by_id: dict[str, dict] = {}
    for item in parsed:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError("invalid batch item")
        by_id[item["id"]] = item

    results: list[dict] = []
    for email in batch:
        item = by_id.get(email["id"])
        if item is None:
            raise ValueError("missing message id in batch response")
        results.append(_normalize_details(item))
    return results


def extract_application_details_batch(emails: list[dict]) -> dict[str, dict]:
    """
    Batch-extract application details for up to BATCH_SIZE emails per LLM call.

    Each email dict must have: id, subject, sender, snippet.
    Returns {gmail_message_id: details_dict}.
    """
    if not emails:
        return {}

    results: dict[str, dict] = {}

    for i in range(0, len(emails), BATCH_SIZE):
        batch = emails[i : i + BATCH_SIZE]
        if len(batch) == 1:
            email = batch[0]
            results[email["id"]] = extract_application_details(
                email["subject"], email["sender"], email["snippet"]
            )
            continue

        try:
            raw = _llm_chat(_BATCH_SYSTEM_PROMPT, _build_batch_user_content(batch))
            batch_results = _parse_batch_result(raw, batch)
            for email, details in zip(batch, batch_results):
                results[email["id"]] = details
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, httpx.HTTPError):
            for email in batch:
                results[email["id"]] = extract_application_details(
                    email["subject"], email["sender"], email["snippet"]
                )

    return results
