from fastapi import FastAPI, Query, HTTPException, Header, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.schemas import (
    CategoryRef, CatalogProductCard, PaginatedCatalogProducts,
    FacetsResponse, FacetGroup, FacetItem, CatalogProductDetail,
    BreadcrumbItem, BreadcrumbsResponse, CategoryDetailResponse,
    CategoryTreeNode, FlatCategoryItem,
    FavoriteResponse, FavoritesResponse,
    SubscriptionRequest, SubscriptionResponse, SubscriptionsListResponse,
    CartItemAddRequest, CartItemUpdateRequest, CartItemResponse, CartResponse, CartMergeRequest,
    BannerResponse, BannerEventRequest, Collection, CollectionDetailResponse,
    OrderItemRequest, OrderCreateRequest, OrderItemResponse, OrderResponse, PaginatedOrders,
    OrderCancelRequest, OrderStatusUpdateRequest
)
from app.b2b_client import B2BClient

app = FastAPI(
    title="NeoMarket B2C Catalog API Backend",
    description="Python API backend reproducing exactly the catalog flows for NeoMarket channels",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler to flatten HTTPExceptions into {"code": "...", "message": "..."} format
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": "INVALID_REQUEST", "message": str(exc.detail)}
    )

# Exception handler to flatten RequestValidationErrors into {"code": "INVALID_REQUEST", "message": "..."}
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = errors[0]["msg"] if errors else "Validation Error"
    loc = " -> ".join(str(x) for x in errors[0]["loc"]) if errors else ""
    full_message = f"{msg} (location: {loc})" if loc else msg
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_REQUEST", "message": full_message}
    )

# Instantiate the B2B mock client
b2b_client = B2BClient()

def extract_filter_params(request_params: dict) -> dict:
    """Unpacks nested query parameters like filter[price_min]=... or filters[verified]=..."""
    extracted = {}
    for key, val in request_params.items():
        if (key.startswith("filter[") or key.startswith("filters[")) and key.endswith("]"):
            inner_key = key.split("[", 1)[1][:-1]
            extracted[inner_key] = val
        else:
            extracted[key] = val
    return extracted

def get_breadcrumbs_for_category(categories: List[Dict[str, Any]], cat_id: UUID) -> List[Dict[str, Any]]:
    trail = []
    current_id = cat_id
    while current_id is not None:
        cat = next((c for c in categories if c["id"] == current_id), None)
        if not cat:
            break
        trail.insert(0, {
            "id": cat["id"],
            "slug": cat["slug"],
            "name": cat["name"],
            "url": f"/catalog/{cat['slug']}",
            "level": 0,
            "is_current": False
        })
        current_id = cat["parent_id"]
    
    for i, item in enumerate(trail):
        item["level"] = i
        item["is_current"] = (i == len(trail) - 1)
    return trail

def is_orphan_node(categories: List[Dict[str, Any]], cat_id: UUID) -> bool:
    current_id = cat_id
    visited = set()
    while current_id is not None:
        if current_id in visited:
            return True  # Cycle detected
        visited.add(current_id)
        cat = next((c for c in categories if c["id"] == current_id), None)
        if not cat:
            return True  # Parent not found
        current_id = cat.get("parent_id")
    return False

@app.get("/api/v1/catalog/products", response_model=PaginatedCatalogProducts)
@app.get("/api/v1/products", response_model=PaginatedCatalogProducts)
def get_products(
    request: Request,
    q: Optional[str] = Query(None, max_length=200),
    search: Optional[str] = Query(None, max_length=200),
    sort: str = "popularity",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category_id: Optional[UUID] = Query(None),
    price_min: Optional[int] = Query(None, ge=0),
    price_max: Optional[int] = Query(None, ge=0),
    verified: Optional[str] = Query(None),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # Simulate B2B outage if header is sent
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable (Simulated/Real Outage)"}
        )

    # Extract all query params (including deepObject filters like filter[price_min] or filters[verified])
    params = extract_filter_params(dict(request.query_params))

    search_query = params.get("q") or params.get("search") or q or search or ""
    
    # Resolve and parse UUID category_id
    cat_id_raw = params.get("category_id") or (str(category_id) if category_id else None)
    resolved_category_id = None
    if cat_id_raw:
        try:
            resolved_category_id = UUID(cat_id_raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "Invalid category ID format"}
            )

    # Resolve and parse price ranges (in kopecks)
    p_min_raw = params.get("price_min") or (str(price_min) if price_min is not None else None)
    resolved_price_min = None
    if p_min_raw is not None and p_min_raw != "":
        try:
            resolved_price_min = int(p_min_raw)
            if resolved_price_min < 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "price_min must be a non-negative integer"}
            )

    p_max_raw = params.get("price_max") or (str(price_max) if price_max is not None else None)
    resolved_price_max = None
    if p_max_raw is not None and p_max_raw != "":
        try:
            resolved_price_max = int(p_max_raw)
            if resolved_price_max < 0:
                raise ValueError()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "price_max must be a non-negative integer"}
            )

    resolved_verified = params.get("verified") or verified

    # Validate sort parameter
    resolved_sort = params.get("sort") or sort
    allowed_sort_options = ["popularity", "price_asc", "price_desc", "new", "rating", "date_desc", "discount_desc"]
    if resolved_sort not in allowed_sort_options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_SORT",
                "message": f"Invalid sort parameter. Allowed options: {', '.join(allowed_sort_options)}"
            }
        )

    # Search pattern validation constraint (B2C-2: query length >= 3)
    if search_query:
        if len(search_query) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "Search query must be at least 3 characters"}
            )
        if len(search_query) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "Search query must be at most 255 characters"}
            )

    # Proxy request connection session to simulated B2B API carrying X-Service-Key for auth
    try:
        # Carry standard authenticated header
        effective_key = x_service_key or "B2B_SECRET_KEY_PROD_2026"
        b2b_headers = {"X-Service-Key": effective_key}
        b2b_products = b2b_client.fetch_products(headers=b2b_headers)
        b2b_categories = b2b_client.fetch_categories(headers=b2b_headers)
    except Exception as e:
        # Translate B2B crash into 502/503 Gateway Proxy Error as per DoD
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service raised an integration fault: {str(e)}"}
        )

    # Apply searches
    items = b2b_products
    if search_query:
        lowered = search_query.lower()
        items = [p for p in items if (lowered in p["title"].lower() or lowered in p["description"].lower())]

    # Filter by category
    if resolved_category_id:
        child_ids = [c["id"] for c in b2b_categories if c["parent_id"] == resolved_category_id]
        allowed_ids = [resolved_category_id] + child_ids
        items = [p for p in items if p["category_id"] in allowed_ids]

    # Filter by price bounds (price is in kopecks)
    if resolved_price_min is not None:
        items = [p for p in items if p["price"] >= resolved_price_min]
    if resolved_price_max is not None:
        items = [p for p in items if p["price"] <= resolved_price_max]

    # Filter by verified badge status
    if resolved_verified is not None:
        is_verified = str(resolved_verified).lower() == "true"
        items = [p for p in items if p["verified"] == is_verified]

    # Sorting
    if resolved_sort == "price_asc":
        items.sort(key=lambda x: x["price"])
    elif resolved_sort == "price_desc":
        items.sort(key=lambda x: x["price"], reverse=True)
    elif resolved_sort == "rating":
        items.sort(key=lambda x: x["rating"], reverse=True)
    elif resolved_sort in ["new", "date_desc"]:
        items.sort(key=lambda x: x["id"])
    else:  # "popularity" (default)
        items.sort(key=lambda x: x["subscribers"], reverse=True)

    total_count = len(items)
    paginated = items[offset:offset+limit]

    # Build response collection
    response_items = []
    for p in paginated:
        cat_ref = next((c for c in b2b_categories if c["id"] == p["category_id"]), None)
        cat_path = get_breadcrumbs_for_category(b2b_categories, cat_ref["id"]) if cat_ref else []
        response_items.append({
            "id": p["id"],
            "name": p["title"],
            "slug": p["slug"],
            "category": {
                "id": cat_ref["id"],
                "name": cat_ref["name"],
                "level": len(cat_path) - 1,
                "path": [t["name"] for t in cat_path]
            } if cat_ref else None,
            "min_price": p["price"],
            "old_price": p.get("old_price"),
            "has_stock": p.get("in_stock", True),
            "rating": p.get("rating"),
            "reviews_count": p.get("reviews_count", 0),
            "subscribers": p["subscribers"],
            "monthly_income": p["monthly_income"],
            "er": p["er"],
            "verified": p["verified"],
            "images": p.get("images", []),
            "seller": p.get("seller")
        })

    return PaginatedCatalogProducts(
        items=response_items,
        total_count=total_count,
        limit=limit,
        offset=offset
    )

