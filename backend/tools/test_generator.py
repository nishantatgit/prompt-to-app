import json
from pathlib import Path

def scope(within_item: str | None) -> str:
    if not within_item:
        return "page"
    return f"page.getByRole('listitem').filter({{ hasText: {json.dumps(within_item)} }})"


def locate(label: str, kinds: dict[str, str], within_item: str | None = None) -> str:
    base = scope(within_item)
    kind = kinds.get(label)
    if kind in ("button", "link", "checkbox"):
        return f"{base}.getByRole({json.dumps(kind)}, {{ name: {json.dumps(label)}, exact: true }})"
    return f"{base}.getByLabel({json.dumps(label)}, {{ exact: true }})"


VIEWPORTS = {
    "small": (375, 667),
    "medium": (768, 1024),
    "large": (1280, 800),
    "extra_large": (1920, 1080),
}


def step_to_js(step: dict, kinds: dict[str, str]) -> str:
    action = step["action"]
    q = json.dumps
    within = step.get("within_item")

    def target() -> str:
        return locate(step["label"], kinds, within)

    if action == "goto":
        return f"await page.goto({q(step['path'])});"
    if action == "reload":
        return "await page.reload();"
    if action == "set_viewport":
        width, height = VIEWPORTS[step["size"]]
        return f"await page.setViewportSize({{ width: {width}, height: {height} }});"
    if action == "click":
        return f"await {target()}.click();"
    if action == "fill":
        return f"await {target()}.fill({q(step['value'])});"
    if action == "select":
        return f"await {target()}.selectOption({q(step['option'])});"
    if action == "check":
        return f"await {target()}.check();"
    if action == "press":
        if not step.get("label"):
            return f"await page.keyboard.press({q(step['key'])});"
        return f"await {target()}.press({q(step['key'])});"
    if action == "expect_visible":
        return f"await expect({target()}).toBeVisible();"
    if action == "expect_disabled":
        return f"await expect({target()}).toBeDisabled();"
    if action == "expect_value":
        return f"await expect({target()}).toHaveValue({q(step['value'])});"
    if action == "expect_count":
        return f"await expect({target()}.getByRole('listitem')).toHaveCount({step['count']});"
    if action == "expect_text":
        return f"await expect({scope(within)}.getByText({q(step['text'])}).first()).toBeVisible();"
    if action == "expect_no_text":
        return f"await expect({scope(within)}.getByText({q(step['text'])})).toHaveCount(0);"

    raise ValueError(f"step action '{action}' is not supported yet")import json


def scope(within_item: str | None) -> str:
    if not within_item:
        return "page"
    return f"page.getByRole('listitem').filter({{ hasText: {json.dumps(within_item)} }})"


def locate(label: str, kinds: dict[str, str], within_item: str | None = None) -> str:
    base = scope(within_item)
    kind = kinds.get(label)
    if kind in ("button", "link", "checkbox"):
        return f"{base}.getByRole({json.dumps(kind)}, {{ name: {json.dumps(label)}, exact: true }})"
    return f"{base}.getByLabel({json.dumps(label)}, {{ exact: true }})"


VIEWPORTS = {
    "small": (375, 667),
    "medium": (768, 1024),
    "large": (1280, 800),
    "extra_large": (1920, 1080),
}


def step_to_js(step: dict, kinds: dict[str, str]) -> str:
    action = step["action"]
    q = json.dumps
    within = step.get("within_item")

    def target() -> str:
        return locate(step["label"], kinds, within)

    if action == "goto":
        return f"await page.goto({q(step['path'])});"
    if action == "reload":
        return "await page.reload();"
    if action == "set_viewport":
        width, height = VIEWPORTS[step["size"]]
        return f"await page.setViewportSize({{ width: {width}, height: {height} }});"
    if action == "click":
        return f"await {target()}.click();"
    if action == "fill":
        return f"await {target()}.fill({q(step['value'])});"
    if action == "select":
        return f"await {target()}.selectOption({q(step['option'])});"
    if action == "check":
        return f"await {target()}.check();"
    if action == "press":
        if not step.get("label"):
            return f"await page.keyboard.press({q(step['key'])});"
        return f"await {target()}.press({q(step['key'])});"
    if action == "expect_visible":
        return f"await expect({target()}).toBeVisible();"
    if action == "expect_disabled":
        return f"await expect({target()}).toBeDisabled();"
    if action == "expect_value":
        return f"await expect({target()}).toHaveValue({q(step['value'])});"
    if action == "expect_count":
        return f"await expect({target()}.getByRole('listitem')).toHaveCount({step['count']});"
    if action == "expect_text":
        return f"await expect({scope(within)}.getByText({q(step['text'])}).first()).toBeVisible();"
    if action == "expect_no_text":
        return f"await expect({scope(within)}.getByText({q(step['text'])})).toHaveCount(0);"

    raise ValueError(f"step action '{action}' is not supported yet")import json


def scope(within_item: str | None) -> str:
    if not within_item:
        return "page"
    return f"page.getByRole('listitem').filter({{ hasText: {json.dumps(within_item)} }})"


def locate(label: str, kinds: dict[str, str], within_item: str | None = None) -> str:
    base = scope(within_item)
    kind = kinds.get(label)
    if kind in ("button", "link", "checkbox"):
        return f"{base}.getByRole({json.dumps(kind)}, {{ name: {json.dumps(label)}, exact: true }})"
    return f"{base}.getByLabel({json.dumps(label)}, {{ exact: true }})"


VIEWPORTS = {
    "small": (375, 667),
    "medium": (768, 1024),
    "large": (1280, 800),
    "extra_large": (1920, 1080),
}


def step_to_js(step: dict, kinds: dict[str, str]) -> str:
    action = step["action"]
    q = json.dumps
    within = step.get("within_item")

    def target() -> str:
        return locate(step["label"], kinds, within)

    if action == "goto":
        return f"await page.goto({q(step['path'])});"
    if action == "reload":
        return "await page.reload();"
    if action == "set_viewport":
        width, height = VIEWPORTS[step["size"]]
        return f"await page.setViewportSize({{ width: {width}, height: {height} }});"
    if action == "click":
        return f"await {target()}.click();"
    if action == "fill":
        return f"await {target()}.fill({q(step['value'])});"
    if action == "select":
        return f"await {target()}.selectOption({q(step['option'])});"
    if action == "check":
        return f"await {target()}.check();"
    if action == "press":
        if not step.get("label"):
            return f"await page.keyboard.press({q(step['key'])});"
        return f"await {target()}.press({q(step['key'])});"
    if action == "expect_visible":
        return f"await expect({target()}).toBeVisible();"
    if action == "expect_disabled":
        return f"await expect({target()}).toBeDisabled();"
    if action == "expect_value":
        return f"await expect({target()}).toHaveValue({q(step['value'])});"
    if action == "expect_count":
        return f"await expect({target()}.getByRole('listitem')).toHaveCount({step['count']});"
    if action == "expect_text":
        return f"await expect({scope(within)}.getByText({q(step['text'])}).first()).toBeVisible();"
    if action == "expect_no_text":
        return f"await expect({scope(within)}.getByText({q(step['text'])})).toHaveCount(0);"

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