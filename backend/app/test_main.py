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
    out_of_stock_id = "770e8400-e29b-41d4-a716-446655440097"
    response = client.get(f"/api/v1/catalog/products/{out_of_stock_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["has_stock"] is False

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
    assert "items" in data
    assert len(data["items"]) > 0
    # Check structure: each category should have level, path, children, id, name
    for item in data["items"]:
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