@app.get("/api/v1/catalog/facets", response_model=FacetsResponse)
def get_facets(
    request: Request,
    category_id: Optional[UUID] = Query(None),
    verified: Optional[str] = Query(None),
    price_min: Optional[int] = Query(None),
    price_max: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # Simulate B2B outage if header is sent
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable (Simulated/Real Outage)"}
        )

    # Extract all query params (including deepObject filters like filter[price_min])
    params = extract_filter_params(dict(request.query_params))

    search_query = params.get("q") or params.get("search") or q or search or ""

    # Resolve category_id
    cat_id_raw = params.get("category_id") or (str(category_id) if category_id else None)
    resolved_category_id = None
    if cat_id_raw:
        try:
            resolved_category_id = UUID(cat_id_raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "Invalid category ID format"}
            )

    # Resolve price bounds (in kopecks)
    p_min_raw = params.get("price_min") or (str(price_min) if price_min is not None else None)
    resolved_price_min = None
    if p_min_raw is not None and p_min_raw != "":
        try:
            resolved_price_min = int(p_min_raw)
        except ValueError:
            pass

    p_max_raw = params.get("price_max") or (str(price_max) if price_max is not None else None)
    resolved_price_max = None
    if p_max_raw is not None and p_max_raw != "":
        try:
            resolved_price_max = int(p_max_raw)
        except ValueError:
            pass

    resolved_verified = params.get("verified") or verified

    try:
        effective_key = x_service_key or "B2B_SECRET_KEY_PROD_2026"
        b2b_headers = {"X-Service-Key": effective_key}
        base_products = b2b_client.fetch_products(headers=b2b_headers)
        b2b_categories = b2b_client.fetch_categories(headers=b2b_headers)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service raised an integration fault: {str(e)}"}
        )

    # Initial search queries filtering
    if search_query and len(search_query) >= 3:
        lowered = search_query.lower()
        base_products = [p for p in base_products if lowered in p["title"].lower() or lowered in p["description"].lower()]

    # Calculate category facets
    category_facets = []
    for cat in b2b_categories:
        # For category counts, we filter by other facets ONLY
        filtered = base_products
        if resolved_verified is not None:
            filtered = [p for p in filtered if p["verified"] == (str(resolved_verified).lower() == "true")]
        if resolved_price_min is not None:
            filtered = [p for p in filtered if p["price"] >= resolved_price_min]
        if resolved_price_max is not None:
            filtered = [p for p in filtered if p["price"] <= resolved_price_max]
        
        # Category target match includes child categories
        target_ids = [cat["id"]] + [c["id"] for c in b2b_categories if c["parent_id"] == cat["id"]]
        count = len([p for p in filtered if p["category_id"] in target_ids])
        category_facets.append({
            "value": cat["name"],
            "text_value": str(cat["id"]),
            "count": count
        })

    # Count verified options
    filtered_for_verified = base_products
    if resolved_category_id:
        child_ids = [c["id"] for c in b2b_categories if c["parent_id"] == resolved_category_id]
        allowed_ids = [resolved_category_id] + child_ids
        filtered_for_verified = [p for p in filtered_for_verified if p["category_id"] in allowed_ids]
    if resolved_price_min is not None:
        filtered_for_verified = [p for p in filtered_for_verified if p["price"] >= resolved_price_min]
    if resolved_price_max is not None:
        filtered_for_verified = [p for p in filtered_for_verified if p["price"] <= resolved_price_max]

    v_count = len([p for p in filtered_for_verified if p["verified"]])
    uv_count = len([p for p in filtered_for_verified if not p["verified"]])

    return FacetsResponse(
        category_id=resolved_category_id,
        facets=[
            FacetGroup(
                name="category",
                values=[FacetItem(**f) for f in category_facets if f["count"] > 0]
            ),
            FacetGroup(
                name="verified",
                values=[
                    FacetItem(value="Верифицированные", text_value="true", count=v_count),
                    FacetItem(value="Обычные", text_value="false", count=uv_count)
                ]
            )
        ]
    )

@app.get("/api/v1/catalog/products/{product_id}", response_model=CatalogProductDetail)
@app.get("/api/v1/products/{product_id}", response_model=CatalogProductDetail)
def get_product_detail(
    product_id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # Simulate B2B outage if header is sent
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable (Simulated/Real Outage)"}
        )

    try:
        effective_key = x_service_key or "B2B_SECRET_KEY_PROD_2026"
        b2b_client._check_auth({"X-Service-Key": effective_key})
        raw_products = b2b_client._products
        b2b_categories = b2b_client._categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service raised an integration fault: {str(e)}"}
        )

    p = next((prod for prod in raw_products if prod["id"] == product_id), None)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )

    # Visibility checks
    if p.get("status") != "MODERATED" or p.get("deleted", False):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product is blocked or deleted"}
        )

    # Process category details
    cat_ref = next((c for c in b2b_categories if c["id"] == p["category_id"]), None)
    cat_path = get_breadcrumbs_for_category(b2b_categories, cat_ref["id"]) if cat_ref else []

    # Map available SKUs (Ensure strict safety - cost_price and reserved_quantity never leak)
    formatted_skus = []
    raw_skus = p.get("skus", [])
    if not raw_skus:
        # Provide a standard B2C sku mapping matching loaded cards
        raw_skus = [{
            "id": p['id'],
            "name": "Полная передача прав (Базовый)",
            "sku_code": f"TG-{p['slug'].upper()}-BASE",
            "price": p["price"],
            "old_price": p.get("old_price"),
            "available_quantity": p.get("active_quantity", 0),
            "attributes": { "Помощь в транзите": "Да", "Обучение": "7 дней" },
            "images": p.get("images", [])
        }]

    for sku in raw_skus:
        # Calculate discount: if there is an old price and it is higher than current price
        price = sku["price"]
        old_price = sku.get("old_price", 0) or 0
        calculated_discount = max(0, old_price - price) if old_price > 0 else 0

        sku_clean = {
            "id": str(sku["id"]),
            "name": sku["name"],
            "sku_code": sku["sku_code"],
            "price": price,
            "old_price": sku.get("old_price"),
            "discount": calculated_discount,
            "available_quantity": sku.get("available_quantity", sku.get("active_quantity", 0)),
            "attributes": sku.get("attributes", {}),
            "images": sku.get("images", p.get("images", []))
        }
        # Express-ly erase any private field if present (Double-Glow Defense Pattern)
        if "cost_price" in sku_clean:
            del sku_clean["cost_price"]
        if "reserved_quantity" in sku_clean:
            del sku_clean["reserved_quantity"]
        formatted_skus.append(sku_clean)

    # Product overall availability reflects active_quantity / SKU quantities
    has_stock = any(sku["available_quantity"] > 0 for sku in formatted_skus) or p.get("active_quantity", 0) > 0

    response_data = {
        "id": p["id"],
        "name": p["title"],
        "slug": p["slug"],
        "description": p["description"],
        "category": {
            "id": cat_ref["id"],
            "name": cat_ref["name"],
            "level": len(cat_path) - 1,
            "path": [t["name"] for t in cat_path]
        } if cat_ref else None,
        "min_price": p["price"],
        "old_price": p.get("old_price"),
        "has_stock": has_stock,
        "rating": p.get("rating"),
        "reviews_count": p.get("reviews_count", 0),
        "subscribers": p["subscribers"],
        "monthly_income": p["monthly_income"],
        "er": p["er"],
        "verified": p["verified"],
        "images": p.get("images", []),
        "seller": p.get("seller"),
        "attributes": p.get("attributes", {
            "Subscribers": p["subscribers"],
            "ER": f"{p['er']}%",
            "Verified": "Yes" if p["verified"] else "No"
        }),
        "characteristics": p.get("characteristics", [
            { "name": "Тематика", "value": cat_ref["name"] if cat_ref else "Медиабизнес" },
            { "name": "Язык аудитории", "value": "Русский" },
            { "name": "Вовлеченность (ER)", "value": f"{p['er']}%" }
        ]),
        "skus": formatted_skus
    }

    return CatalogProductDetail(**response_data)


