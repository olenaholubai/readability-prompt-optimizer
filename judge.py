import json
import os
import random
import sys

import requests

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "meta-llama-3.1-70b-instruct"

JUDGE_SYSTEM = """You evaluate patient education text. Return only valid JSON.

Score each item from 1 to 5:
NATURAL_SCORE: 5 is smooth and human; 1 is robotic or broken.
QUESTION_ANSWERED: 5 directly and fully answers the exact question; 1 is generic or off-topic.
SUMMARY_ALIGNMENT: 5 means In Short accurately condenses the answer and next step; 1 is generic, unrelated, missing, or contradictory.
REFERENCE_CLARITY: 5 means every pronoun has a clear reference; 1 has repeated vague uses of it, this, or they.
ACTIONABILITY: 5 gives clear patient-directed actions when appropriate; 1 gives only general description.
MEDICAL_ACCURACY: 5 has no apparent factual or safety concern; 1 contains a dangerous or seriously inaccurate claim.

PATTERN_FLAGS may contain these exact labels:
"choppy_rhythm", "over_defined", "robotic_structure", "incomplete_bullets",
"oversimplified", "unnatural_flow", "generic_summary", "unclear_pronoun",
"weak_patient_action", "passive_voice", "question_not_answered",
"repeated_definition", "medical_accuracy_concern", "unsupported_specific_advice".

Set no_major_safety_issue to true only when there is no major safety concern.

Return exactly:
{"natural_score": 1, "question_answered": 1, "summary_alignment": 1,
 "reference_clarity": 1, "actionability": 1, "medical_accuracy": 1,
 "no_major_safety_issue": true, "pattern_flags": [], "one_line_note": "15 words maximum"}"""


def _fallback(flag: str, note: str) -> dict:
    return {
        "natural_score": None,
        "question_answered": None,
        "summary_alignment": None,
        "reference_clarity": None,
        "actionability": None,
        "medical_accuracy": None,
        "no_major_safety_issue": False,
        "pattern_flags": [flag],
        "one_line_note": note,
    }


def judge_output(text: str, question: str, url: str = LM_STUDIO_URL, model: str = LM_STUDIO_MODEL) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": f"QUESTION:\n{question}\n\nTEXT:\n{text}"},
        ],
        "temperature": 0.0,
        "max_tokens": 350,
    }
    try:
        response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=120)
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"].strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            raw = raw[start:end]
        result = json.loads(raw)
        result.setdefault("pattern_flags", [])
        result.setdefault("one_line_note", "")
        result.setdefault("no_major_safety_issue", False)
        return result
    except json.JSONDecodeError as exc:
        return _fallback("parse_error", f"JSON parse failed: {str(exc)[:50]}")
    except requests.exceptions.ConnectionError:
        return _fallback("lm_studio_offline", "LM Studio is not reachable")
    except Exception as exc:
        return _fallback("error", str(exc)[:80])


def judge_run(run_id: str, sample_n: int = 40):
    path_in = f"results/scored_{run_id}.json"
    path_out = f"results/judged_{run_id}.json"
    with open(path_in, encoding="utf-8") as file:
        results = json.load(file)
    valid = [record for record in results if not record.get("error")]
    sample = random.sample(valid, min(sample_n, len(valid)))
    for index, record in enumerate(sample, start=1):
        text = record.get("scoring_text") or record.get("output", "")
        record["judge"] = judge_output(text, record["question"])
        print(f"[{index}/{len(sample)}] {record['lineage']}: {record['judge'].get('one_line_note', '')}")
    os.makedirs("results", exist_ok=True)
    with open(path_out, "w", encoding="utf-8") as file:
        json.dump(sample, file, indent=2, ensure_ascii=False)
    print(f"Judged {len(sample)} outputs -> {path_out}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        judge_run(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40)
    else:
        print("Usage: python judge.py <run_id> [sample_n]")
