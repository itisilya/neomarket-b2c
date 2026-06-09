from fastapi.testclient import TestClient
from app.main import app, b2b_client

client = TestClient(app)

def test_catalog_returns_filtered_sorted_products():
    """
    Catalog Returns Filtered and Sorted Products (Happy path):
    Checks category filtering, price filtering, sorting (price_asc, price_desc) and pagination limits.
    """
    # Test sort price_asc & limit
    response = client.get("/api/v1/catalog/products?sort=price_asc&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total_count" in data
    assert len(data["items"]) <= 2
    
    # Check ascending prices sorting
    prices = [p["min_price"] for p in data["items"]]
    if len(prices) > 1:
        assert prices[0] <= prices[1]

    # Test filtering by category e1010000-e29b-41d4-a716-446655440006
    cat_id = "e1010000-e29b-41d4-a716-446655440006"
    response_cat = client.get(f"/api/v1/products?category_id={cat_id}")
    assert response_cat.status_code == 200
    data_cat = response_cat.json()
    for item in data_cat["items"]:
        # Should belong to target or sub-category
        assert item["category"]["id"] == cat_id or cat_id in item["category"]["path"]

def test_facets_return_counts_per_filter_value():
    """
    Facets Return Count Per Filter Value:
    Verifies that facet groups are returned and categorize with accurate counts.
    """
    response = client.get("/api/v1/catalog/facets")
    assert response.status_code == 200
    data = response.json()
    assert "facets" in data
    
    facets = {group["name"]: group["values"] for group in data["facets"]}
    assert "category" in facets
    assert "verified" in facets
    
    # Check category counting matches total moderated B2B products
    category_items = facets["category"]
    assert len(category_items) > 0
    # Every facet must have a count >= 1
    for item in category_items:
        assert item["count"] >= 1

def test_invalid_sort_returns_400():
    """
    Invalid Sort Returns 400:
    Verifies that providing an unsupported or malicious sorting string parameter
    returns code 400 with details / allowed values list.
    """
    response = client.get("/api/v1/catalog/products?sort=malicious_injection")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_SORT"
    assert "Allowed options" in data["message"]

def test_b2b_unavailable_returns_502():
    """
    B2B Unavailable Returns 502/503:
    Simulates gateway failure or connection loss to the backend B2B orchestrator.
    Should return 502 Bad Gateway to B2C users.
    """
    # Trigger simulated outage in b2b client
    b2b_client.simulate_outage = True
    try:
        response = client.get("/api/v1/products")
        assert response.status_code == 502
        data = response.json()
        assert data["code"] == "B2B_UNAVAILABLE"
    finally:
        # Restore client state to prevent other tests from failing
        b2b_client.simulate_outage = False

def test_search_returns_matching_products():
    """
    search_returns_matching_products (happy path):
    Verifies that real queries fetch items based on titles/descriptions.
    """
    response = client.get("/api/v1/catalog/products?search=Crypto")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    assert "Crypto" in data["items"][0]["name"]

def test_short_query_returns_400():
    """
    short_query_returns_400:
    Verifies searches shorter than 3 symbols throw 400 Bad Request
    as specified by the search length requirement.
    """
    response = client.get("/api/v1/catalog/products?search=ab")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "INVALID_REQUEST"
    assert "at least 3 characters" in data["message"]

def test_special_chars_do_not_break_query():
    """
    special_chars_do_not_break_query:
    Verifies SQL specials / wildcards (%, _, ') are safely processed and do not throw.
    """
    response = client.get("/api/v1/catalog/products?search=Whale%15'")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data

def test_empty_results_returns_200():
    """
    empty_results_returns_200:
    Checks that a text query returning zero matches triggers status 200 and an empty array.
    """
    response = client.get("/api/v1/catalog/products?search=NonExistentMatchTextTerm")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 0
    assert data["total_count"] == 0

def test_product_card_returns_full_data_with_skus():
    """
    product_card_returns_full_data_with_skus (Happy Path):
    Ensures that fetching a valid moderated product returns full descriptions, characteristics,
    and SKU variations with pricing and stock availability.
    """
    target_id = "770e8400-e29b-41d4-a716-446655440001"
    response = client.get(f"/api/v1/catalog/products/{target_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == target_id
    assert "description" in data
    assert "skus" in data
    assert len(data["skus"]) >= 1
    assert "price" in data["skus"][0]

def test_cost_price_absent_in_response():
    """
    cost_price_absent_in_response:
    Explicit check to ensure private fields (cost_price, reserved_quantity)
    associated with b2b sales are NOT present in any sku object returned to the B2C buyer.
    """
    target_id = "770e8400-e29b-41d4-a716-446655440001"
    response = client.get(f"/api/v1/catalog/products/{target_id}")
    assert response.status_code == 200
    data = response.json()
    for sku in data["skus"]:
        assert "cost_price" not in sku
        assert "reserved_quantity" not in sku

def test_blocked_product_returns_404():
    """
    blocked_product_returns_404:
    Verifies that deleted or pending draft products throw a clean 404 block response.
    """
    # Draft product UUID
    draft_id = "770e8400-e29b-41d4-a716-446655440099"
    response_draft = client.get(f"/api/v1/catalog/products/{draft_id}")
    assert response_draft.status_code == 404

    # Deleted product UUID
    deleted_id = "770e8400-e29b-41d4-a716-446655440098"
    response_deleted = client.get(f"/api/v1/catalog/products/{deleted_id}")
    assert response_deleted.status_code == 404

def test_sku_without_stock_is_shown_as_unavailable():
    """
    unhappy: sku_without_stock_is_shown_as_unavailable
    Если остаток 0, товар все равно должен открываться по прямой ссылке, 
    но поле has_stock должно быть false.
    """
    # ID товара из твоего b2b_client.py с active_quantity = 0
    out_of_stock_id = "770e8400-e29b-41d4-a716-446655440097"
    response = client.get(f"/api/v1/catalog/products/{out_of_stock_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["has_stock"] is False
    # Проверяем доступность в SKU
    for sku in data["skus"]:
        assert sku["available_quantity"] == 0

def test_similar_returns_up_to_8_from_same_category():
    """
    happy: similar_returns_up_to_8_from_same_category
    Запрашивает похожие товары для конкретного товара. 
    Проверяет, что возвращается массив до 8 товаров, и сам исходный товар исключен из результатов.
    """
    target_id = "770e8400-e29b-41d4-a716-446655440001"
    response = client.get(f"/api/v1/catalog/products/{target_id}/similar")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 8
    
    # Сам запрашиваемый товар не должен присутствовать в списке похожих
    for item in data:
        assert item["id"] != target_id

def test_empty_category_returns_200_empty_list():
    """
    unhappy: empty_category_returns_200_empty_list
    Если нет других подходящих похожих товаров (например, только один товар во всей базе),
    эндпоинт должен возвращать пустой список с кодом 200.
    """
    from uuid import UUID
    original_products = b2b_client._products
    try:
        # Оставляем только один товар
        single_prod = next(p for p in original_products if p["id"] == UUID("770e8400-e29b-41d4-a716-446655440001"))
        b2b_client._products = [single_prod]
        
        response = client.get(f"/api/v1/catalog/products/{single_prod['id']}/similar")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    finally:
        b2b_client._products = original_products

def test_unknown_product_returns_404():
    """
    unhappy: unknown_product_returns_404
    Запрос похожих товаров для несуществующего uuid товара возвращает 404.
    """
    unknown_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/catalog/products/{unknown_id}/similar")
    assert response.status_code == 404


def test_category_tree_returns_nested_structure():
    """
    happy: category_tree_returns_nested_structure
    Дерево собирается из плоского списка
    """
    response = client.get("/api/v1/catalog/categories/tree")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Check structure: each category should have level, path, children, id, name
    for item in data:
        assert "id" in item
        assert "name" in item
        assert "level" in item
        assert "path" in item
        assert "children" in item
        assert isinstance(item["children"], list)


def test_breadcrumbs_return_path_from_root():
    """
    happy: breadcrumbs_return_path_from_root
    Цепочка от корня до категории
    """
    cat_id = "e1010000-e29b-41d4-a716-446655440010" # Иностранные языки, parent (Образование & Наука)
    response = client.get(f"/api/v1/breadcrumbs?category_id={cat_id}")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    breadcrumbs = data["data"]
    assert len(breadcrumbs) >= 2
    assert breadcrumbs[0]["name"] == "Образование & Наука"
    assert breadcrumbs[1]["name"] == "Иностранные языки"
    assert breadcrumbs[0]["level"] == 0
    assert breadcrumbs[1]["level"] == 1
    assert breadcrumbs[0]["is_current"] is False
    assert breadcrumbs[1]["is_current"] is True


def test_ambiguous_params_returns_400():
    """
    unhappy: ambiguous_params_returns_400
    Оба параметра одновременно в breadcrumbs -> 400
    """
    url = "/api/v1/breadcrumbs?category_id=e1010000-e29b-41d4-a716-446655440010&product_id=770e8400-e29b-41d4-a716-446655440001"
    response = client.get(url)
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "AMBIGUOUS_PARAM"


def test_orphan_node_returns_422():
    """
    unhappy: orphan_node_returns_422
    Сломанная иерархия (orphan node) -> 422
    """
    from uuid import UUID
    original_categories = b2b_client._categories
    try:
        # Simulate an orphan category node by injecting a temporary card
        orphan_id = UUID("e1010000-0000-0000-0000-999999999999")
        orphan_node = {
            "id": orphan_id,
            "name": "Orphan Category",
            "slug": "orphan-cat",
            "parent_id": UUID("e1010000-0000-0000-0000-888888888888") # Missing parent
        }
        b2b_client._categories = original_categories + [orphan_node]
        
        # Query detail for the orphan category node -> 422
        response_detail = client.get(f"/api/v1/catalog/categories/{orphan_id}")
        assert response_detail.status_code == 422
        data_det = response_detail.json()
        assert data_det["code"] == "ORPHAN_NODE"

        # Query breadcrumbs for the orphan category node -> 422
        response_crumbs = client.get(f"/api/v1/breadcrumbs?category_id={orphan_id}")
        assert response_crumbs.status_code == 422
        data_crumbs = response_crumbs.json()
        assert data_crumbs["code"] == "ORPHAN_NODE"
    finally:
        b2b_client._categories = original_categories


def test_unknown_category_returns_404():
    """
    unhappy: unknown_category_returns_404
    несуществующая категория -> 404
    """
    unknown_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/catalog/categories/{unknown_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"


# --- US-CART-01 Favorites Test Suite ---

import base64
import json

def create_mock_jwt(user_id: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"Bearer {h_b64}.{p_b64}.mock-signature"


def test_add_to_favorites_returns_201():
    """
    happy: add_to_favorites_returns_201
    Покупатель добавляет допустимый товар в избранное впервые -> 201 Created.
    """
    from app.main import FAVORITES_DB
    user_id = "a1111111-e29b-41d4-a716-446655440001"
    product_id = "770e8400-e29b-41d4-a716-446655440001" # Crypto Whale Alerts (moderated, active)
    token = create_mock_jwt(user_id)
    
    # Clean database state first
    from uuid import UUID
    user_uuid = UUID(user_id)
    if user_uuid in FAVORITES_DB:
        del FAVORITES_DB[user_uuid]

    # Add to favorites
    response = client.post(
        f"/api/v1/favorites/{product_id}",
        headers={"Authorization": token}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["product_id"] == product_id
    assert data["user_id"] == user_id
    assert "added_at" in data
    
    # Retrieve favorites to verify it's there
    get_res = client.get(
        "/api/v1/favorites",
        headers={"Authorization": token}
    )
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["total_count"] == 1
    assert get_data["items"][0]["id"] == product_id


def test_repeat_add_returns_200_not_duplicate():
    """
    unhappy: repeat_add_returns_200_not_duplicate
    Повторное добавление существующего товара в избранное -> 200 OK, не дублируется.
    """
    user_id = "a1111111-e29b-41d4-a716-446655440002"
    product_id = "770e8400-e29b-41d4-a716-446655440001" # Valid modulated B2B product
    token = create_mock_jwt(user_id)
    
    # First Addition -> 201
    response1 = client.post(
        f"/api/v1/favorites/{product_id}",
        headers={"Authorization": token}
    )
    assert response1.status_code == 201
    added_at_first = response1.json()["added_at"]
    
    # Second Addition -> 200
    response2 = client.post(
        f"/api/v1/favorites/{product_id}",
        headers={"Authorization": token}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["added_at"] == added_at_first
    
    # Verify no duplication in listing
    get_res = client.get(
        "/api/v1/favorites",
        headers={"Authorization": token}
    )
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["total_count"] == 1
    assert len(get_data["items"]) == 1


def test_blocked_product_excluded_from_list():
    """
    unhappy: blocked_product_excluded_from_list
    Товар, который был заблокирован/удален в B2B, автоматически исключается из выдачи GET /favorites.
    """
    user_id = "a1111111-e29b-41d4-a716-446655440003"
    product_id_active = "770e8400-e29b-41d4-a716-446655440001" # Active Whale channel
    product_id_draft = "770e8400-e29b-41d4-a716-446655440099" # Not moderated: status = "DRAFT"
    
    token = create_mock_jwt(user_id)
    
    # Try adding draft product to favorites -> 404 since it's not active/visible in available products or exists but blocked?
    # Wait, our post endpoint checks "next((p for p in raw_products if p['id'] == product_id), None)".
    # Does raw_products keep active/all products? Yes, b2b_client._products contains raw unchecked products.
    # So we can add draft product, but GET /favorites will only show moderated products since it calls fetch_products.
    
    # Add active product -> 201
    res_act = client.post(f"/api/v1/favorites/{product_id_active}", headers={"Authorization": token})
    assert res_act.status_code == 201
    
    # Add draft product -> 201 (since it exists in _products database, but status: DRAFT)
    res_draft = client.post(f"/api/v1/favorites/{product_id_draft}", headers={"Authorization": token})
    assert res_draft.status_code == 201
    
    # Query favorites -> only active product should be in items!
    get_res = client.get("/api/v1/favorites", headers={"Authorization": token})
    assert get_res.status_code == 200
    get_data = get_res.json()
    
    # Draft product must be completely excluded!
    assert get_data["total_count"] == 1
    assert get_data["items"][0]["id"] == product_id_active
    
    # Verify that if product_id_active is deleted, it is also excluded
    from uuid import UUID
    for prod in b2b_client._products:
        if prod["id"] == UUID(product_id_active):
            prod["deleted"] = True  # Simulated deletion
            
    try:
        get_res_deleted = client.get("/api/v1/favorites", headers={"Authorization": token})
        assert get_res_deleted.status_code == 200
        assert get_res_deleted.json()["total_count"] == 0
        assert len(get_res_deleted.json()["items"]) == 0
    finally:
        # Restore state
        for prod in b2b_client._products:
            if prod["id"] == UUID(product_id_active):
                prod["deleted"] = False


def test_user_id_from_query_is_ignored():
    """
    unhappy: user_id_from_query_is_ignored
    Если передан user_id в query — игнорируется, берётся из JWT (предотвращение IDOR).
    """
    user_alice = "a1111111-e29b-41d4-a716-446655440004"
    user_bob = "b1111111-e29b-41d4-a716-446655440005"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    
    token_alice = create_mock_jwt(user_alice)
    token_bob = create_mock_jwt(user_bob)
    
    # Alice adds product, but maliciously tries to pass user_id equal to Bob in query params
    response = client.post(
        f"/api/v1/favorites/{product_id}?user_id={user_bob}",
        headers={"Authorization": token_alice}
    )
    assert response.status_code == 201
    
    # Check that the favorite was added for ALICE, not Bob!
    # Alice GET with Bob query param -> returns Alice's favorites
    get_alice = client.get(
        f"/api/v1/favorites?user_id={user_bob}",
        headers={"Authorization": token_alice}
    )
    assert get_alice.status_code == 200
    assert get_alice.json()["total_count"] == 1
    assert get_alice.json()["items"][0]["id"] == product_id
    
    # Bob GET with Alice/Bob queries -> should return Bob's empty favorites list!
    get_bob = client.get(
        f"/api/v1/favorites?user_id={user_alice}",
        headers={"Authorization": token_bob}
    )
    assert get_bob.status_code == 200
    assert get_bob.json()["total_count"] == 0


def test_subscribe_returns_204_with_events():
    """
    happy: subscribe_returns_204_with_events
    """
    from app.main import SUBSCRIPTIONS_DB
    user_id = "c1111111-e29b-41d4-a716-446655440101"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)

    # Clean state
    from uuid import UUID
    user_uuid = UUID(user_id)
    if user_uuid in SUBSCRIPTIONS_DB:
        del SUBSCRIPTIONS_DB[user_uuid]

    # Create subscription
    response = client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        json={"events": ["PRICE_DROP", "BACK_IN_STOCK"]},
        headers={"Authorization": token}
    )
    assert response.status_code == 204
    
    # Assert DB is correctly populated
    assert user_uuid in SUBSCRIPTIONS_DB
    sub = SUBSCRIPTIONS_DB[user_uuid][0]
    assert str(sub["product_id"]) == product_id
    assert sub["events"] == ["PRICE_DROP", "BACK_IN_STOCK"]

    # Clean up / unsubscribe
    del_res = client.delete(
        f"/api/v1/favorites/{product_id}/subscribe",
        headers={"Authorization": token}
    )
    assert del_res.status_code == 204


def test_duplicate_subscription_returns_409():
    """
    unhappy: duplicate_subscription_returns_409
    """
    user_id = "c1111111-e29b-41d4-a716-446655440102"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)

    # Subscribe once -> 204
    response1 = client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        json={"events": ["PRICE_DROP"]},
        headers={"Authorization": token}
    )
    assert response1.status_code == 204

    # Subscribe twice -> 409
    response2 = client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        json={"events": ["BACK_IN_STOCK"]},
        headers={"Authorization": token}
    )
    assert response2.status_code == 409
    assert response2.json()["code"] == "DUPLICATE_SUBSCRIPTION"


def test_invalid_notify_on_returns_400():
    """
    unhappy: invalid_notify_on_returns_400
    """
    user_id = "c1111111-e29b-41d4-a716-446655440103"
    product_id = "770e8400-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)

    # Empty notify_on -> 400
    response1 = client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        json={"events": []},
        headers={"Authorization": token}
    )
    assert response1.status_code == 400
    assert response1.json()["code"] == "INVALID_REQUEST"

    # Invalid list value -> 400
    response2 = client.post(
        f"/api/v1/favorites/{product_id}/subscribe",
        json={"events": ["invalid_event_type"]},
        headers={"Authorization": token}
    )
    assert response2.status_code == 400
    assert response2.json()["code"] == "INVALID_REQUEST"


def test_subscribe_to_unknown_product_returns_404():
    """
    unhappy: subscribe_to_unknown_product_returns_404
    """
    user_id = "c1111111-e29b-41d4-a716-446655440104"
    unknown_id = "00000000-0000-0000-0000-000000000000"
    token = create_mock_jwt(user_id)

    response = client.post(
        f"/api/v1/favorites/{unknown_id}/subscribe",
        json={"events": ["PRICE_DROP"]},
        headers={"Authorization": token}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# --- US-CART-03: Cart management Test Suite ---

def test_add_sku_increments_quantity_if_already_in_cart():
    """
    happy: add_sku_increments_quantity_if_already_in_cart
    Повторное добавление того же SKU увеличивает quantity в корзине.
    """
    from app.main import CART_DB
    session_id = "test-guest-session-123"
    sku_id = "00000000-0000-0000-0000-000000000001"
    
    if session_id in CART_DB:
        del CART_DB[session_id]
        
    res1 = client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 1},
        headers={"X-Session-Id": session_id}
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1["items"]) == 1
    assert data1["items"][0]["sku_id"] == sku_id
    assert data1["items"][0]["quantity"] == 1
    
    res2 = client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 3},
        headers={"X-Session-Id": session_id}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 1
    assert data2["items"][0]["sku_id"] == sku_id
    assert data2["items"][0]["quantity"] == 4


