import json
import os
import re
import sys

from quality_checks import deterministic_quality_metrics


def count_syllables(word: str) -> int:
    word = word.lower().strip(".,!?;:\"'()-")
    if not word:
        return 0
    word = re.sub(r"'s$|n't$|'re$|'ve$|'ll$|'d$", "", word)
    vowels = "aeiouy"
    count = 0
    previous_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not previous_vowel:
            count += 1
        previous_vowel = is_vowel
    if word.endswith("e") and len(word) > 2:
        if word[-2] in vowels:
            pass
        elif word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
            pass
        else:
            count -= 1
    if word.endswith("ed") and len(word) > 3 and word[-3] not in "td":
        count = max(count - 1, 1)
    return max(1, count)


def _is_header_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("-"):
        return False
    if re.search(r"[.!?]$", stripped):
        return False
    words = stripped.split()
    if len(words) > 8:
        return False
    if not re.match(r"^[A-Z]", stripped):
        return False
    return True


def tokenize_sentences(text: str):
    if not text:
        return []
    lines = text.strip().splitlines()
    processed = []
    for line in lines:
        if _is_header_line(line):
            processed.append("")
        else:
            processed.append(line)
    clean = "\n".join(processed)
    raw = re.split(r"(?<=[.!?])\s+|\n(?=- )", clean.strip())
    return [s.strip() for s in raw if len(s.strip()) > 3]


def tokenize_words(text: str):
    return re.findall(r"[A-Za-z']+", text or "")


def flesch_reading_ease(text: str) -> float:
    sentences, words = tokenize_sentences(text), tokenize_words(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(count_syllables(word) for word in words)
    return round(206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words)), 2)


def flesch_kincaid_grade(text: str) -> float:
    sentences, words = tokenize_sentences(text), tokenize_words(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(count_syllables(word) for word in words)
    return round(0.39 * (len(words) / len(sentences)) + 11.8 * (syllables / len(words)) - 15.59, 2)


def smog_grade(text: str) -> float:
    sentences, words = tokenize_sentences(text), tokenize_words(text)
    if len(sentences) < 5 or not words:
        return 0.0
    polysyllables = sum(1 for word in words if count_syllables(word) >= 3)
    return round(3.0 + (polysyllables * (30 / len(sentences))) ** 0.5, 2)


def gunning_fog(text: str) -> float:
    sentences, words = tokenize_sentences(text), tokenize_words(text)
    if not sentences or not words:
        return 0.0
    complex_words = sum(1 for word in words if count_syllables(word) >= 3)
    return round(0.4 * ((len(words) / len(sentences)) + 100 * complex_words / len(words)), 2)


def get_polysyllable_words(text: str):
    return [(word, count_syllables(word)) for word in tokenize_words(text) if count_syllables(word) >= 3]


def poly_rate(text: str) -> float:
    words = tokenize_words(text)
    return round(sum(count_syllables(word) >= 3 for word in words) / len(words), 4) if words else 0.0


JARGON_WORDS = [
    "nephritis", "proteinuria", "autoimmune", "immunosuppressive", "hypertension",
    "corticosteroid", "glomerular", "pathophysiology", "etiology", "prognosis",
    "erythematosus", "hydroxychloroquine", "mycophenolate", "cyclophosphamide",
    "azathioprine", "creatinine",
]


def score_output(text: str) -> dict:
    sentences = tokenize_sentences(text)
    words = tokenize_words(text)
    counts = [len(tokenize_words(sentence)) for sentence in sentences]
    over_12 = [sentence for sentence in sentences if len(tokenize_words(sentence)) > 12]
    jargon_hits = [word for word in JARGON_WORDS if re.search(rf"\b{re.escape(word)}\b", text, re.I)]
    long_words = [word for word in words if count_syllables(word) >= 3]
    scores = {
        "flesch_ease": flesch_reading_ease(text),
        "flesch_kincaid_grade": flesch_kincaid_grade(text),
        "smog_grade": smog_grade(text),
        "gunning_fog": gunning_fog(text),
        "avg_sentence_words": round(sum(counts) / len(counts), 1) if counts else 0,
        "sentences_over_12": len(over_12),
        "over_12_examples": over_12[:3],
        "jargon_count": len(jargon_hits),
        "jargon_words": jargon_hits,
        "long_word_count": len(long_words),
        "poly_rate": poly_rate(text),
        "poly_examples": [word for word, _ in get_polysyllable_words(text)[:8]],
        "total_sentences": len(sentences),
        "word_count": len(words),
    }
    scores.update(deterministic_quality_metrics(text))
    return scores


def evaluate_run(run_id: str):
    path_in = f"results/raw_{run_id}.json"
    path_out = f"results/scored_{run_id}.json"
    with open(path_in, encoding="utf-8") as file:
        results = json.load(file)
    skipped = 0
    for record in results:
        if record.get("error"):
            record["scores"] = {}
            skipped += 1
        else:
            text = record.get("scoring_text") or record.get("output", "")
            record["scores"] = score_output(text)
    os.makedirs("results", exist_ok=True)
    with open(path_out, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)
    print(f"Scored {len(results) - skipped} outputs ({skipped} skipped) -> {path_out}")


def _self_test():
    sample = (
        "Why Treatment Helps\nYour doctor uses treatment to protect your kidneys. "
        "Take each medicine as directed.\n\nIn Short\nTreatment can prevent more kidney damage. "
        "Ask your doctor how the team will track your progress."
    )
    for key, value in score_output(sample).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        _self_test()
    elif len(sys.argv) > 1:
        evaluate_run(sys.argv[1])
    else:
        print("Usage: python evaluator.py <run_id> OR python evaluator.py test")
