
import re
from typing import Dict, List

PRONOUNS = {"it", "this", "that", "they", "these", "those"}

ACTION_VERBS = {
    "ask", "call", "tell", "take", "keep", "check", "track", "avoid",
    "report", "schedule", "contact", "follow", "bring", "write", "wait",
    "limit", "stop", "protect", "watch", "record", "discuss",
}

VAGUE_PHRASES = [
    r"\bways to treat it\b",
    r"\bmanage it\b",
    r"\bprotect it\b",
    r"\bhow it affects\b",
    r"\bwhen it gets worse\b",
    r"\bthis problem\b",
    r"\bwhy it happens\b",
    r"\bhow it works\b",
    r"\btreat it\b",
]

DUMMY_IT_PATTERNS = [
    r"^[-\s]*it is (important|essential|necessary|crucial|vital|key)\b",
    r"^[-\s]*it is (a good idea|best|possible|likely|common)\b",
    r"^[-\s]*it can be (hard|difficult|important|helpful)\b",
]

GENERIC_SUMMARY_FULL = [
    r"^lupus nephritis is a kidney problem caused by lupus\.?$",
    r"^it is a serious problem that affects your kidneys\.?$",
    r"^it is when lupus harms your kidneys\.?$",
]

GENERIC_SUMMARY_FIRST_SENTENCE = [
    r"\bit is when lupus\b",
    r"\bit is a (serious|bad|severe|critical) (problem|condition|disease|issue)\b",
    r"\bit is a kidney problem\b",
    r"\blupus nephritis is a (serious|bad) problem\b",
    r"\bit means lupus is harming\b",
    r"\bit is a bad\b",
]


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def extract_section(text: str, heading: str) -> str:
    lines = (text or "").splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower().rstrip(":") == heading.lower().rstrip(":"):
            start = index + 1
            break
    if start is None:
        return ""
    collected = []
    for line in lines[start:]:
        stripped = line.strip()
        if collected and stripped and not stripped.startswith("-") and re.fullmatch(r"[A-Z][^.!?]{0,70}", stripped):
            break
        collected.append(line)
    return "\n".join(collected).strip()


def ambiguous_pronoun_examples(text: str) -> List[str]:
    sentences = split_sentences(text)
    examples = []
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()

        if any(re.search(pattern, lower) for pattern in VAGUE_PHRASES):
            examples.append(sentence)
            continue

        if any(re.search(pattern, lower) for pattern in DUMMY_IT_PATTERNS):
            examples.append(sentence)
            continue

        first = re.match(r"^[\-\s]*(it|this|that|they|these|those)\b", lower)
        if first:
            previous = sentences[index - 1].lower() if index else ""
            if not re.search(
                r"\b(lupus|kidneys?|biopsy|treatments?|medicines?|drugs?|tests?|doctors?|steroids?|dialysis|transplant|signs?|swelling|blood|urine)\b",
                previous,
            ):
                examples.append(sentence)

    return examples[:5]


def actionability_metrics(text: str) -> Dict[str, int]:
    words = re.findall(r"[A-Za-z']+", (text or "").lower())
    sentences = split_sentences(text)
    direct_actions = sum(1 for word in words if word in ACTION_VERBS)
    second_person = sum(1 for word in words if word in {"you", "your", "you're", "you'll"})
    second_person_sentences = sum(
        1 for sentence in sentences if re.search(r"\b(you|your|you're|you'll)\b", sentence, re.I)
    )
    return {
        "direct_action_count": direct_actions,
        "second_person_count": second_person,
        "second_person_sentence_count": second_person_sentences,
    }


def passive_voice_examples(text: str) -> List[str]:
    pattern = re.compile(
        r"\b(?:am|is|are|was|were|be|been|being|will be|may be|might be|can be|should be)\s+"
        r"(?:\w+ly\s+)?\w+(?:ed|en)\b",
        re.I,
    )
    return [sentence for sentence in split_sentences(text) if pattern.search(sentence)][:5]


def summary_metrics(text: str) -> Dict[str, object]:
    summary = extract_section(text, "In Short")
    full_normalized = re.sub(r"\s+", " ", summary.strip().lower())

    generic_full = any(re.fullmatch(pattern, full_normalized) for pattern in GENERIC_SUMMARY_FULL)

    first_sent = re.split(r"(?<=[.!?])\s+", full_normalized)[0].strip() if full_normalized else ""
    generic_first = any(re.search(pattern, first_sent) for pattern in GENERIC_SUMMARY_FIRST_SENTENCE)

    return {
        "in_short_text": summary,
        "in_short_present": bool(summary),
        "generic_summary": generic_full or generic_first,
    }


def deterministic_quality_metrics(text: str) -> Dict[str, object]:
    ambiguous = ambiguous_pronoun_examples(text)
    passive = passive_voice_examples(text)
    metrics = {
        "ambiguous_pronoun_count": len(ambiguous),
        "ambiguous_pronoun_examples": ambiguous,
        "passive_voice_count": len(passive),
        "passive_voice_examples": passive,
    }
    metrics.update(actionability_metrics(text))
    metrics.update(summary_metrics(text))
    return metrics
