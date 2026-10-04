"""Catalog extension keeps every prior definition and readonly behavior."""
import pytest
from ark_sim.rules import DEFAULT_CATALOG
from tools.chapter08_joint_v2.catalog_v1 import assert_catalog_extension


def test_catalog_is_exact_previous98_plus_dynamic_lifetime_and_readonly():
    assert_catalog_extension(DEFAULT_CATALOG)
    with pytest.raises(TypeError):
        DEFAULT_CATALOG['types']['number'] = {}
    with pytest.raises(TypeError):
        DEFAULT_CATALOG['contracts'][-1]['owner'] = 'source'
