import pytest

if __name__ == "__main__":
    pytest.main([
        "tests/test_intake_agent.py",
        "tests/test_budget_agent.py",
        "-v"
    ])