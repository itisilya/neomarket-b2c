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
    id: str
    name: str
    sku_code: str
    price: int
    old_price: Optional[int] = None
    discount: int = 0
    available_quantity: int = Field(ge=0)
    attributes: Dict[str, Any] = {}
    images: List[ImageRef]

class CatalogProductCard(BaseModel):
    id: UUID
    name: str
    slug: str
    category: Optional[CategoryRef] = None
    min_price: int # Minimum price among available SKUs
    old_price: Optional[int] = None
    has_stock: bool
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    reviews_count: int = Field(default=0, ge=0)
    subscribers: int
    monthly_income: int
    er: float
    verified: bool
    images: List[ImageRef]
    seller: Optional[Dict[str, Any]] = None

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
