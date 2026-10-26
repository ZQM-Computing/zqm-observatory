from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "product-validation.yml"


def paths_for(text: str, trigger: str) -> set[str]:
    start = text.index(f"  {trigger}:")
    following = re.search(r"^  [a-zA-Z_]+:", text[start + len(trigger) + 3 :], re.MULTILINE)
    end = start + len(trigger) + 3 + following.start() if following else len(text)
    block = text[start:end]
    marker = block.index("    paths:")
    return set(re.findall(r'^\s+- "([^"]+)"\s*$', block[marker:], re.MULTILINE))


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
