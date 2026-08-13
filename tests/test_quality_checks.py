import unittest

from quality_checks import ambiguous_pronoun_examples, deterministic_quality_metrics, summary_metrics


class QualityCheckTests(unittest.TestCase):
    def test_flags_vague_treatment_phrase(self):
        examples = ambiguous_pronoun_examples("Your doctor will discuss ways to treat it.")
        self.assertTrue(examples)

    def test_specific_summary_is_not_generic(self):
        text = (
            "Blood Tests\nYour doctor checks kidney function.\n\n"
            "In Short\nBlood and urine tests help diagnose lupus nephritis. "
            "Ask your doctor which tests you need."
        )
        self.assertFalse(summary_metrics(text)["generic_summary"])

    def test_generic_summary_is_flagged(self):
        text = "Treatment\nYour doctor may prescribe medicine.\n\nIn Short\nLupus nephritis is a kidney problem caused by lupus."
        self.assertTrue(summary_metrics(text)["generic_summary"])

    def test_actionability_is_counted(self):
        metrics = deterministic_quality_metrics("Take your medicine. Call your doctor if you have a fever.")
        self.assertGreaterEqual(metrics["direct_action_count"], 2)
        self.assertGreaterEqual(metrics["second_person_sentence_count"], 2)


if __name__ == "__main__":
    unittest.main()
