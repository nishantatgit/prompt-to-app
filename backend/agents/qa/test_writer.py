from tools.test_generator import create_test

def test_writer(state: dict):
    ui_elements = state["architecture"]["ui_elements"]
    kinds = {e["label"]: e["kind"] for e in ui_elements}

    for test in state["test_plan"]["e2e_tests"]:
        create_test(test, kinds, state["workspace_dir"])