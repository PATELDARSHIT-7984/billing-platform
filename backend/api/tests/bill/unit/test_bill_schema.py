import pytest
from pydantic import ValidationError

from api.schema.bill import BillCreate, BillUpdate


@pytest.mark.parametrize("schema", [BillCreate, BillUpdate])
@pytest.mark.parametrize("changes", [
    {'rate': -1}, {'rate': float('inf')}, {'rate': float('nan')},
    {'disc_percent': -1}, {'disc_percent': 101}, {'disc_percent': float('nan')},
    {'cgst': -1, 'sgst': 0, 'igst': 0}, {'cgst': 101, 'sgst': 0, 'igst': 0},
    {'cgst': 0, 'sgst': 101, 'igst': 0}, {'cgst': 0, 'sgst': 0, 'igst': 101},
    {'cgst': 9, 'sgst': 9, 'igst': 18}, {'cgst': 9},
    {'cgst': float('inf'), 'sgst': 0, 'igst': 0}, {'quantity': 1.5},
])
def test_invalid_financial_inputs(schema, changes):
    with pytest.raises(ValidationError):
        schema(customer_id=1, bill_date='2026-09-15',
               items=[dict(item_id=1, quantity=1) | changes])