@app.get("/api/v1/catalog/products/{product_id}/similar", response_model=List[CatalogProductCard])
@app.get("/api/v1/products/{product_id}/similar", response_model=List[CatalogProductCard])
def get_similar_products(
    product_id: UUID,
    limit: int = Query(8, ge=1, le=20),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable (Simulated/Real Outage)"}
        )

    try:
        effective_key = x_service_key or "B2B_SECRET_KEY_PROD_2026"
        b2b_headers = {"X-Service-Key": effective_key}
        raw_products = b2b_client._products
        b2b_categories = b2b_client._categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service raised an integration fault: {str(e)}"}
        )

    p = next((prod for prod in raw_products if prod["id"] == product_id), None)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )

    # Establish similarity search using matching subcategory, sister category or parent categories
    cur_cat = next((c for c in b2b_categories if c["id"] == p["category_id"]), None)
    allowed_category_ids = [p["category_id"]]
    if cur_cat and cur_cat["parent_id"]:
        allowed_category_ids.append(cur_cat["parent_id"])
        sister_ids = [c["id"] for c in b2b_categories if c["parent_id"] == cur_cat["parent_id"]]
        allowed_category_ids.extend(sister_ids)

    similar_set = []
    for prod in raw_products:
        if prod["id"] == product_id:
            continue
        # Only visible (status MODERATED, not deleted, active_quantity > 0)
        if prod.get("status") == "MODERATED" and not prod.get("deleted", False) and prod.get("active_quantity", 0) > 0:
            if prod["category_id"] in allowed_category_ids:
                similar_set.append(prod)

    similar_sliced = similar_set[:limit]

    response_items = []
    for sp in similar_sliced:
        cat_ref = next((c for c in b2b_categories if c["id"] == sp["category_id"]), None)
        cat_path = get_breadcrumbs_for_category(b2b_categories, cat_ref["id"]) if cat_ref else []
        response_items.append({
            "id": sp["id"],
            "name": sp["title"],
            "slug": sp["slug"],
            "category": {
                "id": cat_ref["id"],
                "name": cat_ref["name"],
                "level": len(cat_path) - 1,
                "path": [t["name"] for t in cat_path]
            } if cat_ref else None,
            "min_price": sp["price"],
            "old_price": sp.get("old_price"),
            "has_stock": sp.get("active_quantity", 0) > 0,
            "rating": sp.get("rating"),
            "reviews_count": sp.get("reviews_count", 0),
            "subscribers": sp["subscribers"],
            "monthly_income": sp["monthly_income"],
            "er": sp["er"],
            "verified": sp["verified"],
            "images": sp.get("images", []),
            "seller": sp.get("seller")
        })

    return response_items


@app.get("/api/v1/breadcrumbs", response_model=BreadcrumbsResponse)
def get_breadcrumbs(
    category_id: Optional[UUID] = Query(None),
    product_id: Optional[UUID] = Query(None),
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable (Simulated/Real Outage)"}
        )

    # 400 cases for parameters validations
    if category_id is not None and product_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "AMBIGUOUS_PARAM", "message": "only one of category_id or product_id must be provided"}
        )
    if category_id is None and product_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_PARAM", "message": "category_id or product_id must be provided"}
        )

    try:
        effective_key = x_service_key or "B2B_SECRET_KEY_PROD_2026"
        b2b_headers = {"X-Service-Key": effective_key}
        raw_products = b2b_client._products
        b2b_categories = b2b_client._categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service raised an integration fault: {str(e)}"}
        )

    target_category_id = None
    resolved_via = "category_id"

    if category_id:
        target_category_id = category_id
    elif product_id:
        resolved_via = "product_id"
        p = next((prod for prod in raw_products if prod["id"] == product_id), None)
        if not p:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": "Product not found"}
            )
        target_category_id = p["category_id"]

    # Verify category exists
    cat_exists = next((c for c in b2b_categories if c["id"] == target_category_id), None)
    if not cat_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Category not found"}
        )

    # Validate orphan/broken hierarchy
    if is_orphan_node(b2b_categories, target_category_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ORPHAN_NODE", "message": "category hierarchy is broken"}
        )

    trail = get_breadcrumbs_for_category(b2b_categories, target_category_id)

    items = [BreadcrumbItem(**t) for t in trail]

    return BreadcrumbsResponse(
        data=items,
        meta={
            "resolved_via": resolved_via,
            "category_id": str(target_category_id)
        }
    )


@app.get("/api/v1/catalog/categories/tree", response_model=List[CategoryTreeNode])
@app.get("/api/v1/categories/tree", response_model=List[CategoryTreeNode])
@app.get("/categories/tree", response_model=List[CategoryTreeNode])
def get_categories_tree(
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
        )
    try:
        b2b_categories = b2b_client._categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": str(e)}
        )

    # Validate broken hierarchy/orphan node in database
    for cat in b2b_categories:
        if is_orphan_node(b2b_categories, cat["id"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "ORPHAN_NODE", "message": "category hierarchy is broken"}
            )

    def build_tree(parent_id: Optional[UUID]) -> List[Dict[str, Any]]:
        nodes = []
        for cat in b2b_categories:
            if cat["parent_id"] == parent_id:
                trail = get_breadcrumbs_for_category(b2b_categories, cat["id"])
                nodes.append({
                    "id": cat["id"],
                    "name": cat["name"],
                    "parent_id": cat["parent_id"],
                    "level": len(trail) - 1,
                    "path": [t["name"] for t in trail],
                    "children": build_tree(cat["id"])
                })
        return nodes

    tree = build_tree(None)
    return tree


@app.get("/api/v1/catalog/categories", response_model=List[FlatCategoryItem])
@app.get("/api/v1/categories", response_model=List[FlatCategoryItem])
@app.get("/categories", response_model=List[FlatCategoryItem])
def get_flat_categories(
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
        )
    try:
        b2b_categories = b2b_client._categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": str(e)}
        )

    # Validate broken hierarchy/orphan node in database
    for cat in b2b_categories:
        if is_orphan_node(b2b_categories, cat["id"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "ORPHAN_NODE", "message": "category hierarchy is broken"}
            )

    refs = []
    for c in b2b_categories:
        trail = get_breadcrumbs_for_category(b2b_categories, c["id"])
        refs.append({
            "id": c["id"],
            "name": c["name"],
            "parent_id": c["parent_id"],
            "level": len(trail) - 1,
            "path": [t["name"] for t in trail]
        })
    return refs


@app.get("/api/v1/catalog/categories/{id}", response_model=CategoryDetailResponse)
@app.get("/api/v1/categories/{id}", response_model=CategoryDetailResponse)
def get_category_details(
    id: UUID,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
        )
    try:
        b2b_categories = b2b_client._categories
        raw_products = b2b_client._products
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": str(e)}
        )

    # Validate category exists
    cat = next((c for c in b2b_categories if c["id"] == id), None)
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Category with ID {id} not found."}
        )

    # Validate orphan/broken hierarchy
    if is_orphan_node(b2b_categories, id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ORPHAN_NODE", "message": "category hierarchy is broken"}
        )

    parent_cat = next((p for p in b2b_categories if p["id"] == cat["parent_id"]), None) if cat.get("parent_id") else None

    # Filter with B2B status/moderated rules
    moderated_products = [
        p for p in raw_products 
        if p.get("status") == "MODERATED" and not p.get("deleted", False) and p.get("active_quantity", 0) > 0
    ]
    product_count = len([p for p in moderated_products if p["category_id"] == id])

    return {
        "id": cat["id"],
        "name": cat["name"],
        "slug": cat["slug"],
        "description": f"Premium channels in {cat['name']} marketplace. Ideal for media business and automated ad revenue.",
        "parent": {
            "id": parent_cat["id"],
            "name": parent_cat["name"],
            "slug": parent_cat["slug"]
        } if parent_cat else None,
        "product_count": product_count,
        "seo": {
            "title": f"Buy TG Channel in {cat['name']} | NeoMarket",
            "description": f"Premium and moderated Telegram channels specializing in {cat['name']}. Instant and safe ownership transfer.",
            "keywords": ["telegram channels", cat["slug"], "buy telegram chat"]
        },
        "is_active": True,
        "created_at": "2026-01-15T10:30:00Z"
    }


# Simulated B2C database for favorites
# Key: user_id (UUID), Value: List of Dict containing product_id (UUID) and added_at (str)
FAVORITES_DB: Dict[UUID, List[Dict[str, Any]]] = {}

# Simulated B2C database for physical B2B events status
# Key: sku_id (UUID), Value: unavailable_reason string (e.g., "PRODUCT_BLOCKED", "PRODUCT_DELETED", "OUT_OF_STOCK")
B2B_EVENTS_UNAVAILABLE_REASONS: Dict[UUID, str] = {}
PROCESSED_B2B_EVENTS_KEYS = set()

# Simulated B2C database for subscriptions
# Key: user_id (UUID), Value: List of Dict containing id (UUID), product_id (UUID), notify_on (List[str]), and created_at (str)
SUBSCRIPTIONS_DB: Dict[UUID, List[Dict[str, Any]]] = {}

# Simulated B2C database for collections
# Key: collection_id (UUID), Value: Dict of metadata and referenced product IDs
COLLECTIONS_DB: Dict[UUID, Dict[str, Any]] = {
    UUID("d70e8400-e29b-41d4-a716-446655440001"): {
        "id": UUID("d70e8400-e29b-41d4-a716-446655440001"),
        "name": "Хиты продаж",
        "description": "Самые популярные каналы с высокой доходностью",
        "product_ids": [
            UUID("770e8400-e29b-41d4-a716-446655440001"),
            UUID("770e8400-e29b-41d4-a716-446655440002")
        ]
    },
    UUID("d70e8400-e29b-41d4-a716-446655440002"): {
        "id": UUID("d70e8400-e29b-41d4-a716-446655440002"),
        "name": "Новинки сезона",
        "description": "Свежие каналы, недавно добавленные на биржу",
        "product_ids": [
            UUID("770e8400-e29b-41d4-a716-446655440003"),
            UUID("770e8400-e29b-41d4-a716-446655440099"),  # DRAFT in B2B
            UUID("770e8400-e29b-41d4-a716-446655440098")   # DELETED in B2B
        ]
    }
}

