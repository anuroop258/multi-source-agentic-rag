import pytest
from rag_app.tools import safe_calculate

def test_basic_arithmetic():
    assert safe_calculate("(1200 * 0.08) / 12") == pytest.approx(8)

def test_rejects_function_calls():
    with pytest.raises((ValueError, TypeError)):
        safe_calculate("__import__('os').system('whoami')")

def test_rejects_names():
    with pytest.raises((ValueError, TypeError)):
        safe_calculate("x + 1")
