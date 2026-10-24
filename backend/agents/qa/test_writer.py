from tools.test_generator import create_test

def test_writer(state: dict) -> dict:
    for test in state["test_plan"]["e2e_tests"]:
        create_test(test, state["workspace_dir"])
    return {}