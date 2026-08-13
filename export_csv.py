
import csv
import json
import os
import sys

SCORE_FIELDS = [
    "flesch_ease", "flesch_kincaid_grade", "smog_grade", "gunning_fog",
    "avg_sentence_words", "sentences_over_12", "jargon_count", "long_word_count",
    "poly_rate", "total_sentences", "word_count", "ambiguous_pronoun_count",
    "passive_voice_count", "direct_action_count", "second_person_count",
    "second_person_sentence_count", "generic_summary", "in_short_present",
]
JUDGE_FIELDS = [
    "natural_score", "question_answered", "summary_alignment", "reference_clarity",
    "actionability", "medical_accuracy", "no_major_safety_issue", "pattern_flags",
    "one_line_note",
]
CSV_COLUMNS = [
    "run_id", "timestamp", "source", "lineage", "combo_str", "question",
    "output", "revised_output", "scoring_text",
] + SCORE_FIELDS + JUDGE_FIELDS + [
    "readability_score", "combined_score", "readability_passed", "quality_passed", "passed"
]


def flatten(record: dict) -> dict:
    scores, judge, combo = record.get("scores", {}), record.get("judge", {}), record.get("combo", {})
    row = {
        "run_id": record.get("run_id", ""),
        "timestamp": record.get("timestamp", ""),
        "source": record.get("source", ""),
        "lineage": record.get("lineage", ""),
        "combo_str": "; ".join(f"{key}={value}" for key, value in combo.items()),
        "question": record.get("question", ""),
        "output": record.get("output", ""),
        "revised_output": record.get("revised_output", ""),
        "scoring_text": record.get("scoring_text", ""),
        "readability_score": record.get("readability_score", ""),
        "combined_score": record.get("combined_score", ""),
        "readability_passed": record.get("readability_passed", ""),
        "quality_passed": record.get("quality_passed", ""),
        "passed": record.get("passed", ""),
    }
    for field in SCORE_FIELDS:
        row[field] = scores.get(field, "")
    for field in JUDGE_FIELDS:
        value = judge.get(field, "")
        row[field] = "|".join(value) if isinstance(value, list) else value
    return row


def export_csv(run_id: str):
    candidates = [f"results/judged_{run_id}.json", f"results/all_attempts_{run_id}.json"]
    path_in = next((path for path in candidates if os.path.exists(path)), None)
    if not path_in:
        raise FileNotFoundError(f"No judged or all-attempt file found for {run_id}")
    path_out = f"results/results_{run_id}.csv"
    with open(path_in, encoding="utf-8") as file:
        records = json.load(file)
    rows = sorted((flatten(record) for record in records), key=lambda row: row["combined_score"] or -999, reverse=True)
    with open(path_out, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} rows -> {path_out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python export_csv.py <run_id>")
        raise SystemExit(1)
    export_csv(sys.argv[1])
