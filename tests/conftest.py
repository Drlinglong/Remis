import pytest

from scripts.shared import task_state


@pytest.fixture(autouse=True)
def disable_product_task_ledger_during_tests():
    """Prevent task-oriented tests from writing into the developer AppData database."""
    previous_repository = task_state.get_repository()
    task_state.configure_repository(None)
    yield
    task_state.configure_repository(previous_repository)
