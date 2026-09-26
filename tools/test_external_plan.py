import copy
import json
import unittest
from collections import Counter

from build_external_plan import SOURCE, extract_external, validate_external


class ExternalPlanTests(unittest.TestCase):
    def setUp(self):
        self.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_exact_site_inventory_without_house(self):
        before = copy.deepcopy(self.source)
        result = extract_external(self.source)
        validate_external(self.source, result)
        self.assertEqual(self.source, before)
        self.assertEqual(len(result["walls"]), 7)
        self.assertEqual(Counter(item["elementKind"] for item in result["elements"]), {
            "avocado-tree": 6, "building": 6, "road": 2, "grass": 5,
            "pool": 1, "ninja-set": 1, "table": 1, "chair": 6,
        })
        self.assertEqual(len(result["floors"]), 1)
        self.assertTrue(result["floors"][0]["exteriorOnly"])
        self.assertEqual(len(result["boundaries"]), 1)

    def test_extraction_retains_source_edits_not_hardcoded_styles_or_positions(self):
        item = next(item for item in self.source["elements"] if item.get("context"))
        item.update(color="#abcdef", x=42.75, opacity=.43, rotation=17)
        result = extract_external(self.source)
        validate_external(self.source, result)
        copied = next(entry for entry in result["elements"] if entry["name"] == item["name"])
        for field in ("x", "opacity", "rotation", "color"):
            self.assertEqual(copied[field], item[field])
        copied["color"] = "#000000"
        self.assertEqual(item["color"], "#abcdef")

    def test_incomplete_dining_assembly_requires_review(self):
        self.source["elements"] = [item for item in self.source["elements"]
                                   if not item["id"].endswith("-garden-chair-6")]
        with self.assertRaisesRegex(ValueError, "outdoor dining assembly changed"):
            extract_external(self.source)


if __name__ == "__main__":
    unittest.main()