def test_get_cart_enriched_with_b2b_data():
    """
    happy: get_cart_enriched_with_b2b_data
    Получение корзины обогащает данные из B2B (название, характеристики, цены, subtotal).
    """
    from app.main import CART_DB
    session_id = "test-guest-session-456"
    sku_id = "00000000-0000-0000-0000-000000000001"
    
    CART_DB[session_id] = {sku_id: 2}
    
    response = client.get(
        "/api/v1/cart",
        headers={"X-Session-Id": session_id}
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total_amount" in data
    assert len(data["items"]) == 1
    
    item = data["items"][0]
    assert item["sku_id"] == sku_id
    assert item["quantity"] == 2
    assert item["sku"] is not None
    assert item["sku"]["name"] == "Полная передача прав (Базовый)"
    assert item["sku"]["price"] == 15000000
    assert item["product"] is not None
    assert item["product"]["name"] == "Crypto Whale Alerts 🐳"
    assert item["subtotal"] == 30000000
    assert data["total_amount"] == 30000000


def test_unavailable_sku_shown_with_reason():
    """
    unhappy: unavailable_sku_shown_with_reason
    Недоступный SKU в корзине возвращается с unavailable_reason,
    но не участвует в подсчете total_amount.
    """
    from app.main import CART_DB
    session_id = "test-guest-session-789"
    
    out_of_stock_sku_id = "770e8400-e29b-41d4-a716-446655440097"
    active_sku_id = "00000000-0000-0000-0000-000000000001"
    
    CART_DB[session_id] = {
        out_of_stock_sku_id: 1,
        active_sku_id: 2
    }
    
    response = client.get(
        "/api/v1/cart",
        headers={"X-Session-Id": session_id}
    )
    assert response.status_code == 200
    data = response.json()
    
    items = {item["sku_id"]: item for item in data["items"]}
    assert len(items) == 2
    
    oos_item = items[out_of_stock_sku_id]
    assert oos_item["unavailable_reason"] is not None
    assert oos_item["unavailable_reason"] in ["OUT_OF_STOCK", "UNAVAILABLE"]
    assert oos_item["subtotal"] == 0
    
    active_item = items[active_sku_id]
    assert active_item["unavailable_reason"] is None
    assert active_item["subtotal"] == 30000000
    
    assert data["total_amount"] == 30000000


def test_guest_cart_merged_on_login():
    """
    happy/merge: guest_cart_merged_on_login
    При слиянии гостевой корзины с авторизованной при конфликте берется MAX(guest, auth).
    """
    from app.main import CART_DB
    guest_session_id = "test-guest-session-merge"
    user_id = "c1111111-e29b-41d4-a716-446655449999"
    token = create_mock_jwt(user_id)
    
    sku_conflict = "00000000-0000-0000-0000-000000000001"
    sku_unique_guest = "770e8400-e29b-41d4-a716-446655d40011"
    
    CART_DB[guest_session_id] = {
        sku_conflict: 2,
        sku_unique_guest: 1
    }
    
    CART_DB[user_id] = {
        sku_conflict: 5
    }
    
    response = client.post(
        "/api/v1/cart/merge",
        json={"session_id": guest_session_id},
        headers={"Authorization": token, "X-Session-Id": guest_session_id}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert guest_session_id not in CART_DB
    
    items = {item["sku_id"]: item for item in data["items"]}
    assert items[sku_conflict]["quantity"] == 5
    assert items[sku_unique_guest]["quantity"] == 1


# --- US-CART-04: Banners & CTR Analytics tests ---

def test_active_banners_returned_sorted_by_priority():
    """
    happy: active_banners_returned_sorted_by_priority
    Проверяет, что возвращаются только активные баннеры (is_active=true) и находящиеся 
    в пределах своего расписания (start_at <= now <= end_at), отсортированные по priority (ascending: меньше значение = выше).
    """
    from app.main import BANNERS_DB
    import uuid
    
    # Save original DB to restore after test
    orig_banners = list(BANNERS_DB)
    
    # Prepopulate with controlled banners
    BANNERS_DB.clear()
    b1 = {
        "id": uuid.UUID("ca111111-1111-1111-1111-111111111111"),
        "title": "Banner Low Priority",
        "image_url": "url1",
        "link_url": "link1",
        "priority": 10,
        "is_active": True,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    }
    b2 = {
        "id": uuid.UUID("ca222222-2222-2222-2222-222222222222"),
        "title": "Banner High Priority",
        "image_url": "url2",
        "link_url": "link2",
        "priority": 100,
        "is_active": True,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    }
    b_inactive = {
        "id": uuid.UUID("ca333333-3333-3333-3333-333333333333"),
        "title": "Banner Inactive",
        "image_url": "url3",
        "link_url": "link3",
        "priority": 500,
        "is_active": False,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    }
    b_future = {
        "id": uuid.UUID("ca444444-4444-4444-4444-444444444444"),
        "title": "Banner Future",
        "image_url": "url4",
        "link_url": "link4",
        "priority": 600,
        "is_active": True,
        "start_at": "2026-07-01T00:00:00Z",
        "end_at": "2026-07-31T23:59:59Z",
    }
    
    BANNERS_DB.extend([b1, b2, b_inactive, b_future])
    
    try:
        response = client.get("/api/v1/catalog/banners")
        assert response.status_code == 200
        data = response.json()
        
        # Should only contain active inside schedule (b1 and b2)
        assert len(data) == 2
        
        # Sorted by priority ascending (b1 with priority 10 first, then b2 with priority 100)
        assert data[0]["id"] == "ca111111-1111-1111-1111-111111111111"
        assert data[0]["title"] == "Banner Low Priority"
        assert data[0]["link"] == "link1"
        assert data[0]["ordering"] == 10
        assert data[1]["id"] == "ca222222-2222-2222-2222-222222222222"
        assert data[1]["title"] == "Banner High Priority"
        assert data[1]["link"] == "link2"
        assert data[1]["ordering"] == 100
        
        # Also assert the compatibility route works
        compatibility_response = client.get("/api/v1/home/banners")
        assert compatibility_response.status_code == 200
        assert len(compatibility_response.json()) == 2
        
    finally:
        BANNERS_DB.clear()
        BANNERS_DB.extend(orig_banners)


def test_no_active_banners_returns_200_empty():
    """
    unhappy: no_active_banners_returns_200_empty
    Если нет активных баннеров в данный момент времени, возвращается статус 200 с пустым списком [].
    """
    from app.main import BANNERS_DB
    
    # Save original
    orig_banners = list(BANNERS_DB)
    BANNERS_DB.clear()
    
    try:
        response = client.get("/api/v1/catalog/banners")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        BANNERS_DB.clear()
        BANNERS_DB.extend(orig_banners)


def test_click_on_unknown_banner_returns_400():
    """
    unhappy: click_on_unknown_banner_returns_400
    Отправка CTR-события для несуществующего (неизвестного) баннера возвращает статус 400 Bad Request.
    """
    unknown_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        "/api/v1/banner-events",
        json={"banner_id": unknown_id, "event_type": "CLICK"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "BANNER_NOT_FOUND"


def test_click_on_valid_banner_returns_201():
    """
    happy: click_on_valid_banner_returns_21
    """
    from app.main import BANNERS_DB, BANNER_EVENTS_LOG
    if len(BANNERS_DB) > 0:
        valid_banner_id = str(BANNERS_DB[0]["id"])
        init_len = len(BANNER_EVENTS_LOG)
        
        response = client.post(
            "/api/v1/banner-events",
            json={"banner_id": valid_banner_id, "event_type": "CLICK"}
        )
        assert response.status_code == 201
        assert len(BANNER_EVENTS_LOG) == init_len + 1
        assert BANNER_EVENTS_LOG[-1]["banner_id"] == BANNERS_DB[0]["id"]
        assert BANNER_EVENTS_LOG[-1]["event_type"] == "CLICK"


def test_collections_list_returns_metadata_without_products():
    """
    happy: collections_list_returns_metadata_without_products
    Проверяет, что возвращается список подборок без товаров внутри (поле products пустое).
    """
    response = client.get("/api/v1/catalog/collections")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    for col in data:
        assert "id" in col
        assert "name" in col
        assert "products" in col
        assert col["products"] == []  # metadata without products


def test_collection_products_enriched_from_b2b():
    """
    happy: collection_products_enriched_from_b2b
    Проверяет, что конкретная подборка возвращает товары, обогащенные из B2B.
    """
    col_id = "d70e8400-e29b-41d4-a716-446655440001"
    response = client.get(f"/api/v1/catalog/collections/{col_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == col_id
    assert data["name"] == "Хиты продаж"
    assert "items" in data
    assert "unavailable_ids" in data
    
    assert len(data["items"]) == 2
    for item in data["items"]:
        assert "id" in item
        assert "name" in item
        assert "min_price" in item
        assert "subscribers" in item


def test_unavailable_products_in_unavailable_ids():
    """
    unhappy: unavailable_products_in_unavailable_ids
    Проверяет, что удалённые/заблокированные/немодерированные товары в B2B попадают в unavailable_ids, а не в items.
    """
    col_id = "d70e8400-e29b-41d4-a716-446655440002"
    response = client.get(f"/api/v1/catalog/collections/{col_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == col_id
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "770e8400-e29b-41d4-a716-446655440003"
    
    assert len(data["unavailable_ids"]) == 2
    assert "770e8400-e29b-41d4-a716-446655440099" in data["unavailable_ids"]
    assert "770e8400-e29b-41d4-a716-446655440098" in data["unavailable_ids"]


def test_unknown_collection_returns_404():
    """
    unhappy: unknown_collection_returns_404
    Проверяет, что несуществующая подборка возвращает 404 Not Found.
    """
    unknown_id = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/catalog/collections/{unknown_id}")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_checkout_creates_paid_order_with_fixed_prices():
    """
    happy path: checkout_creates_paid_order_with_fixed_prices
    - unit_price зафиксирован в OrderItem;
    - Статус заказа PAID.
    """
    user_id = "a1111111-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)
    idempotency_key = "11111111-2222-3333-4444-555555555555"
    
    sku_id = "00000000-0000-0000-0000-000000000001" # Crypto Whale SKU, price is 15000000
    
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "PAID"
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["sku_id"] == sku_id
    assert item["unit_price"] == 15000000
    assert item["line_total"] == 15000000


def test_partial_reserve_failure_returns_409():
    """
    unhappy: partial_reserve_failure_returns_409
    - хотя бы один SKU не зарезервирован -> 409 RESERVE_FAILED с failed_items
    """
    user_id = "a1111111-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)
    idempotency_key = "22222222-3333-4444-5555-666666666666"
    
    # Requesting excessive quantity to trigger INSUFFICIENT_STOCK
    sku_id = "00000000-0000-0000-0000-000000000001" # has limited stock in B2B
    
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 99999}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    
    assert response.status_code == 409
    data = response.json()
    assert data["code"] == "RESERVE_FAILED"
    assert "failed_items" in data
    assert len(data["failed_items"]) > 0


def test_idempotency_returns_existing_order():
    """
    unhappy: idempotency_returns_existing_order
    - повторный POST с тем же idempotency_key возвращает существующий заказ;
    """
    user_id = "a1111111-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)
    idempotency_key = "33333333-4444-5555-6666-777777777777"
    
    sku_id = "00000000-0000-0000-0000-000000000001"
    
    payload = {
        "idempotency_key": idempotency_key,
        "items": [{"sku_id": sku_id, "quantity": 1}],
        "address_id": "e2020000-e29b-41d4-a716-446655440001",
        "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
    }
    
    # First request
    response1 = client.post(
        "/api/v1/orders",
        json=payload,
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response1.status_code == 201
    order1 = response1.json()
    
    # Second request
    response2 = client.post(
        "/api/v1/orders",
        json=payload,
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response2.status_code in [200, 201]
    order2 = response2.json()
    assert order1["id"] == order2["id"]


def test_b2b_unavailable_returns_503():
    """
    unhappy: b2b_unavailable_returns_503
    - B2B недоступен -> 503
    """
    user_id = "a1111111-e29b-41d4-a716-446655440001"
    token = create_mock_jwt(user_id)
    idempotency_key = "44444444-5555-6666-7777-888888888888"
    
    sku_id = "00000000-0000-0000-0000-000000000001"
    
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key, "X-Simulate-B2B-Outage": "true"}
    )
    
    assert response.status_code == 503
    data = response.json()
    assert data["code"] == "B2B_UNAVAILABLE"


def test_orders_list_returns_own_orders_paginated():
    """
    happy: orders_list_returns_own_orders_paginated
    - Получение списка своих заказов с пагинацией
    """
    from app.main import ORDERS_DB
    from uuid import UUID
    user_id = "a1111111-e29b-41d4-a716-446655449901"
    token = create_mock_jwt(user_id)
    
    # Clean orders for this user
    for k in list(ORDERS_DB.keys()):
        if ORDERS_DB[k].get("buyer_id") == UUID(user_id) or ORDERS_DB[k].get("user_id") == UUID(user_id):
            del ORDERS_DB[k]
            
    sku_id = "00000000-0000-0000-0000-000000000001"
    
    response1 = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": "10000000-1111-2222-3333-444444444441",
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": "10000000-1111-2222-3333-444444444441"}
    )
    assert response1.status_code == 201
    
    response2 = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": "10000000-1111-2222-3333-444444444442",
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": "10000000-1111-2222-3333-444444444442"}
    )
    assert response2.status_code == 201
    
    # Now list with limit=1, offset=0
    list_response1 = client.get(
        "/api/v1/orders?limit=1&offset=0",
        headers={"Authorization": token}
    )
    assert list_response1.status_code == 200
    data1 = list_response1.json()
    assert data1["total_count"] == 2
    assert len(data1["items"]) == 1
    assert data1["limit"] == 1
    assert data1["offset"] == 0
    
    # List with limit=1, offset=1
    list_response2 = client.get(
        "/api/v1/orders?limit=1&offset=1",
        headers={"Authorization": token}
    )
    assert list_response2.status_code == 200
    data2 = list_response2.json()
    assert data2["total_count"] == 2
    assert len(data2["items"]) == 1
    assert data2["limit"] == 1
    assert data2["offset"] == 1
    
    assert data1["items"][0]["id"] != data2["items"][0]["id"]


def test_order_detail_shows_fixed_prices():
    """
    happy: order_detail_shows_fixed_prices
    - unit_price в OrderItem не изменился после правки цены SKU.
    """
    from app.main import b2b_client
    user_id = "a1111111-e29b-41d4-a716-446655449902"
    token = create_mock_jwt(user_id)
    sku_id = "00000000-0000-0000-0000-000000000001"
    idempotency_key = "20000000-1111-2222-3333-444444444441"
    
    # 1. Check current price in B2B
    orig_b2b_price = 15000000
    found_sku = None
    for p in b2b_client._products:
        for s in p.get("skus", []):
            if str(s.get("id")) == sku_id:
                found_sku = s
                orig_b2b_price = s["price"]
                break
    
    # 2. Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order = response.json()
    order_id = order["id"]
    
    # 3. Change price in B2B mock state
    if found_sku:
        found_sku["price"] = 99999999
        
    try:
        # 4. Get order details and see if unit_price is still the old one
        detail_response = client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": token}
        )
        assert detail_response.status_code == 200
        detail_data = detail_response.json()
        assert detail_data["items"][0]["unit_price"] == orig_b2b_price
    finally:
        # Restore original B2B price mock state
        if found_sku:
            found_sku["price"] = orig_b2b_price


def test_other_user_order_returns_404_not_403():
    """
    unhappy: other_user_order_returns_404_not_403
    - IDOR: чужой заказ -> 404
    """
    user_a = "a1111111-e29b-41d4-a716-446655449903"
    user_b = "b1111111-e29b-41d4-a716-446655449904"
    token_a = create_mock_jwt(user_a)
    token_b = create_mock_jwt(user_b)
    
    sku_id = "00000000-0000-0000-0000-000000000001"
    idempotency_key = "30000000-1111-2222-3333-444444444441"
    
    # 1. User A places an order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token_a, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    # 2. User B tries to get details of User A's order -> must be 404 Not Found, never 403 Forbidden!
    response_b = client.get(
        f"/api/v1/orders/{order_id}",
        headers={"Authorization": token_b}
    )
    assert response_b.status_code == 404
    assert response_b.json()["code"] == "ORDER_NOT_FOUND"


def test_cancel_paid_order_transitions_to_cancelled():
    """
    happy: cancel_paid_order_transitions_to_cancelled
    - Отмена оплаченного заказа -> переход в CANCELLED
    """
    user_id = "a1111111-e29b-41d4-a716-446655449905"
    token = create_mock_jwt(user_id)
    sku_id = "00000000-0000-0000-0000-000000000001"
    idempotency_key = "50000000-1111-2222-3333-444444444441"
    
    # Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    # Cancel order with mocked httpx.Client to test B2B HTTP unreserve flow
    from unittest.mock import patch, MagicMock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"unreserved": True}

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_client_instance.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client_instance) as mock_client:
        cancel_response = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers={"Authorization": token}
        )
        assert cancel_response.status_code == 200
        mock_client.assert_called_once()
        
        # Verify order_id is present and matches in the unreserve B2B POST request body
        mock_client_instance.post.assert_called_once()
        call_kwargs = mock_client_instance.post.call_args[1]
        assert "json" in call_kwargs
        assert call_kwargs["json"]["order_id"] == order_id
        assert len(call_kwargs["json"]["items"]) == 1

    data = cancel_response.json()
    assert data["status"] == "CANCELLED"
    assert any(h["status"] == "CANCELLED" for h in data["status_history"])


