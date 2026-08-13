import unittest
from text_cleanup import (
    simplify_pipeline,
    split_long_sentences,
    extract_inline_lists,
    fix_substitution_collisions,
)


class SentenceSplitterTests(unittest.TestCase):

    def test_splits_at_which_can(self):
        text = (
            "Lupus nephritis causes swelling in the kidney filtering units, "
            "which can lead to reduced kidney function and waste buildup in your blood."
        )
        result = split_long_sentences(text)
        self.assertIn(". ", result)
        self.assertIn("This can lead to", result)
        sentences = [s.strip() for s in result.split(". ") if s.strip()]
        self.assertGreater(len(sentences), 1)

    def test_splits_at_causing(self):
        text = (
            "Lupus attacks the tiny blood vessels in your kidneys, "
            "causing damage and making it hard for them to filter waste."
        )
        result = split_long_sentences(text)
        self.assertIn("This causes", result)

    def test_splits_at_but(self):
        text = (
            "The biopsy is generally safe and takes about thirty minutes, "
            "but you may feel some discomfort at the site afterward."
        )
        result = split_long_sentences(text)
        self.assertIn("But you may", result)

    def test_short_sentence_unchanged(self):
        text = "Lupus can harm your kidneys."
        self.assertEqual(split_long_sentences(text), text)

    def test_bullet_lines_unchanged(self):
        text = "- Take your medicine as directed by your doctor every single day without fail."
        self.assertEqual(split_long_sentences(text), text)

    def test_header_lines_unchanged(self):
        text = "Signs to Watch For"
        self.assertEqual(split_long_sentences(text), text)

    def test_does_not_produce_very_short_fragments(self):
        text = "Swelling can occur, which is bad."
        result = split_long_sentences(text)
        self.assertEqual(result.strip(), text.strip())

    def test_splits_at_leading_to(self):
        text = (
            "Lupus attacks the tiny blood vessels in your kidneys, "
            "leading to damage and making it hard for them to filter waste properly."
        )
        result = split_long_sentences(text)
        self.assertIn("This leads to", result)

    def test_because_without_comma(self):
        text = (
            "You have been given steroids because they are effective "
            "at lowering swelling in the kidneys and protecting them from further damage."
        )
        result = split_long_sentences(text)
        self.assertIn("This is because", result)

    def test_clause_and_split(self):
        text = (
            "Lupus nephritis affects your kidneys, "
            "and you need to follow up with your doctor often."
        )
        result = split_long_sentences(text)
        self.assertIn("You need to follow up", result)

    def test_multiple_long_sentences_both_split(self):
        text = (
            "Lupus attacks the tiny blood vessels in your kidneys, "
            "which can lead to problems with filtering. "
            "Treatment helps lower swelling in your kidneys, "
            "which can protect them from further damage over time."
        )
        result = split_long_sentences(text)
        count = result.count("This can")
        self.assertGreaterEqual(count, 2)


class ListExtractionTests(unittest.TestCase):

    def test_extracts_including_list(self):
        text = (
            "Your doctor orders several blood tests including "
            "a Complete Blood Count, an ESR test, and complement levels."
        )
        result = extract_inline_lists(text)
        self.assertIn("including:", result)
        self.assertIn("- A Complete Blood Count", result)
        self.assertIn("- An ESR test", result)
        self.assertIn("- Complement levels", result)

    def test_extracts_such_as_list(self):
        text = (
            "Your doctor may choose from several treatment options such as "
            "steroids, immune lowering drugs, and biologics."
        )
        result = extract_inline_lists(text)
        self.assertIn("such as:", result)
        self.assertIn("- Steroids", result)

    def test_short_sentence_not_extracted(self):
        text = "Tests include blood work and urine samples."
        result = extract_inline_lists(text)
        self.assertEqual(result, text)

    def test_two_items_not_extracted(self):
        text = (
            "Your doctor orders blood tests including a CBC and an ESR test."
        )
        result = extract_inline_lists(text)
        self.assertNotIn("including:", result)

    def test_clause_items_not_extracted(self):
        text = (
            "Treatment helps such as you can take medicine, "
            "they can check your kidneys, and it can lower swelling."
        )
        result = extract_inline_lists(text)
        self.assertEqual(result, text)

    def test_bullet_lines_unchanged(self):
        text = "- Including blood tests, urine tests, and kidney biopsies."
        self.assertEqual(extract_inline_lists(text), text)


