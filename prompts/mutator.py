import itertools
import random

SLOT_VARIANTS = {
    "sentence_rule": {
        "strict": (
            "Prefer 6-12 words per sentence. Use one main idea per sentence. "
            "Split longer sentences only when both new sentences remain complete."
        ),
        "moderate": (
            "Prefer 7-12 words per sentence. Allow a slightly longer sentence when "
            "splitting it would reduce clarity."
        ),
        "relaxed": (
            "Aim for sentences under 15 words while keeping natural flow."
        ),
    },
    "word_choice": {
        "meaning_safe": (
            "Use short, familiar words only when they preserve the same medical meaning. "
            "Keep precise terms when a simpler replacement would be vague or inaccurate."
        ),
        "principle_only": (
            "Use everyday language. Avoid formal wording, but do not oversimplify."
        ),
        "patient_friendly": (
            "Choose words a patient is likely to know. Briefly explain necessary medical terms."
        ),
    },
    "list_rule": {
        "concise": (
            "Keep bullets concise, but make each bullet understandable on its own."
        ),
        "complete": (
            "Write each bullet as a complete phrase or sentence with a clear subject or action."
        ),
        "action_led": (
            "When giving advice, begin bullets with direct verbs such as Ask, Call, Take, "
            "Keep, Check, or Tell."
        ),
    },
    "paragraph_rule": {
        "tight": "Use no more than two related sentences per paragraph.",
        "standard": "Use two or three related sentences per paragraph.",
        "flowing": (
            "Group related ideas into short paragraphs. Avoid isolated one-sentence paragraphs "
            "unless the sentence gives an important warning."
        ),
    },
    "clarity_rule": {
        "direct": "Answer the exact question in the first section and remove unrelated background.",
        "meaning_first": (
            "Keep explanations complete and meaningful. Do not simplify away important distinctions."
        ),
        "balanced": (
            "Keep the answer direct, complete, and easy to follow without repeating the same definition."
        ),
    },
    "definition_rule": {
        "only_when_needed": (
            "Define lupus nephritis only when the question or section requires a definition."
        ),
        "brief_context": (
            "Use no more than one brief background sentence before answering the main question."
        ),
        "question_specific": (
            "Do not force a disease definition into answers about tests, treatment, pregnancy, "
            "dialysis, transplant, or follow-up care."
        ),
    },
    "bullet_format_rule": {
        "strict_dash": "Use dash bullets on separate lines.",
        "short_dash": "Use short dash bullets and keep one idea per bullet.",
        "mixed_safe": "Use bullets only where the required section naturally calls for a list.",
    },
    "forbidden_terms_rule": {
        "accuracy_first": (
            "Avoid unnecessary jargon, but keep a medical term when replacing it would change meaning."
        ),
        "explain_terms": "Explain unfamiliar medical terms in the same sentence.",
        "off": "Use technical language only when needed for accuracy.",
    },
    "treatment_rule": {
        "simple_actions": (
            "Explain what each treatment does using active verbs such as calm, lower, protect, or prevent."
        ),
        "plain_treatment": (
            "Describe treatment choices in plain language and connect each choice to its purpose."
        ),
        "doctor_led": (
            "State what your doctor may recommend and what you should ask or report."
        ),
    },
    "question_style_rule": {
        "short_plain": (
            "Write short, natural questions. Repeat the relevant noun when a pronoun could be unclear."
        ),
        "supportive": "Write questions a patient could use during the next visit.",
        "minimal": "Use two or three focused questions that match the topic.",
    },
    "summary_rule": {
        "answer_specific": (
            "In Short must restate the main answer, not a general definition of lupus nephritis."
        ),
        "answer_and_action": (
            "In Short must include the main conclusion and one useful next step."
        ),
        "strict_alignment": (
            "In Short must summarize only points already explained in the answer and add no new facts."
        ),
    },
    "reference_rule": {
        "clear_nouns": (
            "Replace unclear uses of it, this, that, they, or these with the exact noun."
        ),
        "nearby_antecedent": (
            "Each pronoun must refer to one clear noun in the same or previous sentence."
        ),
        "repeat_for_clarity": (
            "Repeat short terms such as treatment, biopsy, lupus, medicine, or your kidneys when needed."
        ),
    },
    "actionability_rule": {
        "second_person": (
            "Use you and your when explaining what the reader should do or expect."
        ),
        "active_voice": (
            "Prefer active voice and name the actor: you, your doctor, or your care team."
        ),
        "patient_steps": (
            "When appropriate, state what to do, when to do it, and whom to contact."
        ),
    },
}


def format_structure_block(structure: list[str]) -> str:
    lines = ["REQUIRED SECTIONS:"]
    lines.extend(structure)
    return "\n".join(lines)


def build_prompt_from_slots(combo: dict, structure: list[str]) -> str:
    from prompts.seeds import SYSTEM_FIXED

    label_map = {
        "sentence_rule": "SENTENCE LENGTH",
        "word_choice": "WORD CHOICE",
        "list_rule": "LIST RULES",
        "paragraph_rule": "PARAGRAPH RULES",
        "clarity_rule": "CLARITY",
        "definition_rule": "DEFINITION",
        "bullet_format_rule": "BULLET FORMAT",
        "forbidden_terms_rule": "TECHNICAL TERMS",
        "treatment_rule": "TREATMENT STYLE",
        "question_style_rule": "QUESTION STYLE",
        "summary_rule": "FINAL SUMMARY",
        "reference_rule": "REFERENCE CLARITY",
        "actionability_rule": "ACTIONABILITY",
    }

    parts = [SYSTEM_FIXED, "", format_structure_block(structure), "", "--- WRITING INSTRUCTIONS ---", ""]
    for slot, variant_key in combo.items():
        parts.append(f"{label_map.get(slot, slot.upper())}:\n{SLOT_VARIANTS[slot][variant_key]}\n")
    return "\n".join(parts)


def get_slot_combos(sample_n=None):
    keys = list(SLOT_VARIANTS.keys())
    if sample_n:
        combos = []
        seen = set()
        max_unique = 1
        for variants in SLOT_VARIANTS.values():
            max_unique *= len(variants)
        target = min(sample_n, max_unique)
        while len(combos) < target:
            combo = {key: random.choice(list(SLOT_VARIANTS[key])) for key in keys}
            marker = tuple(combo.items())
            if marker not in seen:
                seen.add(marker)
                combos.append(combo)
        return combos

    return [
        dict(zip(keys, values))
        for values in itertools.product(*[SLOT_VARIANTS[key].keys() for key in keys])
    ]


SMOG_OVERRIDE_VARIANTS = {
    "strict": (
        "WORD LENGTH PRIORITY:\n"
        "Prefer short words when they preserve the same meaning. Do not replace precise medical "
        "terms with vague words. Never lower word length at the cost of accuracy or clear references."
    ),
    "moderate": (
        "WORD LENGTH RULE:\nPrefer one- or two-syllable words when an equally accurate option exists."
    ),
    "off": "",
}


def build_smog_override_block(variant: str = "strict") -> str:
    return SMOG_OVERRIDE_VARIANTS.get(variant, "")