# Simulated B2C database for orders
# Key: order_id (UUID), Value: Dict of order details
ORDERS_DB: Dict[UUID, Dict[str, Any]] = {}
PENDING_FULFILLS: List[tuple] = []


def decode_jwt(token: str) -> dict:
    import base64
    import json
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        token = token.strip()
        parts = token.split(".")
        if len(parts) == 3:
            payload_b64 = parts[1]
            payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
            payload_str = base64.urlsafe_b64decode(payload_b64).decode("utf-8")
            return json.loads(payload_str)
        else:
            try:
                decoded = base64.b64decode(token + "==").decode("utf-8")
                return json.loads(decoded)
            except Exception:
                return {"sub": token}
    except Exception:
        return {"sub": token}

def get_user_id_from_auth(authorization: Optional[str]) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Bearer token is missing or invalid"}
        )
    claims = decode_jwt(authorization)
    user_id_str = claims.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid token content"}
        )
    try:
        return UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "sub claim must be a valid UUID"}
        )


@app.put("/api/v1/favorites/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def add_to_favorites_put(
    product_id: UUID,
    user_id: Optional[UUID] = Query(None),  # Ignored for IDOR protection
    authorization: Optional[str] = Header(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # 1. JWT auth and extraction
    curr_user_id = get_user_id_from_auth(authorization)
    
    # 2. Check outage
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
         )
         
    # 3. Check if product exists in B2B database
    try:
        raw_products = b2b_client._products
    except Exception as e:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service error: {str(e)}"}
         )
         
    product = next((p for p in raw_products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 4. Handle addition
    if curr_user_id not in FAVORITES_DB:
        FAVORITES_DB[curr_user_id] = []
        
    user_favs = FAVORITES_DB[curr_user_id]
    existing = next((f for f in user_favs if f["product_id"] == product_id), None)
    
    from datetime import datetime
    now_str = datetime.utcnow().isoformat() + "Z"
    
    if not existing:
        new_fav = {
            "product_id": product_id,
            "added_at": now_str
        }
        user_favs.append(new_fav)
        
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/favorites/{product_id}", response_model=FavoriteResponse)
def add_to_favorites(
    product_id: UUID,
    response: Response,
    user_id: Optional[UUID] = Query(None),  # Ignored for IDOR protection
    authorization: Optional[str] = Header(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # 1. JWT auth and extraction
    curr_user_id = get_user_id_from_auth(authorization)
    
    # 2. Check outage
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
         )
         
    # 3. Check if product exists in B2B database
    try:
        raw_products = b2b_client._products
    except Exception as e:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service error: {str(e)}"}
         )
         
    product = next((p for p in raw_products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
    
    # 4. Handle addition
    if curr_user_id not in FAVORITES_DB:
        FAVORITES_DB[curr_user_id] = []
        
    user_favs = FAVORITES_DB[curr_user_id]
    existing = next((f for f in user_favs if f["product_id"] == product_id), None)
    
    from datetime import datetime
    now_str = datetime.utcnow().isoformat() + "Z"
    
    if existing:
        # Repeat add returns 200, body with existing/current added_at
        response.status_code = status.HTTP_200_OK
        return {
            "product_id": product_id,
            "user_id": curr_user_id,
            "added_at": existing["added_at"]
        }
    else:
        # First add returns 201
        new_fav = {
            "product_id": product_id,
            "added_at": now_str
        }
        user_favs.append(new_fav)
        response.status_code = status.HTTP_201_CREATED
        return {
            "product_id": product_id,
            "user_id": curr_user_id,
            "added_at": now_str
        }


@app.delete("/api/v1/favorites/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_from_favorites(
    product_id: UUID,
    user_id: Optional[UUID] = Query(None),  # Ignored for IDOR protection
    authorization: Optional[str] = Header(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # JWT auth and extraction
    curr_user_id = get_user_id_from_auth(authorization)
    
    # Check outage
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
         )
         
    if curr_user_id in FAVORITES_DB:
        FAVORITES_DB[curr_user_id] = [f for f in FAVORITES_DB[curr_user_id] if f["product_id"] != product_id]
        
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/v1/favorites", response_model=PaginatedCatalogProducts)
def get_favorites(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: Optional[UUID] = Query(None),  # Ignored for IDOR protection
    authorization: Optional[str] = Header(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # JWT auth and extraction
    curr_user_id = get_user_id_from_auth(authorization)
    
    # Check outage
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
        )
        
    # Get user's favorites from simulated B2C DB
    user_fav_records = FAVORITES_DB.get(curr_user_id, [])
    
    # If empty, return immediately
    if not user_fav_records:
        return {
            "items": [],
            "total_count": 0,
            "limit": limit,
            "offset": offset
        }
        
    # Fetch moderated products from B2B to enrich data
    try:
        effective_key = "B2B_SECRET_KEY_PROD_2026"
        b2b_headers = {"X-Service-Key": effective_key}
        b2b_products = b2b_client.fetch_products(headers=b2b_headers)
        b2b_categories = b2b_client.fetch_categories(headers=b2b_headers)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service error: {str(e)}"}
        )
        
    # Enrich and filter favorites
    enriched_items = []
    
    for fav_rec in user_fav_records:
        prod_id = fav_rec["product_id"]
        p = next((prod for prod in b2b_products if prod["id"] == prod_id), None)
        if p:
            # Format category
            cat_ref = next((c for c in b2b_categories if c["id"] == p["category_id"]), None)
            cat_path = get_breadcrumbs_for_category(b2b_categories, cat_ref["id"]) if cat_ref else []
            
            # Format skus
            formatted_skus = []
            raw_skus = p.get("skus", [])
            if not raw_skus:
                raw_skus = [{
                    "id": p['id'],
                    "name": "Полная передача прав (Базовый)",
                    "sku_code": f"TG-{p['slug'].upper()}-BASE",
                    "price": p["price"],
                    "old_price": p.get("old_price"),
                    "available_quantity": p.get("active_quantity", 0),
                    "attributes": { "Помощь в транзите": "Да", "Обучение": "7 дней" },
                    "images": p.get("images", [])
                }]

            for sku in raw_skus:
                price = sku["price"]
                old_price = sku.get("old_price", 0) or 0
                calculated_discount = max(0, old_price - price) if old_price > 0 else 0

                sku_clean = {
                    "id": str(sku["id"]),
                    "name": sku["name"],
                    "sku_code": sku["sku_code"],
                    "price": price,
                    "old_price": sku.get("old_price"),
                    "discount": calculated_discount,
                    "available_quantity": sku.get("available_quantity", sku.get("active_quantity", 0)),
                    "attributes": sku.get("attributes", {}),
                    "images": sku.get("images", p.get("images", []))
                }
                formatted_skus.append(sku_clean)
                
            has_stock = any(sku["available_quantity"] > 0 for sku in formatted_skus) or p.get("active_quantity", 0) > 0
            
            enriched_items.append({
                "id": p["id"],
                "name": p["title"],
                "slug": p["slug"],
                "category": {
                    "id": cat_ref["id"],
                    "name": cat_ref["name"],
                    "level": len(cat_path) - 1,
                    "path": [t["name"] for t in cat_path]
                } if cat_ref else None,
                "min_price": p["price"],
                "old_price": p.get("old_price"),
                "has_stock": has_stock,
                "rating": p.get("rating"),
                "reviews_count": p.get("reviews_count", 0),
                "subscribers": p["subscribers"],
                "monthly_income": p["monthly_income"],
                "er": p["er"],
                "verified": p["verified"],
                "images": p.get("images", []),
                "seller": p.get("seller"),
                "skus": formatted_skus,
                "added_at": fav_rec["added_at"]
            })
            
    total_count = len(enriched_items)
    paginated_items = enriched_items[offset:offset+limit]
    
    return {
        "items": paginated_items,
        "total_count": total_count,
        "limit": limit,
        "offset": offset
    }


def validate_notify_on(notify_on: Any, field_name: str = "notify_on"):
    if not notify_on:  # empty or None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": f"{field_name} list must not be empty"}
        )
    if not isinstance(notify_on, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": f"{field_name} must be a list of strings"}
        )
    valid_events = {"PRICE_DROP", "BACK_IN_STOCK"}
    for item in notify_on:
        if not item or item not in valid_events:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": f"Invalid {field_name} event: '{item}'. Allowed: {list(valid_events)}"}
            )


@app.get("/api/v1/subscribe", response_model=SubscriptionsListResponse)
@app.get("/subscribe", response_model=SubscriptionsListResponse)
def get_subscriptions(
    authorization: Optional[str] = Header(None)
):
    curr_user_id = get_user_id_from_auth(authorization)
    user_subs = SUBSCRIPTIONS_DB.get(curr_user_id, [])
    return {"items": user_subs}


@app.post("/api/v1/favorites/{product_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def create_subscription_openapi(
    product_id: UUID,
    payload: SubscriptionRequest,
    authorization: Optional[str] = Header(None)
):
    # 1. JWT auth and extraction
    curr_user_id = get_user_id_from_auth(authorization)
    
    # OpenAPI uses events instead of notify_on
    events = payload.events if payload.events is not None else payload.notify_on
    if events is None:
        events = ["BACK_IN_STOCK", "PRICE_DROP"]
        
    # 2. Validate events
    validate_notify_on(events, field_name="events")
    
    # 3. Check if product exists in B2B database
    try:
        raw_products = b2b_client._products
    except Exception as e:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service error: {str(e)}"}
         )
         
    product = next((p for p in raw_products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
        
    # 4. Check for duplicate subscription -> 409
    if curr_user_id not in SUBSCRIPTIONS_DB:
        SUBSCRIPTIONS_DB[curr_user_id] = []
        
    user_subs = SUBSCRIPTIONS_DB[curr_user_id]
    existing = next((s for s in user_subs if s["product_id"] == product_id), None)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_SUBSCRIPTION", "message": "Subscription for this product already exists"}
        )
        
    # 5. Create subscription
    import uuid
    from datetime import datetime
    sub_id = uuid.uuid4()
    now_str = datetime.utcnow().isoformat() + "Z"
    
    new_sub = {
        "id": sub_id,
        "product_id": product_id,
        "user_id": curr_user_id,
        "notify_on": events,
        "events": events,
        "created_at": now_str
    }
    user_subs.append(new_sub)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/subscribe/{product_id}", status_code=status.HTTP_201_CREATED, response_model=SubscriptionResponse)
def create_subscription_legacy(
    product_id: UUID,
    payload: SubscriptionRequest,
    authorization: Optional[str] = Header(None)
):
    curr_user_id = get_user_id_from_auth(authorization)
    events = payload.notify_on if payload.notify_on is not None else payload.events
    if events is None:
        events = ["BACK_IN_STOCK", "PRICE_DROP"]
    validate_notify_on(events, field_name="notify_on")
    
    try:
        raw_products = b2b_client._products
    except Exception as e:
         raise HTTPException(
             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
             detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service error: {str(e)}"}
         )
         
    product = next((p for p in raw_products if p["id"] == product_id), None)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Product not found"}
        )
        
    if curr_user_id not in SUBSCRIPTIONS_DB:
        SUBSCRIPTIONS_DB[curr_user_id] = []
        
    user_subs = SUBSCRIPTIONS_DB[curr_user_id]
    existing = next((s for s in user_subs if s["product_id"] == product_id), None)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_SUBSCRIPTION", "message": "Subscription for this product already exists"}
        )
        
    import uuid
    from datetime import datetime
    sub_id = uuid.uuid4()
    now_str = datetime.utcnow().isoformat() + "Z"
    
    new_sub = {
        "id": sub_id,
        "product_id": product_id,
        "user_id": curr_user_id,
        "notify_on": events,
        "events": events,
        "created_at": now_str
    }
    user_subs.append(new_sub)
    return new_sub


@app.delete("/api/v1/favorites/{product_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
@app.delete("/api/v1/subscribe/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
@app.delete("/subscribe/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
@app.delete("/api/v1/subscribe", status_code=status.HTTP_204_NO_CONTENT)
@app.delete("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_product(
    product_id: Optional[UUID] = None,
    product_id_query: Optional[UUID] = Query(None, alias="product_id"),
    authorization: Optional[str] = Header(None)
):
    # JWT auth and extraction
    curr_user_id = get_user_id_from_auth(authorization)
    
    resolved_product_id = product_id or product_id_query
    if not resolved_product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "product_id is required"}
        )
        
    if curr_user_id in SUBSCRIPTIONS_DB:
        SUBSCRIPTIONS_DB[curr_user_id] = [
            s for s in SUBSCRIPTIONS_DB[curr_user_id] if s["product_id"] != resolved_product_id
        ]
        
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- US-CART-03: Cart management ---

CART_DB: Dict[str, Dict[str, int]] = {}


def find_sku_and_product_in_b2b(b2b_products: list, sku_id: Any):
    target_sku_str = str(sku_id)
    for p in b2b_products:
        raw_skus = p.get("skus", [])
        if not raw_skus:
            # Fallback SKU simulation
            fallback_sku_id = p['id']
            if str(fallback_sku_id) == target_sku_str:
                fallback_sku = {
                    "id": fallback_sku_id,
                    "name": "Полная передача прав (Базовый)",
                    "sku_code": f"TG-{p['slug'].upper()}-BASE",
                    "price": p["price"],
                    "old_price": p.get("old_price"),
                    "available_quantity": p.get("active_quantity", 0),
                    "attributes": { "Помощь в транзите": "Да", "Обучение": "7 дней" },
                    "images": p.get("images", [])
                }
                return fallback_sku, p
        else:
            for s in raw_skus:
                if str(s.get("id")) == target_sku_str:
                    sku_data = {
                        "id": s.get("id"),
                        "name": s["name"],
                        "sku_code": s["sku_code"],
                        "price": s["price"],
                        "old_price": s.get("old_price"),
                        "available_quantity": s.get("available_quantity", s.get("active_quantity", 0)),
                        "attributes": s.get("attributes", {}),
                        "images": s.get("images", p.get("images", []))
                    }
                    return sku_data, p
    return None, None


def get_cart_owner_id(authorization: Optional[str], x_session_id: Optional[str], session_id_query: Optional[str] = None) -> str:
    if authorization and authorization.startswith("Bearer "):
        try:
            claims = decode_jwt(authorization)
            user_id_str = claims.get("sub")
            if user_id_str:
                return str(user_id_str)
        except Exception:
            pass
    
    resolved_session = x_session_id or session_id_query
    if resolved_session:
        return str(resolved_session)
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Bearer token or X-Session-Id is missing"}
    )


def _build_cart_response(owner_id: str, x_simulate_b2b_outage: Optional[str] = None) -> dict:
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
         raise HTTPException(
             status_code=status.HTTP_502_BAD_GATEWAY,
             detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
         )
         
    try:
        effective_key = "B2B_SECRET_KEY_PROD_2026"
        b2b_headers = {"X-Service-Key": effective_key}
        b2b_products = b2b_client.fetch_products(headers=b2b_headers)
        b2b_categories = b2b_client.fetch_categories(headers=b2b_headers)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": f"B2B service error: {str(e)}"}
        )

    items_in_cart = CART_DB.get(owner_id, {})
    enriched_items = []
    total_amount = 0
    
    for sku_id, quantity in items_in_cart.items():
        raw_sku, raw_product = find_sku_and_product_in_b2b(b2b_client._products, sku_id)
        active_sku, active_product = find_sku_and_product_in_b2b(b2b_products, sku_id)
        
        unavailable_reason = None
        local_reason = B2B_EVENTS_UNAVAILABLE_REASONS.get(UUID(sku_id) if isinstance(sku_id, str) else sku_id)
        if local_reason:
            unavailable_reason = local_reason
        elif not raw_sku or not raw_product:
            unavailable_reason = "SKU_NOT_FOUND"
        elif raw_product.get("deleted", False):
            unavailable_reason = "DELETED"
        elif raw_product.get("status") != "MODERATED":
            unavailable_reason = "UNPUBLISHED"
        elif raw_sku.get("available_quantity", 0) <= 0:
            unavailable_reason = "OUT_OF_STOCK"
        elif not active_sku or not active_product:
            unavailable_reason = "UNAVAILABLE"
            
        product_id = "00000000-0000-0000-0000-000000000000"
        name = "Unknown Product"
        sku_code = None
        unit_price = 0
        unit_price_at_add = None
        line_total = 0
        available_quantity = 0
        is_available = (unavailable_reason is None)
        image = None

        sku_clean = None
        product_clean = None
        subtotal = 0
        
        resolved_sku = active_sku or raw_sku
        resolved_product = active_product or raw_product
        
        if resolved_product and resolved_sku:
            product_images = resolved_product.get("images", [])
            images_formatted = []
            for img in product_images:
                images_formatted.append({
                    "id": str(img.get("id")),
                    "url": img.get("url"),
                    "alt": img.get("alt", None),
                    "ordering": img.get("ordering", 0),
                    "is_main": img.get("is_main", False)
                })

            sku_images_formatted = []
            for img in resolved_sku.get("images", []):
                sku_images_formatted.append({
                    "id": str(img.get("id")),
                    "url": img.get("url"),
                    "alt": img.get("alt", None),
                    "ordering": img.get("ordering", 0),
                    "is_main": img.get("is_main", False)
                })
            if not sku_images_formatted:
                sku_images_formatted = images_formatted

            price = resolved_sku["price"]
            old_price = resolved_sku.get("old_price", 0) or 0
            calculated_discount = max(0, old_price - price) if old_price > 0 else 0

            sku_clean = {
                "id": str(resolved_sku["id"]),
                "name": resolved_sku["name"],
                "sku_code": resolved_sku["sku_code"],
                "price": price,
                "old_price": resolved_sku.get("old_price"),
                "discount": calculated_discount,
                "available_quantity": resolved_sku.get("available_quantity", 0),
                "attributes": resolved_sku.get("attributes", {}),
                "images": sku_images_formatted
            }
            
            cat_ref = next((c for c in b2b_categories if c["id"] == resolved_product["category_id"]), None)
            cat_path = get_breadcrumbs_for_category(b2b_categories, cat_ref["id"]) if cat_ref else []

            product_clean = {
                "id": resolved_product["id"],
                "name": resolved_product["title"],
                "slug": resolved_product["slug"],
                "category": {
                    "id": cat_ref["id"],
                    "name": cat_ref["name"],
                    "level": len(cat_path) - 1,
                    "path": [t["name"] for t in cat_path]
                } if cat_ref else None,
                "min_price": resolved_product["price"],
                "old_price": resolved_product.get("old_price"),
                "has_stock": resolved_product.get("in_stock", True),
                "rating": resolved_product.get("rating"),
                "reviews_count": resolved_product.get("reviews_count", 0),
                "subscribers": resolved_product.get("subscribers", 0),
                "monthly_income": resolved_product.get("monthly_income", 0),
                "er": resolved_product.get("er", 0.0),
                "verified": resolved_product.get("verified", False),
                "images": images_formatted,
                "seller": resolved_product.get("seller")
            }
            
            product_id = resolved_product["id"]
            name = f"{resolved_product['title']} - {resolved_sku['name']}"
            sku_code = resolved_sku.get("sku_code")
            unit_price = price
            unit_price_at_add = price
            available_quantity = resolved_sku.get("available_quantity", resolved_sku.get("active_quantity", 0))
            if sku_images_formatted:
                image = sku_images_formatted[0]
            
            if not unavailable_reason:
                line_total = price * quantity
                total_amount += line_total
                
        enriched_items.append({
            "sku_id": sku_id,
            "product_id": product_id,
            "name": name,
            "sku_code": sku_code,
            "quantity": quantity,
            "unit_price": unit_price,
            "unit_price_at_add": unit_price_at_add,
            "line_total": line_total,
            "available_quantity": available_quantity,
            "is_available": is_available,
            "image": image,
            
            # UI compatibility
            "sku": sku_clean,
            "product": product_clean,
            "unavailable_reason": unavailable_reason,
            "price_at_addition": unit_price if sku_clean else None,
            "subtotal": line_total
        })
        
    items_count = sum(item["quantity"] for item in enriched_items)
    subtotal_total = sum(item["line_total"] for item in enriched_items)
    is_valid = all(item["is_available"] and item["quantity"] <= item["available_quantity"] for item in enriched_items)
    from datetime import datetime
    updated_at_str = datetime.utcnow().isoformat() + "Z"

    return {
        "id": owner_id,
        "items": enriched_items,
        "items_count": items_count,
        "subtotal": subtotal_total,
        "is_valid": is_valid,
        "updated_at": updated_at_str,
        
        # UI compatibility
        "total_amount": subtotal_total
    }