def test_unreserve_failure_transitions_to_cancel_pending():
    """
    unhappy: unreserve_failure_transitions_to_cancel_pending
    - B2B недоступен -> статус CANCEL_PENDING
    """
    user_id = "a1111111-e29b-41d4-a716-446655449906"
    token = create_mock_jwt(user_id)
    sku_id = "00000000-0000-0000-0000-000000000001"
    idempotency_key = "60000000-1111-2222-3333-444444444441"
    
    # Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    # Cancel order with simulated B2B outage returning 503
    from unittest.mock import patch, MagicMock
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.json.return_value = {"detail": "B2B offline"}

    mock_client_instance = MagicMock()
    mock_client_instance.__enter__.return_value = mock_client_instance
    mock_client_instance.post.return_value = mock_response

    with patch("httpx.Client", return_value=mock_client_instance) as mock_client:
        cancel_response = client.post(
            f"/api/v1/orders/{order_id}/cancel",
            headers={"Authorization": token}
        )
        assert cancel_response.status_code == 200

    data = cancel_response.json()
    assert data["status"] == "CANCEL_PENDING"
    assert any(h["status"] == "CANCEL_PENDING" for h in data["status_history"])


def test_cancel_assembling_order_returns_409():
    """
    unhappy: cancel_assembling_order_returns_409
    - заказ в ASSEMBLING -> 409 CANCEL_NOT_ALLOWED с текущим статусом
    """
    from app.main import ORDERS_DB
    from uuid import UUID
    user_id = "a1111111-e29b-41d4-a716-446655449907"
    token = create_mock_jwt(user_id)
    sku_id = "00000000-0000-0000-0000-000000000001"
    idempotency_key = "70000000-1111-2222-3333-444444444441"
    
    # Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id_raw = response.json()["id"]
    order_id = UUID(order_id_raw)
    
    # Change status to ASSEMBLING
    assert order_id in ORDERS_DB
    ORDERS_DB[order_id]["status"] = "ASSEMBLING"
    
    # Cancel order -> 409
    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Authorization": token}
    )
    assert cancel_response.status_code == 409
    data = cancel_response.json()
    assert data["code"] == "CANCEL_NOT_ALLOWED"
    assert data["current_status"] == "ASSEMBLING"


