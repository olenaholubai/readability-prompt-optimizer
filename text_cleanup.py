
import re
from typing import Dict, List, Optional, Tuple


SAFE_REPLACEMENTS: Dict[str, str] = {
    "systemic lupus erythematosus": "lupus",
    "healthcare provider":          "doctor",
    "frequent urination":           "peeing a lot",
    "prior to":                     "before",
    "loss of appetite":             "less hunger",
    "hematuria":                    "blood in your urine",
    "proteinuria":                  "protein in your urine",
    "if left untreated":            "without treatment",
    "goes untreated":               "is not treated",
    "go untreated":                 "are not treated",
    "left untreated":               "not treated",
    "erythematosus":                "lupus",
    "autoimmune":                   "immune",
    "inflammation":                 "swelling",
    "specialist":                   "doctor",
    "specialists":                  "doctors",
    "therapies":                    "treatments",
    "therapy":                      "treatment",
    "severity":                     "extent",
    "monitor":                      "check",
    "properly":                     "well",
    "untreated":                    "not treated",
    "suppress":                     "calm",
    "reduce":                       "lower",
    "improve":                      "help",
    "symptoms":                     "signs",
    "tissues":                      "parts",
    "require":                      "need",
    "regularly":                    "often",
    "immediately":                  "right away",
    "necessary":                    "needed",
    "significantly":                "greatly",
    "appointments":                 "visits",
    "appointment":                  "visit",
    "complications":                "problems",
    "complication":                 "problem",
    "laboratory":                   "lab",
    "combination":                  "mix",
    "information":                  "details",
    "important":                    "key",
    "determine":                    "find",
    "condition":                    "disease",
    "adjustment":                   "change",
    "urination":                    "peeing",
    "approximately":                "about",
    "additional":                   "more",
    "individuals":                  "people",
    "numerous":                     "many",
    "assist":                       "help",
    "utilize":                      "use",
    "commence":                     "start",
    "subsequent":                   "later",
    "obtain":                       "get",
    "demonstrate":                  "show",
    "regarding":                    "about",
}


SPLIT_PATTERNS: List[Tuple[str, str]] = [
    (r",\s+which\s+can\s+",    "This can "),
    (r",\s+which\s+may\s+",    "This may "),
    (r",\s+which\s+will\s+",   "This will "),
    (r",\s+which\s+could\s+",  "This could "),
    (r",\s+which\s+helps?\s+", "This helps "),
    (r",\s+which\s+means?\s+", "This means "),
    (r",\s+which\s+is\s+",     "This is "),
    (r",\s+which\s+are\s+",    "These are "),
    (r",\s+which\s+was\s+",    "This was "),
    (r",\s+which\s+were\s+",   "These were "),
    (r",\s+which\s+",           "This "),
    (
        r"\s+that\s+(?=(?:affects?|causes?|leads?|helps?|makes?|harms?"
        r"|damages?|prevents?|protects?|attacks?|reduces?|increases?)\s)",
        "This ",
    ),
    (r",\s+causing\s+",         "This causes "),
    (r",\s+making\s+",          "This makes "),
    (r",\s+leading\s+to\s+",    "This leads to "),
    (r",\s+resulting\s+in\s+",  "This results in "),
    (r",\s+preventing\s+",      "This prevents "),
    (r",\s+helping\s+",         "This helps "),
    (r",\s+allowing\s+",        "This allows "),
    (r",\s+affecting\s+",       "This affects "),
    (r",\s+but\s+",             "But "),
    (r",\s+so\s+",              "So "),
    (r",\s+as\s+(?=(?:it|they|this|that)\s)", "This "),
    (r",\s+because\s+",         "This is because "),
    (
        r",\s+and\s+(?=(?:you|they|this|that|it|the|lupus|kidney|blood)\s)",
        "",
    ),
    (
        r",\s+(?=you\s+(?:may|might|could|can|need|should|experience|notice|feel|have|are|were)\s)",
        "",
    ),
    (
        r"\s+because\s+(?=(?:they|it|this|that|the|your|lupus|kidney)\s)",
        "This is because ",
    ),
]

_BARE_AND_RE = re.compile(
    r"\s+and\s+(?=(?:you|they|this|that|it|the|lupus|kidney|blood)\s)",
    re.IGNORECASE,
)

