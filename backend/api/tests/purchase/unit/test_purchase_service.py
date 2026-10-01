"""Shared rounding contract for the four whole-rupee transaction services."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from api.services.purchase import _calculate_purchase_totals
from api.services.purchase_return import _calculate_totals
from api.services.sales_return import _calculate_sales_return_totals
from api.services.quotation import _calculate_quotation_totals


CASES = json.loads((Path(__file__).resolve().parents[2] / 'fixtures' / 'financial_rounding.json').read_text())


@pytest.mark.parametrize('calculate', [
    _calculate_purchase_totals, _calculate_totals,
    _calculate_sales_return_totals, _calculate_quotation_totals,
], ids=['purchase', 'purchase_return', 'sales_return', 'quotation'])
@pytest.mark.parametrize('case', CASES, ids=lambda case: case['name'])
def test_financial_rounding_matches_preview(calculate, case):
    items = [SimpleNamespace(**(dict(quantity=1, disc_percent=0, sgst=0, cgst=0, igst=0) | row))
             for row in case['items']]
    result = calculate(items, case.get('is_gst', True))
    assert list(result[:6]) == case['totals']
    assert [line['amount'] for line in result[6]] == case['amounts']
