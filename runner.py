import csv
import datetime
import json
import math
import os
import random
import re
import sys
import uuid

import requests

sys.path.insert(0, os.path.dirname(__file__))

from benchmark.questions import QUESTIONS, STRUCTURES
from evaluator import score_output
from judge import judge_output
from prompts.mutator import build_prompt_from_slots, get_slot_combos
from prompts.reviser import REVISION_SYSTEM, build_revision_message
from prompts.seeds import SEED_PROMPTS, SYSTEM_FIXED
from text_cleanup import simplify_pipeline

VALUE_STATS_PATH = os.path.join("results", "value_stats.json")


def normalize_for_scoring(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = text.replace("**", "").replace("â€¢", "-").replace("•", "-")
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
        elif stripped.startswith(("-", "*")):
            lines.append("- " + re.sub(r"^[*-]\s*", "", stripped).strip())
        else:
            lines.append(re.sub(r"[ \t]+", " ", stripped))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def format_structure_block(structure: list[str]) -> str:
    return "REQUIRED SECTIONS:\n" + "\n".join(structure)


def build_seed_prompt(seed_data: dict, structure: list[str]) -> str:
    keys = ["sentence_rule", "word_choice", "list_rule", "paragraph_rule", "term_rule", "clarity_rule"]
    instructions = "\n\n".join(seed_data[key] for key in keys if seed_data.get(key))
    return f"{SYSTEM_FIXED}\n\n{format_structure_block(structure)}\n\n--- WRITING INSTRUCTIONS ---\n{instructions}"


def safe_text_for_csv(text: str, limit: int = 12000) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def call_lm_studio(system_prompt: str, user_message: str, url: str, model: str, max_tokens: int = 1200) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=180)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def revise_output(draft: str, question: str, structure: list[str], url: str, model: str) -> str:
    return call_lm_studio(
        REVISION_SYSTEM,
        build_revision_message(question, structure, draft),
        url,
        model,
        max_tokens=1200,
    )


def passes_target(scores, fk_min, fk_max, smog_max, fog_max, avg_sent_max, sent_over_12_max, jargon_max):
    return (
        fk_min <= scores.get("flesch_kincaid_grade", 999) <= fk_max
        and scores.get("smog_grade", 999) <= smog_max
        and scores.get("gunning_fog", 999) <= fog_max
        and scores.get("avg_sentence_words", 999) <= avg_sent_max
        and scores.get("sentences_over_12", 999) <= sent_over_12_max
        and scores.get("jargon_count", 999) <= jargon_max
    )


def passes_quality_gates(
    judge: dict,
    scores: dict,
    question_answered_min: int,
    summary_alignment_min: int,
    reference_clarity_min: int,
    actionability_min: int,
    medical_accuracy_min: int,
    ambiguous_pronoun_max: int,
    second_person_min: int,
):
    required = [
        judge.get("question_answered"),
        judge.get("summary_alignment"),
        judge.get("reference_clarity"),
        judge.get("actionability"),
        judge.get("medical_accuracy"),
    ]
    if any(value is None for value in required):
        return False
    return (
        judge["question_answered"] >= question_answered_min
        and judge["summary_alignment"] >= summary_alignment_min
        and judge["reference_clarity"] >= reference_clarity_min
        and judge["actionability"] >= actionability_min
        and judge["medical_accuracy"] >= medical_accuracy_min
        and bool(judge.get("no_major_safety_issue"))
        and scores.get("ambiguous_pronoun_count", 999) <= ambiguous_pronoun_max
        and not scores.get("generic_summary", False)
        and scores.get("second_person_sentence_count", 0) >= second_person_min
    )


