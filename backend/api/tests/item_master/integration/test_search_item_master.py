import pytest

from api.model.item_master import ItemMaster
from api.router.item_master import router


@pytest.mark.parametrize("params,expected,status", [
    ({}, ["Alpha", "Beta", "Gamma"], 200),
    ({"search": "alpha"}, ["Alpha"], 200),
    ({"search": "CODE-A"}, ["Alpha"], 200),
    ({"search": "6907"}, ["Alpha"], 200),
    ({"search": "Ceramic"}, ["Alpha"], 200),
    ({"search": "Brand-A"}, ["Alpha"], 200),
    ({"search": "missing"}, [], 200),
    ({"limit": 1}, ["Alpha"], 200),
    ({"skip": 1, "limit": 1}, ["Beta"], 200),
    ({"skip": 3}, [], 200),
    ({"limit": 500}, ["Alpha", "Beta", "Gamma"], 200),
    ({"skip": -1}, None, 422),
    ({"limit": 0}, None, 422),
    ({"limit": 501}, None, 422),
])
def test_item_list_search_and_pagination(client, test_app, db_session, params, expected, status):
    test_app.include_router(router)
    db_session.add_all([
        ItemMaster(name="Alpha", code="CODE-A", hsn_code="6907", unit="Box", category="Ceramic", brand="Brand-A"),
        ItemMaster(name="Beta", hsn_code="1234", unit="Box"),
        ItemMaster(name="Gamma", hsn_code="1234", unit="Box"),
        ItemMaster(name="Alpha inactive", hsn_code="6907", unit="Box", is_active=False),
    ])
    db_session.commit()
    response = client.get('/item-master/', params=params)
    assert response.status_code == status, response.text
    if status == 200:
        assert [row['name'] for row in response.json()] == expected
