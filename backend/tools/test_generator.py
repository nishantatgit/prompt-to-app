import json
from pathlib import Path


def locate(label: str, kinds: dict[str, str]) -> str:
    kind = kinds.get(label)
    if kind in ("button", "link"):
        return f"page.getByRole({json.dumps(kind)}, {{ name: {json.dumps(label)}, exact: true }})"
    return f"page.getByLabel({json.dumps(label)}, {{ exact: true }})"


def step_to_js(step: dict, kinds: dict[str, str]) -> str:
    action = step["action"]
    q = json.dumps

    if action == "goto":
        return f"await page.goto({q(step['path'])});"
    if action == "reload":
        return "await page.reload();"
    if action == "set_viewport":
        return f"await page.setViewportSize({{ width: {step['width']}, height: {step['height']} }});"
    if action == "click":
        return f"await {locate(step['label'], kinds)}.click();"
    if action == "fill":
        return f"await {locate(step['label'], kinds)}.fill({q(step['value'])});"
    if action == "select":
        return f"await {locate(step['label'], kinds)}.selectOption({q(step['option'])});"
    if action == "check":
        return f"await {locate(step['label'], kinds)}.check();"
    if action == "press":
        return f"await {locate(step['label'], kinds)}.press({q(step['key'])});"
    if action == "expect_visible":
        return f"await expect({locate(step['label'], kinds)}).toBeVisible();"
    if action == "expect_disabled":
        return f"await expect({locate(step['label'], kinds)}).toBeDisabled();"
    if action == "expect_value":
        return f"await expect({locate(step['label'], kinds)}).toHaveValue({q(step['value'])});"
    if action == "expect_count":
        return f"await expect({locate(step['label'], kinds)}.getByRole('listitem')).toHaveCount({step['count']});"
    if action == "expect_text":
        return f"await expect(page.getByText({q(step['text'])}).first()).toBeVisible();"
    if action == "expect_no_text":
        return f"await expect(page.getByText({q(step['text'])})).toHaveCount(0);"

    raise ValueError(f"step action '{action}' is not supported yet")

def create_test(test: dict, kinds: dict[str, str], workspace_dir: str) -> Path:
    path = Path(workspace_dir) / "tests" / f"{test['criterion_id']}-{test['id']}.spec.js"
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test({json.dumps(test['criterion_id'] + ': ' + test['description'])}, async ({{ page }}) => {{",
    ]
    for step in test["steps"]:
        lines.append("  " + step_to_js(step, kinds))
    lines.append("});")

    path.write_text("\n".join(lines) + "\n")
    return path