def readability_objective(scores, fk_min, fk_max, smog_max, fog_max, avg_sent_max, sent_over_12_max, jargon_max):
    fk = scores.get("flesch_kincaid_grade", 999)
    penalty = 0.0
    if fk < fk_min:
        penalty += (fk_min - fk) * 3.0
    elif fk > fk_max:
        penalty += (fk - fk_max) * 3.0
    penalty += max(0, scores.get("smog_grade", 999) - smog_max) * 4.0
    penalty += max(0, scores.get("gunning_fog", 999) - fog_max) * 2.0
    penalty += max(0, scores.get("avg_sentence_words", 999) - avg_sent_max) * 1.5
    penalty += max(0, scores.get("sentences_over_12", 999) - sent_over_12_max)
    penalty += max(0, scores.get("jargon_count", 999) - jargon_max) * 1.5
    penalty += scores.get("ambiguous_pronoun_count", 0) * 2.0
    penalty += scores.get("passive_voice_count", 0) * 0.25
    return -penalty


def combined_objective_score(readability_score: float, judge: dict, scores: dict) -> float:
    quality = (
        3.0 * (judge.get("question_answered") or 0)
        + 3.0 * (judge.get("medical_accuracy") or 0)
        + 2.0 * (judge.get("summary_alignment") or 0)
        + 2.0 * (judge.get("reference_clarity") or 0)
        + 1.5 * (judge.get("actionability") or 0)
        + 1.5 * (judge.get("natural_score") or 0)
    )
    quality += min(scores.get("direct_action_count", 0), 6) * 0.15
    quality += min(scores.get("second_person_sentence_count", 0), 8) * 0.10
    quality -= scores.get("ambiguous_pronoun_count", 0) * 1.5
    quality -= 5.0 if scores.get("generic_summary") else 0.0
    quality -= 2.0 if scores.get("second_person_sentence_count", 0) < 3 else 0.0
    quality -= 20.0 if not judge.get("no_major_safety_issue") else 0.0
    return round(quality + readability_score, 3)