class WordSubstitutionTests(unittest.TestCase):

    def test_regularly_to_often(self):
        result = simplify_pipeline("Check your blood pressure regularly.")
        self.assertIn("often", result.lower())
        self.assertNotIn("regularly", result.lower())

    def test_immediately_to_right_away(self):
        result = simplify_pipeline("Call your doctor immediately.")
        self.assertIn("right away", result.lower())
        self.assertNotIn("immediately", result.lower())

    def test_necessary_to_needed(self):
        result = simplify_pipeline("It is necessary to take your medicine.")
        self.assertIn("needed", result.lower())
        self.assertNotIn("necessary", result.lower())

    def test_appointment_to_visit(self):
        result = simplify_pipeline("Schedule a follow-up appointment with your doctor.")
        self.assertIn("visit", result.lower())
        self.assertNotIn("appointment", result.lower())

    def test_untreated_context_goes(self):
        result = simplify_pipeline("If lupus goes untreated, your kidneys may fail.")
        self.assertNotIn("goes untreated", result.lower())
        self.assertNotIn("goes not treated", result.lower())
        self.assertIn("not treated", result.lower())

    def test_untreated_context_left(self):
        result = simplify_pipeline("If left untreated, kidney damage gets worse.")
        self.assertIn("without treatment", result.lower())

    def test_complication_to_problem(self):
        result = simplify_pipeline("Lupus nephritis is a complication of lupus.")
        self.assertIn("problem", result.lower())
        self.assertNotIn("complication", result.lower())

    def test_treatment_options_preserved(self):
        result = simplify_pipeline("Ask about your treatment options.")
        self.assertIn("treatment options", result.lower())
        self.assertNotIn("ways to treat it", result.lower())

    def test_precise_medical_terms_preserved(self):
        text = "Lupus nephritis affects the kidneys and may require dialysis."
        result = simplify_pipeline(text)
        self.assertIn("lupus", result.lower())
        self.assertIn("nephritis", result.lower())
        self.assertIn("kidneys", result.lower())
        self.assertIn("dialysis", result.lower())


class CollisionFixTests(unittest.TestCase):

    def test_swelling_and_swelling(self):
        text = "reducing swelling and swelling in the kidneys"
        result = fix_substitution_collisions(text)
        self.assertEqual(result, "reducing swelling in the kidneys")

    def test_pipeline_prevents_double_swelling(self):
        text = "reducing inflammation and swelling in the kidneys"
        result = simplify_pipeline(text)
        self.assertNotIn("swelling and swelling", result.lower())
        self.assertIn("swelling", result.lower())

    def test_no_collision_no_change(self):
        text = "swelling and damage to the kidneys"
        result = fix_substitution_collisions(text)
        self.assertEqual(result, text)


class PipelineOrderTests(unittest.TestCase):

    def test_split_before_extract(self):
        text = (
            "Lupus attacks tiny blood vessels in your kidneys, "
            "causing problems including kidney failure, high blood pressure, and swelling."
        )
        result = simplify_pipeline(text)
        self.assertIn("This causes", result)

    def test_full_pipeline_reduces_word_count(self):
        long_sentence = (
            "Lupus nephritis is a key problem of systemic lupus erythematosus (lupus), "
            "an autoimmune disease that affects many parts of your body, "
            "which can lead to reduced kidney function and a buildup of waste products in your blood."
        )
        result = simplify_pipeline(long_sentence)
        sentence_count = len([s for s in re.split(r"(?<=[.!?])\s+", result) if s.strip()])
        self.assertGreaterEqual(sentence_count, 2)


import re

if __name__ == "__main__":
    unittest.main()
