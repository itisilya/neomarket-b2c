from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class CategoryRef(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    level: int
    path: List[str]

    class Config:
        from_attributes = True

class CategoryTreeNode(CategoryRef):
    children: List['CategoryTreeNode'] = []

# Resolve self-referential Pydantic structures for category trees
CategoryTreeNode.model_rebuild()

class ImageRef(BaseModel):
    id: str
    url: str
    alt: Optional[str] = None
    ordering: int = Field(ge=0)
    is_main: Optional[bool] = False

class CatalogSku(BaseModel):
    id: UUID
    name: str
    sku_code: str
    price: int # Price in kopecks
    old_price: Optional[int] = None # Price in kopecks
    discount: int = 0
    available_quantity: int = Field(ge=0)
    attributes: Dict[str, Any] = {}
    images: List[ImageRef]

class CatalogProductCard(BaseModel):
    id: UUID
    name: str
    slug: str
    category: Optional[CategoryRef] = None
    min_price: int # Minimum price among available SKUs in kopecks
    old_price: Optional[int] = None # in kopecks
    has_stock: bool
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    reviews_count: int = Field(default=0, ge=0)
    subscribers: int
    monthly_income: int
    er: float
    verified: bool
    images: List[ImageRef]
    seller: Optional[Dict[str, Any]] = None
    skus: Optional[List[CatalogSku]] = None
    added_at: Optional[str] = None

class CatalogProductDetail(CatalogProductCard):
    description: str
    attributes: Dict[str, Any] = {}
    characteristics: List[Dict[str, str]] = []
    skus: List[CatalogSku]

class PaginatedCatalogProducts(BaseModel):
    items: List[CatalogProductCard]
    total_count: int
    limit: int
    offset: int

class FacetItem(BaseModel):
    value: str
    text_value: str
    count: int

class FacetGroup(BaseModel):
    name: str
    values: List[FacetItem]

class FacetsResponse(BaseModel):
    category_id: Optional[UUID] = None
    facets: List[FacetGroup]

class BreadcrumbItem(BaseModel):
    id: UUID
    slug: str
    name: str
    url: str
    level: int
    is_current: bool

class BreadcrumbsResponse(BaseModel):
    data: List[BreadcrumbItem]
    meta: Dict[str, Any]

class CategoryDetailParent(BaseModel):
    id: UUID
    name: str
    slug: str

class CategoryDetailSeo(BaseModel):
    title: str
    description: str
    keywords: List[str]

class CategoryDetailResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    parent: Optional[CategoryDetailParent] = None
    product_count: int
    seo: CategoryDetailSeo
    is_active: bool
    created_at: str

class FlatCategoryItem(BaseModel):
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    level: int
    path: List[str]


class FavoriteResponse(BaseModel):
    product_id: UUID
    user_id: UUID
    added_at: str


class FavoriteItem(BaseModel):
    id: UUID
    name: str
    slug: str
    category: Optional[CategoryRef] = None
    min_price: int
    old_price: Optional[int] = None
    has_stock: bool
    rating: Optional[float] = None
    reviews_count: int = 0
    subscribers: int
    monthly_income: int
    er: float
    verified: bool
    images: List[ImageRef]
    seller: Optional[Dict[str, Any]] = None
    skus: List[CatalogSku] = []
    added_at: str


class FavoritesResponse(BaseModel):
    items: List[FavoriteItem]
    total_count: int
    limit: int
    offset: int


class SubscriptionRequest(BaseModel):
    events: Optional[List[str]] = Field(default=["BACK_IN_STOCK", "PRICE_DROP"])
    notify_on: Optional[List[str]] = None


class SubscriptionResponse(BaseModel):
    id: UUID
    product_id: UUID
    user_id: UUID
    notify_on: List[str]
    events: Optional[List[str]] = None
    created_at: str


class SubscriptionsListResponse(BaseModel):
    items: List[SubscriptionResponse]


class CartItemAddRequest(BaseModel):
    sku_id: UUID
    quantity: int = Field(default=1, ge=1)


class CartItemUpdateRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    sku_id: UUID
    product_id: UUID
    name: str
    sku_code: Optional[str] = None
    quantity: int
    unit_price: int
    unit_price_at_add: Optional[int] = None
    line_total: int
    available_quantity: int
    is_available: bool
    image: Optional[ImageRef] = None
    
    # UI compatibility
    sku: Optional[CatalogSku] = None
    product: Optional[CatalogProductCard] = None
    unavailable_reason: Optional[str] = None
    price_at_addition: Optional[int] = None
    subtotal: int = 0


class CartResponse(BaseModel):
    id: str  # ID корзины (owner_id)
    items: List[CartItemResponse]
    items_count: int  # Сумма всех quantity
    subtotal: int     # Общая сумма всех line_total
    is_valid: bool
    updated_at: str
    
    # UI compatibility
    total_amount: int


class CartMergeRequest(BaseModel):
    session_id: str


class BannerResponse(BaseModel):
    id: UUID
    title: str
    image_url: str
    link: str
    ordering: int
    active_from: str
    active_to: str
    
    # UI compatibility
    link_url: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None


class BannerEventRequest(BaseModel):
    banner_id: UUID
    event_type: str