@app.get("/api/v1/cart", response_model=CartResponse)
@app.get("/cart", response_model=CartResponse)
def get_cart(
    authorization: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    session_id: Optional[str] = Query(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    owner_id = get_cart_owner_id(authorization, x_session_id, session_id)
    return _build_cart_response(owner_id, x_simulate_b2b_outage)


@app.post("/api/v1/cart/items", response_model=CartResponse)
@app.post("/cart/items", response_model=CartResponse)
def add_cart_item(
    payload: CartItemAddRequest,
    authorization: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    session_id: Optional[str] = Query(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    owner_id = get_cart_owner_id(authorization, x_session_id, session_id)
    
    # Check if SKU exists at all in B2B raw database
    raw_sku, raw_product = find_sku_and_product_in_b2b(b2b_client._products, payload.sku_id)
    if not raw_sku:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SKU_NOT_FOUND", "message": f"SKU with ID '{payload.sku_id}' not found"}
        )
        
    user_cart = CART_DB.setdefault(owner_id, {})
    
    if payload.sku_id in user_cart:
        user_cart[payload.sku_id] += payload.quantity
    else:
        user_cart[payload.sku_id] = payload.quantity
        
    return _build_cart_response(owner_id, x_simulate_b2b_outage)


@app.put("/api/v1/cart/items/{sku_id}", response_model=CartResponse)
@app.put("/cart/items/{sku_id}", response_model=CartResponse)
@app.patch("/api/v1/cart/items/{sku_id}", response_model=CartResponse)
@app.patch("/cart/items/{sku_id}", response_model=CartResponse)
def update_cart_item(
    sku_id: str,
    payload: CartItemUpdateRequest,
    authorization: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    session_id: Optional[str] = Query(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    owner_id = get_cart_owner_id(authorization, x_session_id, session_id)
    
    user_cart = CART_DB.get(owner_id, {})
    if sku_id not in user_cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ITEM_NOT_FOUND", "message": f"SKU with ID '{sku_id}' not found in cart"}
        )
        
    user_cart[sku_id] = payload.quantity
    return _build_cart_response(owner_id, x_simulate_b2b_outage)


@app.delete("/api/v1/cart/items/{sku_id}")
@app.delete("/cart/items/{sku_id}")
def delete_cart_item(
    sku_id: str,
    authorization: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    session_id: Optional[str] = Query(None)
):
    owner_id = get_cart_owner_id(authorization, x_session_id, session_id)
    
    user_cart = CART_DB.get(owner_id, {})
    if sku_id in user_cart:
        del user_cart[sku_id]
        
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/v1/cart/merge", response_model=CartResponse)
@app.post("/cart/merge", response_model=CartResponse)
def merge_cart(
    payload: Optional[CartMergeRequest] = None,
    authorization: Optional[str] = Header(None),
    x_session_id: str = Header(..., alias="X-Session-Id"),
    session_id: Optional[str] = Query(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    curr_user_id = str(get_user_id_from_auth(authorization))
    
    source_session_id = None
    if payload and payload.session_id:
        source_session_id = payload.session_id
    elif x_session_id:
        source_session_id = x_session_id
    elif session_id:
        source_session_id = session_id
        
    if not source_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "session_id is required for merge"}
        )
        
    guest_cart = CART_DB.get(source_session_id, {})
    user_cart = CART_DB.setdefault(curr_user_id, {})
    
    for s_id, q_qty in guest_cart.items():
        if s_id in user_cart:
            user_cart[s_id] = max(user_cart[s_id], q_qty)
        else:
            user_cart[s_id] = q_qty
            
    if source_session_id in CART_DB:
        del CART_DB[source_session_id]
        
    return _build_cart_response(curr_user_id, x_simulate_b2b_outage)


# --- US-CART-04: Banners & CTR Analytics ---
from datetime import datetime, timezone

BANNERS_DB: List[Dict[str, Any]] = [
    {
        "id": UUID("ba123456-1111-4444-8888-000000000001"),
        "title": "🔥 Эксклюзивные скидки на IT-каналы! Сэкономьте до 15% на этой неделе.",
        "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200&auto=format&fit=crop&q=80",
        "link_url": "/catalog/it-tech",
        "priority": 50,
        "is_active": True,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    },
    {
        "id": UUID("ba123456-2222-4444-8888-000000000002"),
        "title": "🐳 Crypto Whale VIP: получите передачу прав и 7 дней обучения бесплатно!",
        "image_url": "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=1200&auto=format&fit=crop&q=80",
        "link_url": "/catalog/products/770e8400-e29b-41d4-a716-446655440001",
        "priority": 100,
        "is_active": True,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    },
    {
        "id": UUID("ba123456-3333-4444-8888-000000000003"),
        "title": "📚 Скидка на образовательные каналы! Учите языки просто",
        "image_url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1200&auto=format&fit=crop&q=80",
        "link_url": "/catalog/languages",
        "priority": 20,
        "is_active": True,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    },
    {
        "id": UUID("ba123456-4444-4444-8888-000000000004"),
        "title": "Черный список (неактивный баннер)",
        "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200",
        "link_url": "/",
        "priority": 150,
        "is_active": False,
        "start_at": "2026-06-01T00:00:00Z",
        "end_at": "2026-06-30T23:59:59Z",
    },
    {
        "id": UUID("ba123456-5555-4444-8888-000000000005"),
        "title": "Будущая акция (не началась)",
        "image_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200",
        "link_url": "/",
        "priority": 200,
        "is_active": True,
        "start_at": "2026-07-01T00:00:00Z",
        "end_at": "2026-07-31T23:59:59Z",
    }
]

BANNER_EVENTS_LOG: List[Dict[str, Any]] = []

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        cleaned = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def is_banner_active(banner: dict, now: datetime) -> bool:
    if not banner.get("is_active", True):
        return False
    start_dt = parse_iso_datetime(banner.get("start_at"))
    end_dt = parse_iso_datetime(banner.get("end_at"))
    
    if start_dt and now < start_dt:
        return False
    if end_dt and now > end_dt:
        return False
    return True

@app.get("/api/v1/catalog/banners", response_model=List[BannerResponse])
@app.get("/catalog/banners", response_model=List[BannerResponse])
@app.get("/api/v1/home/banners", response_model=List[BannerResponse])
@app.get("/home/banners", response_model=List[BannerResponse])
def get_banners():
    now = datetime.now(timezone.utc)
    active_banners = [b for b in BANNERS_DB if is_banner_active(b, now)]
    active_banners.sort(key=lambda b: b["priority"])
    
    enriched = []
    for b in active_banners:
        item = dict(b)
        item["link"] = b.get("link_url", "")
        item["ordering"] = b.get("priority", 0)
        item["active_from"] = b.get("start_at")
        item["active_to"] = b.get("end_at")
        enriched.append(item)
    return enriched

@app.post("/api/v1/banner-events", status_code=status.HTTP_201_CREATED)
@app.post("/banner-events", status_code=status.HTTP_201_CREATED)
def post_banner_event(payload: BannerEventRequest):
    banner_exists = any(b["id"] == payload.banner_id for b in BANNERS_DB)
    if not banner_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "BANNER_NOT_FOUND", "message": f"Banner with ID '{payload.banner_id}' not found"}
        )
    
    event_log = {
        "banner_id": payload.banner_id,
        "event_type": payload.event_type.upper(),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    BANNER_EVENTS_LOG.append(event_log)
    return {"status": "ok", "message": "Event logged successfully"}


@app.get("/api/v1/catalog/collections", response_model=List[Collection])
@app.get("/catalog/collections", response_model=List[Collection])
def get_collections():
    # Return all collections in database with products as an empty list (metadata without products)
    result = []
    for cid, col in COLLECTIONS_DB.items():
        result.append(Collection(
            id=col["id"],
            name=col["name"],
            description=col.get("description"),
            products=[]
        ))
    return result


@app.get("/api/v1/catalog/collections/{collection_id}", response_model=CollectionDetailResponse)
@app.get("/catalog/collections/{collection_id}", response_model=CollectionDetailResponse)
def get_collection_detail(
    collection_id: UUID,
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    # Simulate B2B outage if header is sent
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": "B2B Service Unavailable"}
        )

    col = COLLECTIONS_DB.get(collection_id)
    if not col:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Collection not found"}
        )

    try:
        b2b_products = b2b_client._products
        b2b_categories = b2b_client._categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "B2B_UNAVAILABLE", "message": str(e)}
        )

    items = []
    unavailable_ids = []

    product_ids_set = col["product_ids"]

    for pid in product_ids_set:
        # Find product in B2B
        p = next((prod for prod in b2b_products if prod["id"] == pid), None)
        
        # Determine availability: exists AND is visible (status MODERATED, not deleted, active_quantity > 0)
        is_available = False
        if p:
            if p.get("status") == "MODERATED" and not p.get("deleted", False) and p.get("active_quantity", 0) > 0:
                is_available = True

        if is_available:
            cat_ref = next((c for c in b2b_categories if c["id"] == p["category_id"]), None)
            cat_path = get_breadcrumbs_for_category(b2b_categories, cat_ref["id"]) if cat_ref else []

            items.append({
                "id": p["id"],
                "name": p["title"],
                "slug": p["slug"],
                "category": {
                    "id": cat_ref["id"],
                    "name": cat_ref["name"],
                    "level": len(cat_path) - 1,
                    "path": [t["name"] for t in cat_path]
                } if cat_ref else None,
                "min_price": p["price"],
                "old_price": p.get("old_price"),
                "has_stock": p.get("active_quantity", 0) > 0,
                "rating": p.get("rating"),
                "reviews_count": p.get("reviews_count", 0),
                "subscribers": p["subscribers"],
                "monthly_income": p["monthly_income"],
                "er": p["er"],
                "verified": p["verified"],
                "images": p.get("images", []),
                "seller": p.get("seller")
            })
        else:
            unavailable_ids.append(pid)

    return {
        "id": col["id"],
        "name": col["name"],
        "description": col.get("description"),
        "items": items,
        "unavailable_ids": unavailable_ids
    }