def load_value_stats():
    if os.path.exists(VALUE_STATS_PATH):
        try:
            with open(VALUE_STATS_PATH, encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_value_stats(stats: dict):
    os.makedirs(os.path.dirname(VALUE_STATS_PATH), exist_ok=True)
    with open(VALUE_STATS_PATH, "w", encoding="utf-8") as file:
        json.dump(stats, file, indent=2, ensure_ascii=False)


def update_value_stats(stats: dict, combo: dict, score: float):
    for field, value in combo.items():
        entry = stats.setdefault(field, {}).setdefault(value, {"n": 0, "avg_score": 0.0})
        entry["avg_score"] = (entry["avg_score"] * entry["n"] + score) / (entry["n"] + 1)
        entry["n"] += 1


def combo_estimated_score(combo: dict, stats: dict) -> float:
    values = []
    for field, value in combo.items():
        known = stats.get(field, {}).get(value)
        if known:
            values.append(known["avg_score"] + 1.0 / math.sqrt(known["n"] + 1))
        else:
            values.append(1.5)
    return sum(values) / max(len(values), 1)


def choose_adaptive_combos(stats: dict, how_many: int):
    pool = get_slot_combos(sample_n=max(how_many * 6, 30))
    return [combo for _, combo in sorted(
        ((combo_estimated_score(combo, stats), combo) for combo in pool),
        key=lambda item: item[0],
        reverse=True,
    )[:how_many]]


def get_prompt_variants_adaptive(max_attempts: int, warmup_attempts: int, stats: dict, structure: list[str]):
    variants = [
        {"source": "baseline", "lineage": name, "combo": {}, "prompt": build_seed_prompt(data, structure)}
        for name, data in SEED_PROMPTS.items()
    ]
    remaining = max(0, max_attempts - len(variants))
    warmup = min(warmup_attempts, remaining)
    for combo in get_slot_combos(sample_n=warmup):
        variants.append({
            "source": "slot_mutation",
            "lineage": "mutated_warmup",
            "combo": combo,
            "prompt": build_prompt_from_slots(combo, structure),
        })
    for combo in choose_adaptive_combos(stats, max(0, max_attempts - len(variants))):
        variants.append({
            "source": "slot_mutation",
            "lineage": "mutated_adaptive",
            "combo": combo,
            "prompt": build_prompt_from_slots(combo, structure),
        })
    return variants[:max_attempts]


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def run_until_target(
    question_item: dict,
    host: str,
    port: int,
    model: str,
    max_attempts: int,
    warmup_attempts: int,
    fk_min: float,
    fk_max: float,
    smog_max: float,
    fog_max: float,
    avg_sent_max: float,
    sent_over_12_max: int,
    jargon_max: int,
    question_answered_min: int = 4,
    summary_alignment_min: int = 4,
    reference_clarity_min: int = 4,
    actionability_min: int = 3,
    medical_accuracy_min: int = 4,
    ambiguous_pronoun_max: int = 1,
    second_person_min: int = 3,
    use_revision_pass: bool = True,
):
    os.makedirs("results", exist_ok=True)
    question = question_item["question"]
    structure = question_item.get("structure") or STRUCTURES[question_item["structure_name"]]
    run_id = str(uuid.uuid4())[:8]
    timestamp = datetime.datetime.now().isoformat()
    url = f"http://{host}:{port}/v1/chat/completions"
    all_json_path = f"results/all_attempts_{run_id}.json"
    best_json_path = f"results/best_result_{run_id}.json"
    csv_path = f"results/all_attempts_{run_id}.csv"

    value_stats = load_value_stats()
    variants = get_prompt_variants_adaptive(max_attempts, warmup_attempts, value_stats, structure)
    attempts = []

    columns = [
        "run_id", "timestamp", "attempt", "source", "lineage", "combo", "question", "structure",
        "fk_grade", "smog_grade", "fog_grade", "flesch_ease", "avg_sentence_words",
        "sentences_over_12", "jargon_count", "ambiguous_pronoun_count", "passive_voice_count",
        "direct_action_count", "second_person_sentence_count", "generic_summary",
        "natural_score", "question_answered", "summary_alignment", "reference_clarity",
        "actionability", "medical_accuracy", "no_major_safety_issue", "pattern_flags",
        "readability_score", "combined_score", "readability_passed", "quality_passed", "passed",
        "error", "error_message", "prompt", "raw_output", "revised_output", "scoring_text",
    ]

    print(f"Using LM Studio URL: {url}")
    print(f"Question: {question}")
    print(f"Testing {len(variants)} prompt variants")

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()

        for index, variant in enumerate(variants, start=1):
            print(f"[{index}/{len(variants)}] {variant['lineage']}")
            record = {
                "run_id": run_id,
                "timestamp": timestamp,
                "attempt": index,
                "source": variant["source"],
                "lineage": variant["lineage"],
                "combo": variant["combo"],
                "question": question,
                "structure": structure,
                "prompt": variant["prompt"],
                "error": False,
                "error_message": "",
            }
            try:
                raw_output = call_lm_studio(variant["prompt"], question, url, model)
                revised_output = raw_output
                if use_revision_pass:
                    revised_output = revise_output(raw_output, question, structure, url, model)
                cleaned = normalize_for_scoring(simplify_pipeline(revised_output))
                scores = score_output(cleaned)
                judge = judge_output(cleaned, question, url=url, model=model)

                readability_score = readability_objective(
                    scores, fk_min, fk_max, smog_max, fog_max,
                    avg_sent_max, sent_over_12_max, jargon_max,
                )
                readability_passed = passes_target(
                    scores, fk_min, fk_max, smog_max, fog_max,
                    avg_sent_max, sent_over_12_max, jargon_max,
                )
                quality_passed = passes_quality_gates(
                    judge, scores,
                    question_answered_min, summary_alignment_min,
                    reference_clarity_min, actionability_min,
                    medical_accuracy_min, ambiguous_pronoun_max,
                    second_person_min,
                )
                combined_score = combined_objective_score(readability_score, judge, scores)
                passed = readability_passed and quality_passed

                record.update({
                    "raw_output": raw_output,
                    "revised_output": revised_output,
                    "scoring_text": cleaned,
                    "scores": scores,
                    "judge": judge,
                    "readability_score": readability_score,
                    "combined_score": combined_score,
                    "readability_passed": readability_passed,
                    "quality_passed": quality_passed,
                    "passed": passed,
                })
                if variant["combo"]:
                    update_value_stats(value_stats, variant["combo"], combined_score)
                    save_value_stats(value_stats)

                row = {
                    "run_id": run_id,
                    "timestamp": timestamp,
                    "attempt": index,
                    "source": variant["source"],
                    "lineage": variant["lineage"],
                    "combo": json.dumps(variant["combo"], ensure_ascii=False),
                    "question": question,
                    "structure": " | ".join(structure),
                    "fk_grade": scores.get("flesch_kincaid_grade"),
                    "smog_grade": scores.get("smog_grade"),
                    "fog_grade": scores.get("gunning_fog"),
                    "flesch_ease": scores.get("flesch_ease"),
                    "avg_sentence_words": scores.get("avg_sentence_words"),
                    "sentences_over_12": scores.get("sentences_over_12"),
                    "jargon_count": scores.get("jargon_count"),
                    "ambiguous_pronoun_count": scores.get("ambiguous_pronoun_count"),
                    "passive_voice_count": scores.get("passive_voice_count"),
                    "direct_action_count": scores.get("direct_action_count"),
                    "second_person_sentence_count": scores.get("second_person_sentence_count"),
                    "generic_summary": scores.get("generic_summary"),
                    "natural_score": judge.get("natural_score"),
                    "question_answered": judge.get("question_answered"),
                    "summary_alignment": judge.get("summary_alignment"),
                    "reference_clarity": judge.get("reference_clarity"),
                    "actionability": judge.get("actionability"),
                    "medical_accuracy": judge.get("medical_accuracy"),
                    "no_major_safety_issue": judge.get("no_major_safety_issue"),
                    "pattern_flags": "|".join(judge.get("pattern_flags", [])),
                    "readability_score": readability_score,
                    "combined_score": combined_score,
                    "readability_passed": readability_passed,
                    "quality_passed": quality_passed,
                    "passed": passed,
                    "error": False,
                    "error_message": "",
                    "prompt": safe_text_for_csv(variant["prompt"]),
                    "raw_output": safe_text_for_csv(raw_output),
                    "revised_output": safe_text_for_csv(revised_output),
                    "scoring_text": safe_text_for_csv(cleaned),
                }
                writer.writerow(row)
                csv_file.flush()
                print(
                    f"  combined={combined_score:.2f} read={readability_passed} "
                    f"qual={quality_passed} pronouns={scores.get('ambiguous_pronoun_count')} "
                    f"2nd_person={scores.get('second_person_sentence_count')} "
                    f"generic_summary={scores.get('generic_summary')}"
                )
            except Exception as exc:
                record.update({
                    "raw_output": "",
                    "revised_output": "",
                    "scoring_text": "",
                    "scores": {},
                    "judge": {},
                    "readability_score": -999,
                    "combined_score": -999,
                    "readability_passed": False,
                    "quality_passed": False,
                    "passed": False,
                    "error": True,
                    "error_message": str(exc),
                })
                writer.writerow({
                    **{column: "" for column in columns},
                    "run_id": run_id,
                    "timestamp": timestamp,
                    "attempt": index,
                    "source": variant["source"],
                    "lineage": variant["lineage"],
                    "combo": json.dumps(variant["combo"]),
                    "question": question,
                    "structure": " | ".join(structure),
                    "error": True,
                    "error_message": str(exc),
                    "prompt": safe_text_for_csv(variant["prompt"]),
                })
                print(f"  ERROR: {exc}")
            attempts.append(record)
            _write_json(all_json_path, attempts)

    valid = [record for record in attempts if not record.get("error")]
    passing = [record for record in valid if record.get("passed")]
    pool = passing or valid
    best = max(pool, key=lambda record: record.get("combined_score", -999)) if pool else None
    result = {
        "run_id": run_id,
        "question": question,
        "passed": bool(best and best.get("passed")),
        "best": best,
        "attempt_count": len(attempts),
        "passing_count": len(passing),
        "all_attempts_path": all_json_path,
        "csv_path": csv_path,
    }
    _write_json(best_json_path, result)
    print(f"Best result: {best_json_path}")
    return result


if __name__ == "__main__":
    print("Run this module through main.py")
