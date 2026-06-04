"""
Tests for Company Context — region-aware prompts.

Verifies:
- default settings load
- region-specific regulations / channels / currency
- region change → updated regulations
- render_company_block contains region + regulations
"""

from __future__ import annotations

import pytest

from core import company_context as cc


def test_default_settings_have_required_fields():
    s = cc.DEFAULT_SETTINGS
    for field in ["company_id", "region", "country", "industry",
                  "currency", "primary_language", "primary_channels"]:
        assert field in s, f"DEFAULT_SETTINGS missing {field}"


def test_regional_regulations_coverage():
    """Every region in REGIONAL_MARKET_CONTEXT must also have regulations."""
    for region in cc.REGIONAL_MARKET_CONTEXT:
        assert region in cc.REGIONAL_REGULATIONS, \
            f"region {region} has market context but no regulations"


@pytest.mark.parametrize("region,must_contain", [
    ("RU",  "152-ФЗ"),
    ("EU",  "GDPR"),
    ("US",  "CCPA"),
    ("CN",  "PIPL"),
    ("BR",  "LGPD"),
    ("IN",  "DPDP"),
])
def test_region_specific_regulations(region, must_contain):
    regs = cc.REGIONAL_REGULATIONS[region]
    assert any(must_contain in r for r in regs), \
        f"{region} regulations missing {must_contain}: {regs}"


@pytest.mark.parametrize("region,currency", [
    ("RU", "RUB"), ("EU", "EUR"), ("US", "USD"), ("CN", "CNY"),
    ("BR", "BRL"), ("IN", "INR"), ("UK", "GBP"),
])
def test_region_currency(region, currency):
    assert cc.REGIONAL_MARKET_CONTEXT[region]["currency"] == currency


def test_render_company_block_includes_region_and_regulations():
    settings = {**cc.DEFAULT_SETTINGS, "region": "EU", "company_name": "Acme EU"}
    block = cc.render_company_block(settings)
    assert "Acme EU" in block
    assert "EU" in block
    assert "GDPR" in block, "EU company must see GDPR in its block"
    assert "152-ФЗ" not in block, "EU company should NOT see RU laws"


def test_render_company_block_ru_company_sees_russian_laws():
    settings = {**cc.DEFAULT_SETTINGS, "region": "RU", "company_name": "Рога и Копыта"}
    block = cc.render_company_block(settings)
    assert "152-ФЗ" in block
    assert "ТК РФ" in block
    assert "GDPR" not in block, "RU-only company should not see GDPR"


def test_render_company_block_us_company():
    settings = {**cc.DEFAULT_SETTINGS, "region": "US", "country": "USA"}
    block = cc.render_company_block(settings)
    assert "CCPA" in block
    assert "USD" in block or "$" in block or "USA" in block
