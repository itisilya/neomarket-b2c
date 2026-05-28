export interface CategoryRef {
  id: string;
  name: string;
  parent_id?: string | null;
  level: number;
  path: string[];
}

export interface CategoryTreeNode extends CategoryRef {
  children?: CategoryTreeNode[];
}

export interface ImageRef {
  id: string;
  url: string;
  alt?: string;
  ordering: number;
  is_main?: boolean;
}

export interface CatalogProductCard {
  id: string;
  name: string;
  slug: string;
  category: CategoryRef | null;
  min_price: number; // in kopecks
  old_price: number | null; // in kopecks
  has_stock: boolean;
  rating: number;
  reviews_count: number;
  subscribers: number;
  monthly_income: number;
  er: number;
  verified: boolean;
  images: ImageRef[];
  seller?: {
    id: string;
    display_name: string;
  };
}

export interface CatalogSku {
  id: string;
  name: string;
  sku_code: string;
  price: number; // kopecks
  old_price: number | null; // kopecks
  available_quantity: number;
  attributes: Record<string, any>;
  images: ImageRef[];
}

export interface CatalogProductDetail extends CatalogProductCard {
  description: string;
  attributes: Record<string, any>;
  characteristics: Array<{ name: string; value: string }>;
  skus: CatalogSku[];
}

export interface FacetItem {
  value: string; // User-facing name
  text_value: string; // filter value (e.g. id or true/false)
  count: number;
}

export interface FacetGroup {
  name: string; // e.g. "category", "verified"
  values: FacetItem[];
}

export interface FacetsResponse {
  category_id: string | null;
  facets: FacetGroup[];
}

export interface BreadcrumbItem {
  id: string;
  slug: string;
  name: string;
  url: string;
  level: number;
  is_current: boolean;
}

export interface DevApiLog {
  id: string;
  method: string;
  path: string;
  status: number;
  duration: string;
  timestamp: string;
}
