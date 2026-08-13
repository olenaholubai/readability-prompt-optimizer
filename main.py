import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from benchmark.questions import QUESTIONS
from runner import run_until_target


def main():
    parser = argparse.ArgumentParser(description="Patient-education prompt quality optimizer")

    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9916)
    parser.add_argument("--model", default="meta-llama-3.1-70b-instruct")

    parser.add_argument("--max-attempts", type=int, default=200,
                        help="Total prompt variants to try per question (default: 200)")
    parser.add_argument("--warmup-attempts", type=int, default=20,
                        help="Random warmup attempts before adaptive selection (default: 20)")

    parser.add_argument("--fk-min", type=float, default=4.0)
    parser.add_argument("--fk-max", type=float, default=8.5)
    parser.add_argument("--smog-max", type=float, default=9.5)
    parser.add_argument("--fog-max", type=float, default=9.5)
    parser.add_argument("--avg-sent-max", type=float, default=12.0)
    parser.add_argument("--sent-over-12-max", type=int, default=5)
    parser.add_argument("--jargon-max", type=int, default=3)

    parser.add_argument("--question-answered-min", type=int, default=4)
    parser.add_argument("--summary-alignment-min", type=int, default=4)
    parser.add_argument("--reference-clarity-min", type=int, default=4)
    parser.add_argument("--actionability-min", type=int, default=3)
    parser.add_argument("--medical-accuracy-min", type=int, default=4)
    parser.add_argument("--ambiguous-pronoun-max", type=int, default=1,
                        help="Maximum ambiguous pronoun instances allowed (default: 1)")
    parser.add_argument("--second-person-min", type=int, default=3,
                        help="Minimum sentences using you/your (default: 3)")

    parser.add_argument("--no-revision-pass", action="store_true",
                        help="Skip the revision pass (faster, lower quality)")
    parser.add_argument(
        "--questions",
        default=None,
        help="Comma-separated question IDs, e.g. q1,q3. Default: all.",
    )
    args = parser.parse_args()

    questions = QUESTIONS
    if args.questions:
        requested = {item.strip() for item in args.questions.split(",") if item.strip()}
        questions = [item for item in QUESTIONS if item["id"] in requested]
        if not questions:
            parser.error(f"No questions matched: {', '.join(sorted(requested))}")

    print("=" * 72)
    print("PATIENT-EDUCATION PROMPT QUALITY OPTIMIZER")
    print("=" * 72)
    print(f"Questions : {len(questions)}")
    print(f"Attempts  : {args.max_attempts} per question ({args.warmup_attempts} warmup)")
    print(f"Revision  : {'off' if args.no_revision_pass else 'on'}")
    print(
        f"Readability: FK {args.fk_min}-{args.fk_max} | "
        f"SMOG ≤ {args.smog_max} | FOG ≤ {args.fog_max} | "
        f"avg_sent ≤ {args.avg_sent_max} | over_12 ≤ {args.sent_over_12_max}"
    )
    print(
        f"Quality   : answered ≥ {args.question_answered_min} | "
        f"summary ≥ {args.summary_alignment_min} | "
        f"reference_clarity ≥ {args.reference_clarity_min} | "
        f"actionability ≥ {args.actionability_min} | "
        f"accuracy ≥ {args.medical_accuracy_min} | "
        f"pronouns ≤ {args.ambiguous_pronoun_max} | "
        f"second_person ≥ {args.second_person_min}"
    )

    for index, question_item in enumerate(questions, start=1):
        print("\n" + "=" * 72)
        print(f"QUESTION {index}/{len(questions)}: {question_item['question']}")
        print("=" * 72)
        result = run_until_target(
            question_item=question_item,
            host=args.host,
            port=args.port,
            model=args.model,
            max_attempts=args.max_attempts,
            warmup_attempts=args.warmup_attempts,
            fk_min=args.fk_min,
            fk_max=args.fk_max,
            smog_max=args.smog_max,
            fog_max=args.fog_max,
            avg_sent_max=args.avg_sent_max,
            sent_over_12_max=args.sent_over_12_max,
            jargon_max=args.jargon_max,
            question_answered_min=args.question_answered_min,
            summary_alignment_min=args.summary_alignment_min,
            reference_clarity_min=args.reference_clarity_min,
            actionability_min=args.actionability_min,
            medical_accuracy_min=args.medical_accuracy_min,
            ambiguous_pronoun_max=args.ambiguous_pronoun_max,
            second_person_min=args.second_person_min,
            use_revision_pass=not args.no_revision_pass,
        )
        print(f"Result  : {'PASS' if result['passed'] else 'BEST AVAILABLE'}")
        print(f"Passing : {result['passing_count']}/{result['attempt_count']}")


if __name__ == "__main__":
    main()