# --- US-ORD-01: Order management (checkout) ---

@app.post("/api/v1/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    authorization: Optional[str] = Header(None),
    idempotency_key_header: Optional[str] = Header(None, alias="Idempotency-Key"),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    import uuid
    import datetime

    # 1. Authorization
    user_id = get_user_id_from_auth(authorization)

    # 2. Extract idempotency key
    idempotency_key = None
    if idempotency_key_header:
        try:
            idempotency_key = UUID(idempotency_key_header)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key header is not a valid UUID"}
            )
    elif payload.idempotency_key:
        idempotency_key = payload.idempotency_key

    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Idempotency-Key is required"}
        )

    # 3. Check existing order
    for o in ORDERS_DB.values():
        if o.get("idempotency_key") == idempotency_key:
            return o

    # 4. Resolve items
    items = payload.items
    if not items:
        # Fallback to fetching from Cart
        cart_id_str = str(user_id)
        cart_items_dict = CART_DB.get(cart_id_str, {})
        items = []
        for sku_id_str, qty in cart_items_dict.items():
            items.append(OrderItemRequest(sku_id=UUID(sku_id_str), quantity=qty))

    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Список items не может быть пустым"}
        )

    # Check for invalid quantity
    for item in items:
        if item.quantity < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_QUANTITY", "message": "Количество должно быть не менее 1 для каждой позиции"}
            )

    # 5. Check B2B Outage
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "B2B_UNAVAILABLE", "message": "Сервис товаров временно недоступен, попробуйте позже"}
        )

    # 6. Check B2B Availability
    failed_items = []
    for item in items:
        sku_data, p = find_sku_and_product_in_b2b(b2b_client._products, item.sku_id)
        if not sku_data:
            failed_items.append({
                "sku_id": str(item.sku_id),
                "reason": "SKU_NOT_FOUND"
            })
        elif p.get("status") in ["BLOCKED", "HARD_BLOCKED"] or p.get("status") != "MODERATED":
            failed_items.append({
                "sku_id": str(item.sku_id),
                "reason": "PRODUCT_BLOCKED"
            })
        elif p.get("deleted", False):
            failed_items.append({
                "sku_id": str(item.sku_id),
                "reason": "PRODUCT_DELETED"
            })
        else:
            avail = sku_data.get("available_quantity", 0)
            if avail == 0:
                failed_items.append({
                    "sku_id": str(item.sku_id),
                    "reason": "OUT_OF_STOCK",
                    "requested": item.quantity,
                    "available": 0
                })
            elif avail < item.quantity:
                failed_items.append({
                    "sku_id": str(item.sku_id),
                    "reason": "INSUFFICIENT_STOCK",
                    "requested": item.quantity,
                    "available": avail
                })

    if failed_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "RESERVE_FAILED",
                "message": "Не удалось зарезервировать товары",
                "failed_items": failed_items
            }
        )

    # 7. Reserve SKU in B2B (decrease stock)
    for item in items:
        found = False
        for p in b2b_client._products:
            for s in p.get("skus", []):
                if s.get("id") == item.sku_id:
                    s["available_quantity"] -= item.quantity
                    found = True
                    break
            if found:
                break
        if not found:
            for p in b2b_client._products:
                if p.get("id") == item.sku_id:
                    p["active_quantity"] = max(0, p.get("active_quantity", 0) - item.quantity)
                    break

    # 8. Create Order in DB
    order_id = uuid.uuid4()
    order_items = []
    total_amount = 0

    for item in items:
        sku_data, p = find_sku_and_product_in_b2b(b2b_client._products, item.sku_id)
        unit_price = sku_data["price"]
        line_total = unit_price * item.quantity
        total_amount += line_total
        order_items.append({
            "id": uuid.uuid4(),
            "sku_id": item.sku_id,
            "product_id": p["id"],
            "product_title": p["title"],
            "sku_name": sku_data["name"],
            "name": f"{p['title']} - {sku_data['name']}",
            "sku_code": sku_data["sku_code"],
            "quantity": item.quantity,
            "unit_price": unit_price,
            "line_total": line_total,
            "image_url": sku_data["images"][0]["url"] if sku_data["images"] else (p["images"][0]["url"] if p["images"] else None)
        })

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    order_data = {
        "id": order_id,
        "number": f"NM-2026-{str(uuid.uuid4().fields[0])[:6]}",
        "buyer_id": user_id,
        "user_id": user_id,
        "status": "PAID",
        "status_history": [
            {"status": "PAID", "changed_at": now_iso, "reason": "Initial checkout"}
        ],
        "items": order_items,
        "subtotal": total_amount,
        "total": total_amount,
        "delivery_cost": 0,
        "delivery_address": payload.delivery_address or "г. Екатеринбург, ул. Мира 19, кв. 42",
        "address": {
            "id": uuid.uuid4(),
            "country": "Россия",
            "city": "Екатеринбург",
            "street": "Мира",
            "building": "19",
            "apartment": "42",
            "created_at": now_iso
        },
        "comment": payload.comment,
        "idempotency_key": idempotency_key,
        "created_at": now_iso,
        "updated_at": now_iso,
        "paid_at": now_iso
    }

    ORDERS_DB[order_id] = order_data

    # Clear user's cart in CART_DB (B2C)
    cart_id_str = str(user_id)
    if cart_id_str in CART_DB:
         del CART_DB[cart_id_str]

    return order_data


