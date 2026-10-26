from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "product-validation.yml"


def path_list_for(text: str, trigger: str) -> list[str]:
    if trigger == "pull_request":
        block = text.split("  pull_request:", 1)[1].split("\n  push:", 1)[0]
    elif trigger == "push":
        block = text.split("\n  push:", 1)[1].split("\n\npermissions:", 1)[0]
    else:
        raise AssertionError(f"unsupported trigger: {trigger}")
    marker = block.index("    paths:")
    return re.findall(r'^\s+- "([^"]+)"\s*

class ProductValidationWorkflowTests(unittest.TestCase):
    def test_push_and_pull_request_path_filters_match(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        pull_request_entries = path_list_for(text, "pull_request")
        push_entries = path_list_for(text, "push")
        self.assertEqual(len(pull_request_entries), len(set(pull_request_entries)), "duplicate pull_request path filter")
        self.assertEqual(len(push_entries), len(set(push_entries)), "duplicate push path filter")
        pull_request = set(pull_request_entries)
        push = set(push_entries)
        self.assertTrue(pull_request)
        self.assertEqual(
            pull_request,
            push,
            f"push trigger missing paths: {sorted(pull_request - push)}; "
            f"push-only paths: {sorted(push - pull_request)}",
        )


if __name__ == "__main__":
    unittest.main()
, block[marker:], re.MULTILINE)


def paths_for(text: str, trigger: str) -> set[str]:
    return set(path_list_for(text, trigger))


class ProductValidationWorkflowTests(unittest.TestCase):
    def test_push_and_pull_request_path_filters_match(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        pull_request = paths_for(text, "pull_request")
        push = paths_for(text, "push")
        self.assertTrue(pull_request)
        self.assertEqual(
            pull_request,
            push,
            f"push trigger missing paths: {sorted(pull_request - push)}; "
            f"push-only paths: {sorted(push - pull_request)}",
        )


if __name__ == "__main__":
    unittest.main()