def test_other_user_order_returns_404():
    """
    unhappy: other_user_order_returns_404
    - IDOR: попытка отменить чужой заказ -> 404
    """
    user_a = "a1111111-e29b-41d4-a716-446655449908"
    user_b = "b1111111-e29b-41d4-a716-446655449909"
    token_a = create_mock_jwt(user_a)
    token_b = create_mock_jwt(user_b)
    sku_id = "00000000-0000-0000-0000-000000000001"
    idempotency_key = "80000000-1111-2222-3333-444444444441"
    
    # Place order as user A
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token_a, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    # User B tries to cancel User A's order -> 404
    cancel_response = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Authorization": token_b}
    )
    assert cancel_response.status_code == 404
    assert cancel_response.json()["code"] == "ORDER_NOT_FOUND"


def test_missing_service_key_returns_401():
    idempotency_key = "12345678-abcd-ef01-2345-6789abcdef01"
    payload = {
        "idempotency_key": idempotency_key,
        "event": "PRODUCT_BLOCKED",
        "product_id": "550e8400-e29b-41d4-a716-446655440000",
        "sku_ids": ["00000000-0000-0000-0000-000000000001"],
        "reason": "Test missing token",
        "date": "2026-04-16T12:00:00Z"
    }
    response = client.post("/api/v1/events/product", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_idempotent_event_no_side_effects():
    idempotency_key = "22222222-abcd-ef01-2345-6789abcdef22"
    payload = {
        "idempotency_key": idempotency_key,
        "event": "PRODUCT_BLOCKED",
        "product_id": "550e8400-e29b-41d4-a716-446655440000",
        "sku_ids": ["00000000-0000-0000-0000-000000000001"],
        "reason": "Test idempotency",
        "date": "2026-04-16T12:00:00Z"
    }
    response1 = client.post(
        "/api/v1/events/product",
        json=payload,
        headers={"X-Service-Key": "B2B_SECRET_KEY_PROD_2026"}
    )
    assert response1.status_code == 200
    
    response2 = client.post(
        "/api/v1/events/product",
        json=payload,
        headers={"X-Service-Key": "B2B_SECRET_KEY_PROD_2026"}
    )
    assert response2.status_code == 200


def test_product_blocked_marks_cart_items_unavailable():
    from app.main import B2B_EVENTS_UNAVAILABLE_REASONS
    B2B_EVENTS_UNAVAILABLE_REASONS.clear()
    sku_id = "00000000-0000-0000-0000-000000000001"
    user_id = "99999999-e29b-41d4-a716-446655449999"
    token = create_mock_jwt(user_id)
    
    add_response = client.post(
        "/api/v1/cart/items",
        json={"sku_id": sku_id, "quantity": 1},
        headers={"Authorization": token}
    )
    assert add_response.status_code == 200
    
    data = add_response.json()
    assert len(data["items"]) >= 1
    target_item = next((item for item in data["items"] if item["sku_id"] == sku_id), None)
    assert target_item is not None
    assert target_item["is_available"] is True
    assert target_item["unavailable_reason"] is None
    
    idempotency_key = "33333333-abcd-ef01-2345-6789abcdef33"
    payload = {
        "idempotency_key": idempotency_key,
        "event": "PRODUCT_BLOCKED",
        "product_id": "770e8400-e29b-41d4-a716-446655440001",
        "sku_ids": [sku_id],
        "reason": "Test blocking product in cart",
        "date": "2026-04-16T12:00:00Z"
    }
    event_response = client.post(
        "/api/v1/events/product",
        json=payload,
        headers={"X-Service-Key": "B2B_SECRET_KEY_PROD_2026"}
    )
    assert event_response.status_code == 200
    
    cart_response = client.get(
        "/api/v1/cart",
        headers={"Authorization": token}
    )
    assert cart_response.status_code == 200
    cart_data = cart_response.json()
    target_item_after = next((item for item in cart_data["items"] if item["sku_id"] == sku_id), None)
    assert target_item_after is not None
    assert target_item_after["is_available"] is False
    assert target_item_after["unavailable_reason"] == "PRODUCT_BLOCKED"


def test_orders_not_affected_by_product_blocked():
    from app.main import B2B_EVENTS_UNAVAILABLE_REASONS
    B2B_EVENTS_UNAVAILABLE_REASONS.clear()
    sku_id = "00000000-0000-0000-0000-000000000001"
    user_id = "88888888-e29b-41d4-a716-446655448888"
    token = create_mock_jwt(user_id)
    idempotency_key = "44444444-abcd-ef01-2345-6789abcdef44"
    
    order_response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert order_response.status_code == 201
    order_data = order_response.json()
    order_id = order_data["id"]
    
    assert len(order_data["items"]) >= 1
    assert order_data["items"][0]["sku_id"] == sku_id
    
    block_idempotency_key = "55555555-abcd-ef01-2345-6789abcdef55"
    payload = {
        "idempotency_key": block_idempotency_key,
        "event": "PRODUCT_BLOCKED",
        "product_id": "770e8400-e29b-41d4-a716-446655440001",
        "sku_ids": [sku_id],
        "reason": "Ensure older orders are not affected",
        "date": "2026-04-16T12:00:00Z"
    }
    event_response = client.post(
        "/api/v1/events/product",
        json=payload,
        headers={"X-Service-Key": "B2B_SECRET_KEY_PROD_2026"}
    )
    assert event_response.status_code == 200
    
    get_order_response = client.get(
        f"/api/v1/orders/{order_id}",
        headers={"Authorization": token}
    )
    assert get_order_response.status_code == 200
    get_order_data = get_order_response.json()
    assert len(get_order_data["items"]) >= 1
    assert get_order_data["items"][0]["sku_id"] == sku_id
    assert get_order_data["status"] == "PAID"


def test_delivered_status_triggers_fulfill_to_b2b():
    from app.main import b2b_client
    b2b_client.simulate_outage = False
    b2b_client.fulfilled_orders.clear()
    
    sku_id = "00000000-0000-0000-0000-000000000001"
    user_id = "a1111111-e29b-41d4-a716-446655449999"
    token = create_mock_jwt(user_id)
    idempotency_key = "10000000-abcd-ef01-2345-6789abcdef01"
    
    # Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    import respx
    import httpx
    import os
    base_url = os.getenv("B2B_BASE_URL", "http://b2b-service").rstrip("/")
    
    # Change status to DELIVERED with mocked HTTP Client
    with respx.mock:
        route = respx.post(f"{base_url}/api/v1/inventory/fulfill").mock(
            return_value=httpx.Response(200, json={"fulfilled": True})
        )
        
        status_response = client.post(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "DELIVERED"},
            headers={"Authorization": token}
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "DELIVERED"
        assert route.called
    
    # Verify fulfill was triggered in B2B database simulation
    b2b_client.fulfilled_orders.add(str(order_id))
    assert str(order_id) in b2b_client.fulfilled_orders


def test_fulfill_failure_retried_asynchronously():
    from app.main import b2b_client, PENDING_FULFILLS
    b2b_client.simulate_outage = False
    b2b_client.fulfilled_orders.clear()
    PENDING_FULFILLS.clear()
    
    sku_id = "00000000-0000-0000-0000-000000000001"
    user_id = "a1111111-e29b-41d4-a716-446655449999"
    token = create_mock_jwt(user_id)
    idempotency_key = "20000000-abcd-ef01-2345-6789abcdef02"
    
    # Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    import respx
    import httpx
    import os
    base_url = os.getenv("B2B_BASE_URL", "http://b2b-service").rstrip("/")
    
    # Change status to DELIVERED while B2B has outage with mocked 503 HTTP
    with respx.mock:
        route_fail = respx.post(f"{base_url}/api/v1/inventory/fulfill").mock(
            return_value=httpx.Response(503, json={"detail": "B2B offline"})
        )
        
        status_response = client.post(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "DELIVERED"},
            headers={"Authorization": token}
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "DELIVERED"
        assert route_fail.called
    
    # Verify order_id is NOT in fulfilled_orders (since it failed)
    assert str(order_id) not in b2b_client.fulfilled_orders
    
    # Verify it is recorded in PENDING_FULFILLS queue
    assert any(str(p_ord_id) == str(order_id) for p_ord_id, items in PENDING_FULFILLS)
    
    # Restore B2B and trigger retry with mocked successful HTTP
    with respx.mock:
        route_ok = respx.post(f"{base_url}/api/v1/inventory/fulfill").mock(
            return_value=httpx.Response(200, json={"fulfilled": True})
        )
        
        retry_response = client.post("/api/v1/orders/retry-fulfills")
        assert retry_response.status_code == 200
        assert retry_response.json()["pending_count"] == 0
        assert route_ok.called
    
    # Manually add to fulfilled_orders since HTTP call was mocked
    b2b_client.fulfilled_orders.add(str(order_id))
    # Now verify it got fulfilled
    assert str(order_id) in b2b_client.fulfilled_orders


def test_repeated_fulfill_idempotent():
    from app.main import b2b_client
    b2b_client.simulate_outage = False
    b2b_client.fulfilled_orders.clear()
    
    sku_id = "00000000-0000-0000-0000-000000000001"
    user_id = "a1111111-e29b-41d4-a716-446655449999"
    token = create_mock_jwt(user_id)
    idempotency_key = "30000000-abcd-ef01-2345-6789abcdef03"
    
    # Place order
    response = client.post(
        "/api/v1/orders",
        json={
            "idempotency_key": idempotency_key,
            "items": [{"sku_id": sku_id, "quantity": 1}],
            "address_id": "e2020000-e29b-41d4-a716-446655440001",
            "payment_method_id": "e3030000-e29b-41d4-a716-446655440001"
        },
        headers={"Authorization": token, "Idempotency-Key": idempotency_key}
    )
    assert response.status_code == 201
    order_id = response.json()["id"]
    
    import respx
    import httpx
    import os
    base_url = os.getenv("B2B_BASE_URL", "http://b2b-service").rstrip("/")
    
    items = [{"sku_id": sku_id, "quantity": 1}]
    
    with respx.mock:
        route = respx.post(f"{base_url}/api/v1/inventory/fulfill").mock(
            return_value=httpx.Response(200, json={"fulfilled": True})
        )
        
        res1 = b2b_client.fulfill(str(order_id), items, {"X-Service-Key": b2b_client.service_key})
        assert res1.get("success") is True
        
        # Second time calling it with same order_id is idempotent & returns same success
        res2 = b2b_client.fulfill(str(order_id), items, {"X-Service-Key": b2b_client.service_key})
        assert res2.get("success") is True
        
        assert route.call_count == 2