@app.get("/api/v1/orders", response_model=PaginatedOrders)
@app.get("/orders", response_model=PaginatedOrders)
def list_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    authorization: Optional[str] = Header(None)
):
    user_id = get_user_id_from_auth(authorization)

    # Filter by user_id
    user_orders = [o for o in ORDERS_DB.values() if o.get("buyer_id") == user_id]

    # Filter by status
    if status:
        user_orders = [o for o in user_orders if o.get("status") == status]

    # Sort by created_at descending (latest first)
    user_orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)

    total_count = len(user_orders)
    paginated = user_orders[offset : offset + limit]

    result = []
    for o in paginated:
        order_copy = dict(o)
        order_copy["items_count"] = sum(item["quantity"] for item in o["items"])
        result.append(order_copy)

    return {
        "items": result,
        "total_count": total_count,
        "limit": limit,
        "offset": offset
    }


@app.get("/api/v1/orders/{order_id}", response_model=OrderResponse)
@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: UUID,
    authorization: Optional[str] = Header(None)
):
    user_id = get_user_id_from_auth(authorization)

    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
        )

    # Ownership check: MUST return 404 (not 403) to prevent IDOR scanning
    if order.get("buyer_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
        )

    return order


@app.post("/api/v1/orders/{order_id}/cancel", response_model=OrderResponse)
@app.post("/orders/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: UUID,
    payload: Optional[OrderCancelRequest] = None,
    authorization: Optional[str] = Header(None),
    x_simulate_b2b_outage: Optional[str] = Header(None, alias="X-Simulate-B2B-Outage")
):
    import datetime
    user_id = get_user_id_from_auth(authorization)

    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
        )

    # Ownership: return 404 to hide other orders
    if order.get("buyer_id") != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
        )

    # Status validation: cancel allowed only in CREATED or PAID
    if order.get("status") not in ["CREATED", "PAID"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CANCEL_NOT_ALLOWED",
                "message": f"Отмена невозможна: заказ в статусе {order.get('status')}",
                "current_status": order.get("status")
            }
        )

    reason_str = payload.reason if (payload and payload.reason) else None

    # If B2B is unavailable, transition to CANCEL_PENDING
    if x_simulate_b2b_outage == "true" or b2b_client.simulate_outage:
        now_iso = datetime.datetime.utcnow().isoformat() + "Z"
        order["status"] = "CANCEL_PENDING"
        order["updated_at"] = now_iso
        if "status_history" not in order:
            order["status_history"] = []
        reason_msg = reason_str if reason_str else "B2B service unavailable"
        order["status_history"].append({"status": "CANCEL_PENDING", "changed_at": now_iso, "reason": reason_msg})
        order["cancel_reason"] = reason_str
        return order

    # Unreserve SKU in B2B (add stock back)
    for item in order["items"]:
        found = False
        for p in b2b_client._products:
            for s in p.get("skus", []):
                if s.get("id") == item["sku_id"]:
                    s["available_quantity"] += item["quantity"]
                    found = True
                    break
            if found:
                break
        if not found:
            for p in b2b_client._products:
                if p.get("id") == item["sku_id"]:
                    p["active_quantity"] = p.get("active_quantity", 0) + item["quantity"]
                    break

    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    order["status"] = "CANCELLED"
    order["updated_at"] = now_iso
    if "status_history" not in order:
        order["status_history"] = []
    reason_msg = reason_str if reason_str else "Order cancelled by client"
    order["status_history"].append({"status": "CANCELLED", "changed_at": now_iso, "reason": reason_msg})
    order["cancel_reason"] = reason_str
    return order