SPLIT_THRESHOLD = 10
BARE_AND_MIN    = 16
MIN_LEFT_WORDS  = 5
MIN_RIGHT_WORDS = 4
MAX_PASSES      = 3


def _wc(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _is_header_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("-"):
        return False
    if re.search(r"[.!?]$", stripped):
        return False
    if len(stripped.split()) > 8:
        return False
    if not re.match(r"^[A-Z]", stripped):
        return False
    return True


def _try_bare_and(sentence: str) -> Optional[List[str]]:
    if _wc(sentence) <= BARE_AND_MIN:
        return None
    for m in _BARE_AND_RE.finditer(sentence):
        left      = sentence[:m.start()].strip()
        right_raw = sentence[m.end():].strip()
        if left.endswith(","):
            continue
        if _wc(left) >= 8 and _wc(right_raw) >= 8:
            if left and left[-1] not in ".!?":
                left += "."
            right = right_raw[0].upper() + right_raw[1:] if right_raw else right_raw
            return [left, right]
    return None


def _split_one(sentence: str, threshold: int = SPLIT_THRESHOLD) -> List[str]:
    if _wc(sentence) <= threshold:
        return [sentence]
    for pattern, prefix in SPLIT_PATTERNS:
        m = re.search(pattern, sentence, re.IGNORECASE)
        if not m:
            continue
        left      = sentence[:m.start()].strip()
        right_raw = sentence[m.end():].strip()
        right_check = prefix + right_raw
        if _wc(left) < MIN_LEFT_WORDS or _wc(right_check) < MIN_RIGHT_WORDS:
            continue
        if left and left[-1] not in ".!?":
            left += "."
        if right_raw:
            right_raw = right_raw[0].lower() + right_raw[1:]
        right = prefix + right_raw
        if right:
            right = right[0].upper() + right[1:]
        return [left, right]
    result = _try_bare_and(sentence)
    if result:
        return result
    return [sentence]


def split_long_sentences(text: str, threshold: int = SPLIT_THRESHOLD) -> str:
    lines  = text.splitlines()
    output = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or _is_header_line(stripped):
            output.append(line)
            continue
        raw_sentences = re.split(r"(?<=[.!?])\s+", stripped)
        result_sentences: List[str] = []
        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            parts = [sentence]
            for _ in range(MAX_PASSES):
                new_parts: List[str] = []
                changed = False
                for part in parts:
                    split = _split_one(part, threshold)
                    new_parts.extend(split)
                    if len(split) > 1:
                        changed = True
                parts = new_parts
                if not changed:
                    break
            result_sentences.extend(parts)
        output.append(" ".join(result_sentences))
    return "\n".join(output)


EXTRACT_THRESHOLD = 12
MIN_LIST_ITEMS    = 3
MAX_ITEM_WORDS    = 9
CLAUSE_STARTERS   = {
    "you", "your", "they", "we", "it", "he", "she",
    "this", "that", "these", "those", "i",
}

_LIST_TRIGGER_RE = re.compile(
    r"^(.+?)\s+(including|such\s+as|includes?|involves?)\s+(.+?)([.!?])?\s*$",
    re.IGNORECASE,
)

_VERB_LIST_RE = re.compile(
    r"^(.+?\b(?:will|can|may|should)\s+(?:\w+\s+)?"
    r"(?:check|order|include|monitor|track|prescribe|perform|test|examine|consider|review))\s+"
    r"((?:[^,]+,\s*){2,}(?:and|or)\s+[^.!?]+)"
    r"([.!?])?\s*$",
    re.IGNORECASE,
)


def _parse_items(raw: str) -> List[str]:
    m = re.match(r"^(.+),\s*(?:and|or)\s+(.+)$", raw.strip(), re.IGNORECASE)
    if m:
        items = [i.strip() for i in m.group(1).split(",")]
        items.append(m.group(2).strip())
    else:
        items = [i.strip() for i in raw.split(",")]
    return [i.rstrip(".,;") for i in items if i.strip()]


def _try_extract_list(sentence: str) -> str:
    if _wc(sentence) < EXTRACT_THRESHOLD:
        return sentence
    m = _LIST_TRIGGER_RE.match(sentence)
    if not m:
        return sentence
    intro, trigger, raw_list = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    if raw_list.count(",") < 2:
        return sentence
    items = _parse_items(raw_list)
    if len(items) < MIN_LIST_ITEMS:
        return sentence
    for item in items:
        first = item.split()[0].lower() if item.split() else ""
        if first in CLAUSE_STARTERS or _wc(item) > MAX_ITEM_WORDS:
            return sentence
    return "\n".join([f"{intro} {trigger}:"] + [f"- {i[0].upper()+i[1:]}" for i in items])


def _try_extract_verb_list(sentence: str) -> str:
    if _wc(sentence) < EXTRACT_THRESHOLD:
        return sentence
    m = _VERB_LIST_RE.match(sentence)
    if not m:
        return sentence
    intro, raw_list = m.group(1).strip(), m.group(2).strip()
    if raw_list.count(",") < 2:
        return sentence
    items = _parse_items(raw_list)
    if len(items) < MIN_LIST_ITEMS or any(_wc(i) > 12 for i in items):
        return sentence
    return "\n".join([f"{intro}:"] + [f"- {i[0].upper()+i[1:]}" for i in items])


def extract_inline_lists(text: str) -> str:
    lines  = text.splitlines()
    output = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or _is_header_line(stripped):
            output.append(line)
            continue
        converted = _try_extract_list(stripped)
        if converted == stripped:
            converted = _try_extract_verb_list(stripped)
        if converted != stripped:
            output.extend(converted.splitlines())
        else:
            output.append(line)
    return "\n".join(output)


def fix_substitution_collisions(text: str) -> str:
    text = re.sub(r"\b(\w+)\s+and\s+\1\b", r"\1", text, flags=re.IGNORECASE)
    return text


def preserve_case(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def simplify_phrases(text: str, replacements: Dict[str, str] | None = None) -> str:
    if not text:
        return text
    replacements = replacements or SAFE_REPLACEMENTS
    for old in sorted(replacements, key=len, reverse=True):
        pattern = re.compile(rf"\b{re.escape(old)}\b", re.IGNORECASE)
        text = pattern.sub(
            lambda m, o=old, r=replacements[old]: preserve_case(m.group(0), r),
            text,
        )
    return text


def remove_markdown_title(text: str) -> str:
    if not text:
        return text
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    if not lines:
        return text
    first = re.sub(r"^[#*\s]+|[#*\s]+$", "", lines[0]).strip().lower()
    if first in {"lupus nephritis", "patient education", "lupus nephritis patient education"}:
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
    return "\n".join(lines)


def normalize_bullets(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[•*–—-]\s*", stripped):
            content = re.sub(r"^[•*–—-]\s*", "", stripped).strip()
            lines.append(f"- {content}")
        else:
            lines.append(line.rstrip())
    return "\n".join(lines)


def normalize_headings(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"^\*\*(.*?)\*\*$", r"\1", stripped)
        lines.append(stripped if stripped else "")
    return "\n".join(lines)


def fix_encoding_artifacts(text: str) -> str:
    for old, new in [
        ("\u00c2\u00b0", "\u00b0"), ("\u00e2\u0080\u00a2", "-"),
        ("\u00e2\u0080\u0093", "-"), ("\u00e2\u0080\u0094", "-"),
        ("\u00e2\u0080\u0099", "'"), ("\u00e2\u0080\u009c", '"'),
        ("\u00e2\u0080\u009d", '"'),
    ]:
        text = text.replace(old, new)
    return text


def fix_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"([.!?])([A-Z])", r"\1 \2", text)
    cleaned = []
    for line in text.splitlines():
        if line.strip().startswith("-"):
            cleaned.append(re.sub(r"[ \t]+", " ", line.strip()))
        else:
            cleaned.append(re.sub(r"[ \t]+", " ", line).strip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()


def fix_line_capitalization(text: str) -> str:
    fixed = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            fixed.append("")
            continue
        prefix  = "- " if stripped.startswith("-") else ""
        content = stripped[1:].strip() if prefix else stripped
        if content and content[0].islower():
            content = content[0].upper() + content[1:]
        fixed.append(prefix + content)
    return "\n".join(fixed)


def simplify_pipeline(text: str) -> str:
    if not text:
        return text
    text = fix_encoding_artifacts(text)
    text = remove_markdown_title(text)
    text = normalize_headings(text)
    text = normalize_bullets(text)
    text = split_long_sentences(text)
    text = extract_inline_lists(text)
    text = simplify_phrases(text)
    text = fix_substitution_collisions(text)
    text = fix_line_capitalization(text)
    return fix_spacing(text)
