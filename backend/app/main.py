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
    CategoryTreeResponse, FlatCategoriesResponse,
    FavoriteResponse, FavoritesResponse
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

@app.get("/api/v1/catalog/products/{id}", response_model=CatalogProductDetail)
@app.get("/api/v1/products/{id}", response_model=CatalogProductDetail)
def get_product_detail(
    id: UUID,
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

    p = next((prod for prod in raw_products if prod["id"] == id), None)
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
            "id": f"sku-std-{p['id']}",
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


@app.get("/api/v1/catalog/products/{id}/similar", response_model=List[CatalogProductCard])
@app.get("/api/v1/products/{id}/similar", response_model=List[CatalogProductCard])
def get_similar_products(
    id: UUID,
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

    p = next((prod for prod in raw_products if prod["id"] == id), None)
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
        if prod["id"] == id:
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


@app.get("/api/v1/catalog/categories/tree", response_model=CategoryTreeResponse)
@app.get("/api/v1/categories/tree", response_model=CategoryTreeResponse)
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
    return {"items": tree}


@app.get("/api/v1/catalog/categories", response_model=FlatCategoriesResponse)
@app.get("/api/v1/categories", response_model=FlatCategoriesResponse)
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
    return {"items": refs}


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


@app.post("/api/v1/favorites/{product_id}", response_model=FavoriteResponse)
@app.put("/api/v1/favorites/{product_id}", response_model=FavoriteResponse)
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


@app.get("/api/v1/favorites", response_model=FavoritesResponse)
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
                    "id": f"sku-std-{p['id']}",
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