def change_order_status(order_id: UUID, new_status: str) -> Dict[str, Any]:
    import datetime
    order = ORDERS_DB.get(order_id)
    if not order:
        return {}
    
    order["status"] = new_status
    now_iso = datetime.datetime.utcnow().isoformat() + "Z"
    order["updated_at"] = now_iso
    if "status_history" not in order:
        order["status_history"] = []
    order["status_history"].append({"status": new_status, "changed_at": now_iso, "reason": f"Status changed to {new_status}"})
    if new_status == "DELIVERED":
        order["delivered_at"] = now_iso
        # Trigger fulfill to B2B
        items_payload = [{"sku_id": str(item["sku_id"]), "quantity": item["quantity"]} for item in order["items"]]
        try:
            b2b_client.fulfill(str(order_id), items_payload, {"X-Service-Key": b2b_client.service_key})
        except Exception as e:
            PENDING_FULFILLS.append((order_id, items_payload))
            print(f"B2B Fulfill failed, enqueued to PENDING_FULFILLS: {e}")
            
    return order


@app.post("/api/v1/orders/{order_id}/status", response_model=OrderResponse)
@app.patch("/api/v1/orders/{order_id}/status", response_model=OrderResponse)
@app.post("/orders/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdateRequest,
    authorization: Optional[str] = Header(None)
):
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
        )

    # Allow custom JWT user/operator or simulate transition
    updated = change_order_status(order_id, payload.status)
    return updated


@app.post("/api/v1/orders/retry-fulfills")
@app.post("/orders/retry-fulfills")
def trigger_retry_pending_fulfills():
    still_pending = []
    for ord_id, items in PENDING_FULFILLS:
        try:
            b2b_client.fulfill(str(ord_id), items, {"X-Service-Key": b2b_client.service_key})
        except Exception:
            still_pending.append((ord_id, items))
    PENDING_FULFILLS.clear()
    PENDING_FULFILLS.extend(still_pending)
    return {"pending_count": len(PENDING_FULFILLS)}


@app.post("/api/v1/events/product")
@app.post("/api/v1/b2b/events")
async def handle_b2b_product_event(
    request: Request,
    x_service_key: Optional[str] = Header(None, alias="X-Service-Key")
):
    if not x_service_key or x_service_key != "B2B_SECRET_KEY_PROD_2026":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or missing X-Service-Key"}
        )

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_REQUEST", "message": "Invalid JSON body"}
        )

    idempotency_key = body.get("idempotency_key")
    if idempotency_key:
        id_str = str(idempotency_key)
        if id_str in PROCESSED_B2B_EVENTS_KEYS:
            return {"accepted": True}
        PROCESSED_B2B_EVENTS_KEYS.add(id_str)

    event_type = body.get("event") or body.get("event_type")
    product_id = body.get("product_id")
    sku_ids = body.get("sku_ids")

    # Check nested payload in case of OpenAPI format
    payload_dict = body.get("payload")
    if isinstance(payload_dict, dict):
        if not product_id:
            product_id = payload_dict.get("product_id") or payload_dict.get("id")
        if not sku_ids:
            sku_id = payload_dict.get("sku_id")
            if sku_id:
                sku_ids = [sku_id]
            else:
                sku_ids = payload_dict.get("sku_ids")

    resolved_sku_ids = []
    if sku_ids:
        resolved_sku_ids = [str(sid) for sid in sku_ids]
    elif product_id:
        p_id_str = str(product_id).lower()
        b2b_products = b2b_client._products
        prod = next((p for p in b2b_products if str(p.get("id")).lower() == p_id_str), None)
        if prod:
            raw_skus = prod.get("skus", [])
            if raw_skus:
                resolved_sku_ids = [str(s.get("id")) for s in raw_skus]
            else:
                resolved_sku_ids = [p_id_str]  # fallback sku matches product_id

    reason_map = {
        "PRODUCT_BLOCKED": "PRODUCT_BLOCKED",
        "PRODUCT_HARD_BLOCKED": "PRODUCT_BLOCKED",
        "PRODUCT_DELETED": "PRODUCT_DELETED",
        "SKU_OUT_OF_STOCK": "OUT_OF_STOCK"
    }

    reason = reason_map.get(event_type, "UNAVAILABLE")

    for sid in resolved_sku_ids:
        try:
            B2B_EVENTS_UNAVAILABLE_REASONS[UUID(sid)] = reason
        except Exception:
            pass

    return {"accepted": True}