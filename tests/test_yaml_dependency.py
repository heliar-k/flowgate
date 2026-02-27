import importlib

import pytest


@pytest.mark.unit
def test_pyyaml_is_installed():
    assert importlib.util.find_spec("yaml") is not None

