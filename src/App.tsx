import React, { useState, useEffect } from "react";
import { CatalogProductCard, CatalogProductDetail, CategoryRef, CatalogSku, FacetsResponse, BreadcrumbItem, FavoriteItem, FavoritesResponse, CartResponse, CartItemResponse } from "./types";
import { SidebarFilters } from "./components/SidebarFilters";
import { ChannelCard } from "./components/ChannelCard";
import { ChannelDetailModal } from "./components/ChannelDetailModal";
import { DevLogDashboard } from "./components/DevLogDashboard";
import { PythonCodeViewer } from "./components/PythonCodeViewer";
import { 
  Users, 
  Search, 
  ShoppingCart, 
  Heart, 
  Flame, 
  Clock, 
  Check, 
  BookOpen, 
  Sparkles, 
  HelpCircle,
  TrendingUp,
  SlidersHorizontal,
  ChevronRight,
  X
} from "lucide-react";

const STATIC_CATEGORIES: CategoryRef[] = [
  { id: "e1010000-e29b-41d4-a716-446655440001", name: "Электроника (Каналы)", parent_id: null, level: 0, path: ["Электроника (Каналы)"] },
  { id: "e1010000-e29b-41d4-a716-446655440002", name: "Технологии & IT", parent_id: null, level: 0, path: ["Технологии & IT"] },
  { id: "e1010000-e29b-41d4-a716-446655440003", name: "Искусственный интеллект", parent_id: "e1010000-e29b-41d4-a716-446655440002", level: 1, path: ["Технологии & IT", "Искусственный интеллект"] },
  { id: "e1010000-e29b-41d4-a716-446655440004", name: "Разработка ПО", parent_id: "e1010000-e29b-41d4-a716-446655440002", level: 1, path: ["Технологии & IT", "Разработка ПО"] },
  { id: "e1010000-e29b-41d4-a716-446655440005", name: "Бизнес & Финансы", parent_id: null, level: 0, path: ["Бизнес & Финансы"] },
  { id: "e1010000-e29b-41d4-a716-446655440006", name: "Криптовалюты", parent_id: "e1010000-e29b-41d4-a716-446655440005", level: 1, path: ["Бизнес & Финансы", "Криптовалюты"] },
  { id: "e1010000-e29b-41d4-a716-446655440007", name: "Развлечения & Юмор", parent_id: null, level: 0, path: ["Развлечения & Юмор"] },
  { id: "e1010000-e29b-41d4-a716-446655440008", name: "Мемы", parent_id: "e1010000-e29b-41d4-a716-446655440007", level: 1, path: ["Развлечения & Юмор", "Мемы"] },
  { id: "e1010000-e29b-41d4-a716-446655440009", name: "Образование & Наука", parent_id: null, level: 0, path: ["Образование & Наука"] },
  { id: "e1010000-e29b-41d4-a716-446655440010", name: "Иностранные языки", parent_id: "e1010000-e29b-41d4-a716-446655440009", level: 1, path: ["Образование & Наука", "Иностранные языки"] }
];

export default function App() {
  // Filters & Search states
  const [categories, setCategories] = useState<CategoryRef[]>(STATIC_CATEGORIES);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sortOption, setSortOption] = useState("popularity");

  // Loaded Catalog states
  const [products, setProducts] = useState<CatalogProductCard[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([]);
  
  // App system states
  const [loading, setLoading] = useState(true);
  const [searchError, setSearchError] = useState("");
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [activeChannelDetail, setActiveChannelDetail] = useState<CatalogProductDetail | null>(null);

  // Real B2C Cart Integration states
  const [cart, setCart] = useState<CartResponse>({ items: [], total_amount: 0 });
  const [isCartOpen, setIsCartOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"authorized" | "guest">("authorized");
  const [sessionId, setSessionId] = useState<string>("");
  
  // US-CART-04: Banners & CTR Analytics state
  const [banners, setBanners] = useState<any[]>([]);
  const [activeBannerIndex, setActiveBannerIndex] = useState(0);
  
  // Real B2C Favorites Database Integration
  const MOCK_JWT = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMTExMTExMS1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDEifQ.mock-signature";
  const [activeTab, setActiveTab] = useState<"catalog" | "favorites">("catalog");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [favoriteItems, setFavoriteItems] = useState<FavoriteItem[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [checkoutFinished, setCheckoutFinished] = useState(false);
  const [subscriptions, setSubscriptions] = useState<string[]>([]);

  const handleToggleSubscription = async (productId: string) => {
    const isSub = subscriptions.includes(productId);
    try {
      if (isSub) {
        // Remove subscription -> DELETE /api/v1/favorites/{productId}/subscribe
        const res = await fetch(`/api/v1/favorites/${productId}/subscribe`, {
          method: "DELETE",
          headers: {
            "Authorization": MOCK_JWT
          }
        });
        if (res.ok || res.status === 204) {
          setSubscriptions(prev => prev.filter(id => id !== productId));
        }
      } else {
        // Add subscription -> POST /api/v1/favorites/{productId}/subscribe
        const res = await fetch(`/api/v1/favorites/${productId}/subscribe`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": MOCK_JWT
          },
          body: JSON.stringify({
            notify_on: ["PRICE_DROP", "BACK_IN_STOCK"]
          })
        });
        if (res.ok || res.status === 201) {
          setSubscriptions(prev => [...prev, productId]);
        }
      }
    } catch (err) {
      console.error("Failed in subscription transaction request:", err);
    }
  };

  const loadFavorites = async () => {
    setFavoritesLoading(true);
    try {
      const res = await fetch("/api/v1/favorites", {
        headers: {
          "Authorization": MOCK_JWT
        }
      });
      if (res.ok) {
        const data: FavoritesResponse = await res.json();
        setFavoriteItems(data.items);
        setFavorites(data.items.map(item => item.id));
      }
    } catch (err) {
      console.error("Failed to load favorites from B2C database:", err);
    } finally {
      setFavoritesLoading(false);
    }
  };

  const loadSubscriptions = async () => {
    try {
      const res = await fetch("/api/v1/subscribe", {
        headers: {
          "Authorization": MOCK_JWT
        }
      });
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.items)) {
          setSubscriptions(data.items.map((item: any) => item.product_id));
        }
      }
    } catch (err) {
      console.error("Failed to load subscriptions from B2C database:", err);
    }
  };

  const loadCart = async (activeAuthMode?: "authorized" | "guest", customSessionId?: string) => {
    const resolvedAuthMode = activeAuthMode !== undefined ? activeAuthMode : authMode;
    const resolvedSessionId = customSessionId !== undefined ? customSessionId : sessionId;

    try {
      const headers: Record<string, string> = {};
      if (resolvedAuthMode === "authorized") {
        headers["Authorization"] = MOCK_JWT;
      } else if (resolvedSessionId) {
        headers["X-Session-Id"] = resolvedSessionId;
      }

      const res = await fetch("/api/v1/cart", { headers });
      if (res.ok) {
        const data: CartResponse = await res.json();
        setCart(data);
      }
    } catch (err) {
      console.error("Failed to load B2C Cart:", err);
    }
  };

  const loadBanners = async () => {
    try {
      const res = await fetch("/api/v1/catalog/banners");
      if (res.ok) {
        const data = await res.json();
        setBanners(data);
        if (data && data.length > 0) {
          handleBannerEvent(data[0].id, "IMPRESSION");
        }
      }
    } catch (err) {
      console.error("Failed to load home banners:", err);
    }
  };

  const handleBannerEvent = async (bannerId: string, eventType: "CLICK" | "IMPRESSION") => {
    try {
      await fetch("/api/v1/banner-events", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          banner_id: bannerId,
          event_type: eventType
        })
      });
    } catch (err) {
      console.error("Failed sending banner analytical event:", err);
    }
  };

  useEffect(() => {
    let sId = localStorage.getItem("b2c_session_id");
    if (!sId) {
      sId = "guest_session_" + Math.random().toString(36).substring(2, 10);
      localStorage.setItem("b2c_session_id", sId);
    }
    setSessionId(sId);
    
    loadFavorites();
    loadSubscriptions();
    loadCart(authMode, sId);
    loadBanners();
  }, [authMode]);

  const handleToggleFavorite = async (productId: string, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
    }
    const isFav = favorites.includes(productId);
    try {
      if (isFav) {
        // Remove Favorite -> DELETE /api/v1/favorites/{productId}
        const res = await fetch(`/api/v1/favorites/${productId}`, {
          method: "DELETE",
          headers: {
            "Authorization": MOCK_JWT
          }
        });
        if (res.ok || res.status === 204) {
          setFavorites(prev => prev.filter(id => id !== productId));
          setFavoriteItems(prev => prev.filter(item => item.id !== productId));
        }
      } else {
        // Add Favorite -> POST /api/v1/favorites/{productId}
        const res = await fetch(`/api/v1/favorites/${productId}`, {
          method: "POST",
          headers: {
            "Authorization": MOCK_JWT
          }
        });
        if (res.ok || res.status === 201) {
          await loadFavorites();
        }
      }
    } catch (err) {
      console.error("Failed in favorites transaction request:", err);
    }
  };

  // Sync Products and Facets on filter updates
  useEffect(() => {
    const syncCatalogData = async () => {
      setLoading(true);
      
      // Validation check for search length (B2C-2 search specs: minimum 3 letters)
      if (searchQuery.length > 0 && searchQuery.length < 3) {
        setSearchError("Запрос должен содержать минимум 3 символа.");
        setLoading(false);
        return;
      } else {
        setSearchError("");
      }

      // Convert prices from user units (rubles) to backend api units (kopecks)
      const pMinKops = priceMin ? Number(priceMin) * 100 : "";
      const pMaxKops = priceMax ? Number(priceMax) * 100 : "";

      // Build listing & facets query params
      const queryParams = new URLSearchParams();
      if (searchQuery) queryParams.append("q", searchQuery);
      if (selectedCategoryId) queryParams.append("category_id", selectedCategoryId);
      if (pMinKops) queryParams.append("price_min", String(pMinKops));
      if (pMaxKops) queryParams.append("price_max", String(pMaxKops));
      if (verifiedOnly) queryParams.append("verified", "true");
      queryParams.append("sort", sortOption);

      try {
        // 1. Load Products (GET /api/v1/catalog/products)
        const prodRes = await fetch(`/api/v1/catalog/products?${queryParams.toString()}`);
        if (prodRes.ok) {
          const prodData = await prodRes.json();
          setProducts(prodData.items);
          setTotalCount(prodData.total_count);
        }

        // 2. Load dynamic counts facets (GET /api/v1/catalog/facets)
        const facetRes = await fetch(`/api/v1/catalog/facets?${queryParams.toString()}`);
        if (facetRes.ok) {
          const facetData = await facetRes.json();
          setFacets(facetData);
        }

        // 3. Resolve active breadcrumbs list locally from STATIC_CATEGORIES
        if (selectedCategoryId) {
          const chain: BreadcrumbItem[] = [];
          let curId: string | null = selectedCategoryId;
          while (curId) {
            const cat = STATIC_CATEGORIES.find(c => c.id === curId);
            if (!cat) break;
            chain.unshift({
              id: cat.id,
              slug: cat.name.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
              name: cat.name,
              url: "#",
              level: 0,
              is_current: false
            });
            curId = cat.parent_id || null;
          }
          chain.forEach((item, index) => {
            item.level = index;
            item.is_current = (index === chain.length - 1);
          });
          setBreadcrumbs(chain);
        } else {
          setBreadcrumbs([]);
        }

      } catch (err) {
        console.error("Failed syncing catalog data:", err);
      } finally {
        setLoading(false);
      }
    };

    syncCatalogData();
  }, [selectedCategoryId, searchQuery, priceMin, priceMax, verifiedOnly, sortOption]);

  const handleResetFilters = () => {
    setSelectedCategoryId(null);
    setSearchQuery("");
    setPriceMin("");
    setPriceMax("");
    setVerifiedOnly(false);
    setSortOption("popularity");
  };

  const handleSelectProduct = async (id: string) => {
    setSelectedProductId(id);
    const detail = await handleLoadProductDetail(id);
    if (detail) {
      setActiveChannelDetail(detail);
    }
  };

  const handleLoadProductDetail = async (id: string): Promise<CatalogProductDetail | null> => {
    try {
      const res = await fetch(`/api/v1/catalog/products/${id}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.error("Failed fetching product detail from backend, falling back:", err);
    }

    const foundCard = products.find(p => p.id === id);
    if (foundCard) {
      // Mock full details using the loaded product card representation safely
      return {
        ...foundCard,
        description: foundCard.slug === "crypto-whale-alerts" 
          ? "Раздел аналитики криптовалютных рынков и крупных транзакций. Стабильный доход со спансорских постов, высокая вовлеченность трейдеров и крипто-энтузиастов."
          : foundCard.slug === "it-career-roadmap"
          ? "Ведущий образовательный ресурс для начинающих программистов. Интегрированная CPA-сеть вакансий и курсов приносит стабильный пассивный доход."
          : "Premium-канал проверен кураторами платформы NeoMarket. Полный аудит характеристик, проверенный доход и безопасная передача через гаранта.",
        attributes: {
          "Subscribers": foundCard.subscribers,
          "ER": `${foundCard.er}%`,
          "Verified": foundCard.verified ? "Yes" : "No"
        },
        characteristics: [
          { name: "Тематика", value: foundCard.category?.name || "Медиабизнес" },
          { name: "Язык аудитории", value: "Русский" },
          { name: "Вовлеченность (ER)", value: `${foundCard.er}%` }
        ],
        skus: [
          {
            id: `sku-std-${foundCard.id}`,
            name: "Полная передача прав (Базовый)",
            sku_code: `TG-${foundCard.slug.toUpperCase()}-BASE`,
            price: foundCard.min_price,
            old_price: foundCard.old_price,
            available_quantity: 1,
            attributes: { "Помощь в транзите": "Да", "Обучение": "7 дней" },
            images: foundCard.images
          }
        ]
      };
    }
    return null;
  };

  const handleAddToCart = async (sku: CatalogSku, productName: string) => {
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json"
      };
      if (authMode === "authorized") {
        headers["Authorization"] = MOCK_JWT;
      } else if (sessionId) {
        headers["X-Session-Id"] = sessionId;
      }

      const res = await fetch("/api/v1/cart/items", {
        method: "POST",
        headers,
        body: JSON.stringify({ sku_id: sku.id, quantity: 1 })
      });
      if (res.ok) {
        const updatedCart: CartResponse = await res.json();
        setCart(updatedCart);
      } else {
        console.error("Failed to add SKU into Cart API");
      }
    } catch (err) {
      console.error("Failed adding to cart:", err);
    }
  };

  const handleRemoveFromCart = async (skuId: string) => {
    try {
      const headers: Record<string, string> = {};
      if (authMode === "authorized") {
        headers["Authorization"] = MOCK_JWT;
      } else if (sessionId) {
        headers["X-Session-Id"] = sessionId;
      }

      const res = await fetch(`/api/v1/cart/items/${skuId}`, {
        method: "DELETE",
        headers
      });
      if (res.ok || res.status === 204) {
        await loadCart(authMode, sessionId);
      }
    } catch (err) {
      console.error("Failed deleting cart item:", err);
    }
  };

  const handleUpdateQuantity = async (skuId: string, quantity: number) => {
    if (quantity < 1) {
      await handleRemoveFromCart(skuId);
      return;
    }
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json"
      };
      if (authMode === "authorized") {
        headers["Authorization"] = MOCK_JWT;
      } else if (sessionId) {
        headers["X-Session-Id"] = sessionId;
      }

      const res = await fetch(`/api/v1/cart/items/${skuId}`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ quantity })
      });
      if (res.ok) {
        const updatedCart: CartResponse = await res.json();
        setCart(updatedCart);
      }
    } catch (err) {
      console.error("Failed updating item quantity:", err);
    }
  };

  const handleMergeCart = async () => {
    try {
      const res = await fetch("/api/v1/cart/merge", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": MOCK_JWT
        },
        body: JSON.stringify({ session_id: sessionId })
      });
      if (res.ok) {
        const mergedCart: CartResponse = await res.json();
        setCart(mergedCart);
        setAuthMode("authorized");
      }
    } catch (err) {
      console.error("Failed merging guest cart into authorized:", err);
    }
  };

  const handleSimulatedCheckout = () => {
    setCheckoutFinished(true);
    setTimeout(() => {
      setCart({ items: [], total_amount: 0 });
      setCheckoutFinished(false);
      setIsCartOpen(false);
    }, 4000);
  };

  const cartTotal = cart.total_amount;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 antialiased font-sans">
      
      {/* Visual background ambient gradient splashes */}
      <div className="absolute top-0 left-0 -z-10 h-[500px] w-full bg-radial-at-t from-cyan-500/10 via-slate-950/20 to-transparent" />
      <div className="absolute top-[20%] right-[10%] -z-10 h-72 w-72 rounded-full bg-purple-500/5 blur-3xl" />

      {/* Modern Header Navigation */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/85 py-4 shadow-xl backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6">
          
          {/* Logo & Platform Name */}
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 border border-slate-800/80 text-white shadow-md shadow-cyan-500/5">
              <Sparkles className="h-5 w-5 text-cyan-400 stroke-2" />
            </div>
            <div>
              <span className="font-sans text-base font-black tracking-tight text-white uppercase">
                NeoMarket
              </span>
              <span className="block text-[10px] font-medium text-slate-400 mt-0.5">Маркетплейс Telegram каналов</span>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-1 bg-slate-900/90 border border-slate-800/80 p-1 rounded-2xl shadow-inner shadow-black/40">
            <button
              onClick={() => setActiveTab("catalog")}
              className={`flex items-center gap-1.5 px-35 py-1.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-150 ${
                activeTab === "catalog"
                  ? "bg-slate-800/95 text-white border border-slate-750 shadow-md shadow-black/50"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <BookOpen className="h-3.5 w-3.5 text-cyan-400" /> Каталог
            </button>
            <button
              onClick={() => setActiveTab("favorites")}
              className={`flex items-center gap-1.5 px-35 py-1.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-150 relative ${
                activeTab === "favorites"
                  ? "bg-slate-800/95 text-white border border-slate-750 shadow-md shadow-black/50"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Heart className={`h-3.5 w-3.5 ${activeTab === "favorites" || favorites.length > 0 ? "text-rose-500 fill-rose-500" : "text-slate-400"}`} /> Избранное
              {favorites.length > 0 && (
                <span className="flex h-4.5 min-w-[18px] items-center justify-center rounded-full bg-rose-500/20 text-rose-400 text-[9px] font-black font-mono px-1">
                  {favorites.length}
                </span>
              )}
            </button>
          </div>

          {/* Cart & Status Ribbon */}
          <div className="flex items-center gap-3">
            {/* Authenticated Mode Selector */}
            <div className="hidden sm:flex items-center bg-slate-900 border border-slate-800 rounded-xl p-0.5 text-[10px] font-mono">
              <button
                onClick={() => setAuthMode("authorized")}
                className={`px-2.5 py-1.5 rounded-lg transition-all ${
                  authMode === "authorized" 
                    ? "bg-cyan-500 text-slate-950 font-bold" 
                    : "text-slate-400 hover:text-white"
                }`}
                title="Режим авторизованного пользователя API"
              >
                🔐 Вошедший юзер
              </button>
              <button
                onClick={() => setAuthMode("guest")}
                className={`px-2.5 py-1.5 rounded-lg transition-all ${
                  authMode === "guest" 
                    ? "bg-amber-500 text-slate-950 font-bold" 
                    : "text-slate-400 hover:text-white"
                }`}
                title="Режим анонимного гостя (сессия)"
              >
                👤 Гость
              </button>
            </div>

            <button
              onClick={() => setIsCartOpen(true)}
              className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 hover:bg-slate-850 border border-slate-800 transition-colors"
            >
              <ShoppingCart className="h-4.5 w-4.5 text-slate-200" />
              {cart.items.length > 0 && (
                <span className="absolute -top-1.5 -right-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-cyan-500 text-[10px] font-black font-mono text-slate-950 animate-pulse">
                  {cart.items.length}
                </span>
              )}
            </button>
          </div>

        </div>
      </header>

      {/* App Body Wrapper */}
      <main className="mx-auto mt-8 max-w-7xl px-4 sm:px-6">

        {activeTab === "catalog" ? (
          /* Catalog Tab View */
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
              
              {/* Left Hand: Filter Columns */}
              <div className="lg:col-span-1 space-y-6">
                <SidebarFilters
                  categories={categories}
                  selectedCategoryId={selectedCategoryId}
                  onSelectCategory={setSelectedCategoryId}
                  priceMin={priceMin}
                  priceMax={priceMax}
                  setPriceMin={setPriceMin}
                  setPriceMax={setPriceMax}
                  verifiedOnly={verifiedOnly}
                  setVerifiedOnly={setVerifiedOnly}
                  facets={facets}
                  onReset={handleResetFilters}
                />
              </div>

              {/* Right Hand: Catalog Grid, Search, and Tools */}
              <div className="lg:col-span-3 space-y-6">
                
                {/* Promo Banner Slider (US-CART-04) */}
                {banners && banners.length > 0 ? (
                  <div className="relative overflow-hidden rounded-2xl bg-slate-950 h-52 md:h-60 border border-slate-800/80 shadow-2xl group transition-all duration-300">
                    {/* Background image component */}
                    <div 
                      className="absolute inset-0 bg-cover bg-center transition-all duration-700 ease-in-out scale-102 group-hover:scale-105 opacity-85" 
                      style={{ backgroundImage: `url(${banners[activeBannerIndex]?.image_url})` }}
                    />
                    
                    {/* Dark gradient overlay covering left side deeply */}
                    <div className="absolute inset-0 bg-gradient-to-r from-slate-950/95 via-slate-950/70 to-slate-950/30 md:to-transparent pointer-events-none" />
                    
                    {/* Glow effect */}
                    <div className="absolute top-0 right-0 h-full w-64 bg-radial-at-t from-cyan-500/10 via-transparent to-transparent pointer-events-none" />

                    {/* Content Layer */}
                    <div className="absolute inset-0 flex flex-col justify-between p-6 md:p-8 z-10">
                      <div>
                        {/* Super Header Tag */}
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9px] font-black uppercase tracking-wider text-cyan-400 bg-cyan-950/80 border border-cyan-850 px-2 py-0.5 rounded-md">
                            Промоакция B2C
                          </span>
                          <span className="text-[9px] font-mono text-slate-400">
                            Приоритет: {banners[activeBannerIndex]?.priority}
                          </span>
                        </div>

                        {/* Slide Title */}
                        <h2 className="mt-4 font-sans text-lg md:text-2xl font-black text-white leading-snug max-w-xl transition-all duration-300">
                          {banners[activeBannerIndex]?.title}
                        </h2>
                      </div>

                      <div className="flex items-center justify-between mt-2">
                        {/* Call to Action Button */}
                        <a
                          href={banners[activeBannerIndex]?.link_url}
                          onClick={() => handleBannerEvent(banners[activeBannerIndex]?.id, "CLICK")}
                          className="inline-flex items-center gap-1.5 px-4.5 py-1.5 rounded-xl bg-cyan-500 text-slate-950 text-xs font-black uppercase tracking-wider transition-all hover:bg-cyan-400 active:scale-95 shadow-lg shadow-cyan-500/10"
                        >
                          Перейти к акции <ChevronRight className="h-3.5 w-3.5" />
                        </a>

                        {/* Dot Navigation & Switchers */}
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              const newIndex = (activeBannerIndex - 1 + banners.length) % banners.length;
                              setActiveBannerIndex(newIndex);
                              handleBannerEvent(banners[newIndex].id, "IMPRESSION");
                            }}
                            className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900/90 border border-slate-800 text-slate-400 hover:text-white transition-all active:scale-90"
                          >
                            &larr;
                          </button>
                          
                          {/* Dots */}
                          <div className="flex gap-1">
                            {banners.map((_, idx) => (
                              <button
                                key={idx}
                                onClick={() => {
                                  if (idx !== activeBannerIndex) {
                                    setActiveBannerIndex(idx);
                                    handleBannerEvent(banners[idx].id, "IMPRESSION");
                                  }
                                }}
                                className={`h-1.5 transition-all rounded-full ${idx === activeBannerIndex ? "w-4 bg-cyan-400" : "w-1.5 bg-slate-750"}`}
                              />
                            ))}
                          </div>

                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              const newIndex = (activeBannerIndex + 1) % banners.length;
                              setActiveBannerIndex(newIndex);
                              handleBannerEvent(banners[newIndex].id, "IMPRESSION");
                            }}
                            className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-900/90 border border-slate-800 text-slate-400 hover:text-white transition-all active:scale-90"
                          >
                            &rarr;
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Header Promo Dummy Fallback Banner */
                  <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-950 to-slate-950 p-6 md:p-8 text-white border border-slate-800 shadow-xl">
                    <div className="absolute top-0 right-0 h-full w-48 bg-radial-at-t from-cyan-500/15 via-transparent to-transparent pointer-events-none" />
                    <div className="max-w-xl">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-cyan-400 bg-cyan-950/80 px-2 py-1 rounded inline-block border border-cyan-900/50">Портал Покупки Каналов</span>
                      <h1 className="mt-3.5 font-sans text-xl md:text-2xl font-black text-white leading-tight">
                        Инвестируйте в готовый медиабизнес безопасно
                      </h1>
                      <p className="mt-2 text-xs text-slate-400 leading-relaxed">
                        Все выставленные Telegram-каналы прошли полную модерацию и аудит вовлеченности (ER) нашими кураторами. Простая сделка "под ключ" через Безопасный Гарант.
                      </p>
                    </div>
                  </div>
                )}

                {/* Dynamic Search Box & Sort Selection */}
                <div className="flex flex-col gap-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-4 shadow-lg glass sm:flex-row sm:items-center sm:justify-between">
                  
                  {/* Text search form */}
                  <div className="relative flex-1 max-w-md">
                    <Search className="absolute top-3 left-3.5 h-4 w-4 text-cyan-400" />
                    <input
                      type="text"
                      value={searchQuery}
                      placeholder="Поиск по названию или описанию..."
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full rounded-xl border border-slate-800 bg-slate-950 py-2.5 pr-4 pl-10 text-xs font-semibold text-white placeholder:text-slate-500 focus:border-cyan-405 focus:bg-slate-950 focus:outline-none transition-all"
                    />
                    {searchError && (
                      <span className="absolute left-1 -bottom-5 text-[10px] font-bold text-rose-450 font-mono">
                        {searchError}
                      </span>
                    )}
                  </div>

                  {/* Sort selection drop down */}
                  <div className="flex items-center gap-3 self-baseline sm:self-auto">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Сортировать:</span>
                    <select
                      value={sortOption}
                      onChange={(e) => setSortOption(e.target.value)}
                      className="rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer"
                    >
                      <option value="popularity">Популярность (Подписчики)</option>
                      <option value="rating">Высокий рейтинг</option>
                      <option value="price_asc">Цена по возрастанию</option>
                      <option value="price_desc">Цена по убыванию</option>
                      <option value="new">Сначала новые</option>
                    </select>
                  </div>

                </div>

                {/* Category Breadcrumbs chain */}
                {breadcrumbs.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 rounded-xl bg-cyan-950/20 px-4 py-2 text-[11px] text-cyan-400 font-semibold border border-cyan-900/40">
                    <span className="text-cyan-400/80">Навигация:</span>
                    <span>Все категории</span>
                    {breadcrumbs.map((b) => (
                      <React.Fragment key={b.id}>
                        <ChevronRight className="h-3 w-3 text-cyan-500" />
                        <span className={b.is_current ? "text-white font-extrabold" : "text-cyan-400"}>
                          {b.name}
                        </span>
                      </React.Fragment>
                    ))}
                  </div>
                )}

                {/* Main Products Grid Column */}
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-20">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent" />
                    <span className="mt-4 text-xs font-semibold text-slate-450 font-mono">Запрос товаров от B2B роутера...</span>
                  </div>
                ) : products.length === 0 ? (
                  <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 py-16 px-4 text-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-900 border border-slate-800 text-slate-400">
                      <Search className="h-6 w-6" />
                    </div>
                    <h3 className="mt-4 font-sans text-sm font-bold text-white">Увы, совпадений нет</h3>
                    <p className="mt-1 text-xs text-slate-500 max-w-sm leading-normal">
                      Мы не нашли каналов под выбранные ценовые ограничения или фильтры. Попробуйте сбросить параметры.
                    </p>
                    <button
                      onClick={handleResetFilters}
                      className="mt-4 rounded-xl bg-slate-900 text-slate-300 border border-slate-800 px-4 py-2 text-xs font-bold hover:bg-slate-800 transition-colors"
                    >
                      Сбросить все фильтры
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-450 uppercase tracking-widest font-mono">
                        Найдено каналов: {totalCount}
                      </span>
                    </div>

                    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
                      {products.map((p) => (
                        <ChannelCard
                          key={p.id}
                          channel={p}
                          onClick={() => handleSelectProduct(p.id)}
                          isFavorite={favorites.includes(p.id)}
                          onToggleFavorite={handleToggleFavorite}
                        />
                      ))}
                    </div>
                  </div>
                )}

              </div>

          </div>
        ) : (
          /* Favorites Tab View */
          <div className="space-y-6">
            
            {/* Header Favorites Banner */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-950 to-slate-950 p-6 md:p-8 text-white border border-slate-800 shadow-xl">
              <div className="absolute top-0 right-0 h-full w-48 bg-radial-at-t from-rose-500/10 via-transparent to-transparent pointer-events-none" />
              <div className="max-w-xl">
                <h1 className="font-sans text-xl md:text-2xl font-black text-white leading-tight">
                  Избранные Telegram-каналы
                </h1>
              </div>
            </div>

            {favoritesLoading ? (
              <div className="flex flex-col items-center justify-center py-20">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-rose-500 border-t-transparent" />
                <span className="mt-4 text-xs font-semibold text-slate-450 font-mono">Загрузка ваших сохраненных каналов...</span>
              </div>
            ) : favoriteItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/20 py-16 px-4 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-900 border border-slate-800 text-rose-500">
                  <Heart className="h-6 w-6 fill-rose-500" />
                </div>
                <h3 className="mt-4 font-sans text-sm font-bold text-white font-mono">Список избранного пуст</h3>
                <p className="mt-1 text-xs text-slate-500 max-w-sm leading-normal">
                  Вы пока не добавили ни одного канала в избранное. Изучите наш каталог и отмечайте понравившиеся активы сердечком.
                </p>
                <button
                  onClick={() => setActiveTab("catalog")}
                  className="mt-5 rounded-2xl bg-white text-slate-950 px-5 py-2.5 text-xs font-black hover:bg-cyan-400 hover:text-slate-950 hover:shadow-cyan-400/10 transition-colors"
                >
                  Перейти в Каталог
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-slate-455 uppercase tracking-widest font-mono">
                    Всего в избранном: {favoriteItems.length}
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                  {favoriteItems.map((item) => (
                    <ChannelCard
                      key={item.id}
                      channel={item}
                      onClick={() => handleSelectProduct(item.id)}
                      isFavorite={true}
                      onToggleFavorite={(id, e) => handleToggleFavorite(id, e)}
                    />
                  ))}
                </div>
              </div>
            )}
            
          </div>
        )}

      </main>

      {/* Slide-out Cart Sidebar drawer */}
      {isCartOpen && (
        <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/80 p-0 backdrop-blur-sm">
          <div className="h-full w-full max-w-sm bg-slate-900/95 p-6 shadow-2xl flex flex-col justify-between animate-in slide-in-from-right duration-250 glass border-l border-slate-800">
            <div>
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div className="flex flex-col">
                  <h3 className="font-sans text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5 animate-in slide-in-from-top">
                    <ShoppingCart className="h-4 w-4 text-cyan-400" /> Ваша Корзина B2C
                  </h3>
                  <span className="text-[9px] font-semibold text-slate-500 font-mono mt-0.5">
                    {authMode === "authorized" ? "🔑 Режим: Авторизован (User)" : "👤 Режим: Гость (Guest)"}
                  </span>
                </div>
                <button
                  onClick={() => setIsCartOpen(false)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors duration-150"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {cart.items.length === 0 ? (
                <div className="text-center py-20 text-slate-500 flex flex-col items-center justify-center">
                  <ShoppingCart className="h-10 w-10 text-slate-800" />
                  <span className="text-xs font-bold mt-4 block text-slate-450">Корзина пока пуста</span>
                  <span className="text-[10px] text-slate-550 max-w-xs block mt-1 leading-normal">
                    Выберите подходящий Телеграм-канал и добавьте его SKU внутри карточки товара.
                  </span>
                </div>
              ) : (
                <div className="mt-6 space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                  {cart.items.map((item) => {
                    const skuSubtotal = Math.round(item.subtotal / 100);
                    const prodName = item.product?.name || item.sku?.name || "Неизвестный канал";
                    const isUnavailable = !!item.unavailable_reason;
                    return (
                      <div
                        key={item.sku_id}
                        className={`flex flex-col border-b border-slate-850 pb-4 animate-in fade-in ${
                          isUnavailable ? "opacity-60 bg-rose-950/10 p-2.5 rounded-xl border border-rose-900/30" : ""
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <span className="block text-xs font-bold text-white leading-tight">
                              {prodName}
                            </span>
                            {item.sku ? (
                              <>
                                <span className="block text-[10px] text-cyan-400 mt-1 font-semibold">{item.sku.name}</span>
                                <span className="block text-[9px] text-slate-500 mt-1 font-mono">Код: {item.sku.sku_code}</span>
                              </>
                            ) : (
                              <span className="block text-[10px] text-slate-500 mt-1">Товар недоступен</span>
                            )}
                            
                            {isUnavailable && (
                              <span className="inline-block mt-2 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded">
                                {item.unavailable_reason === "OUT_OF_STOCK" ? "Нет на складе" : "Ограничен или Удален"}
                              </span>
                            )}
                          </div>
                          
                          <div className="text-right shrink-0 ml-2">
                            <span className="block font-mono text-xs font-extrabold text-white">
                              {skuSubtotal.toLocaleString("ru-RU")} ₽
                            </span>
                            {!isUnavailable && (
                              <div className="flex items-center gap-1 justify-end mt-2 bg-slate-950 border border-slate-800 rounded-lg p-0.5 max-w-max ml-auto shadow-inner">
                                <button
                                  onClick={() => handleUpdateQuantity(item.sku_id, item.quantity - 1)}
                                  className="h-4.5 w-4.5 text-[9px] bg-slate-900 hover:bg-slate-800 rounded flex items-center justify-center font-black transition-colors"
                                >
                                  -
                                </button>
                                <span className="text-[10px] font-bold font-mono px-1.5 text-slate-300">
                                  {item.quantity}
                                </span>
                                <button
                                  onClick={() => handleUpdateQuantity(item.sku_id, item.quantity + 1)}
                                  className="h-4.5 w-4.5 text-[9px] bg-slate-900 hover:bg-slate-800 rounded flex items-center justify-center font-black transition-colors"
                                >
                                  +
                                </button>
                              </div>
                            )}
                            <button
                              onClick={() => handleRemoveFromCart(item.sku_id)}
                              className="text-[9px] font-bold text-rose-400 hover:text-rose-350 hover:underline mt-2 block ml-auto"
                            >
                              Удалить
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {cart.items.length > 0 && (
              <div className="border-t border-slate-800 pt-6">
                
                {/* Mode Context Smart Notice or Merger Banner */}
                {authMode === "guest" && (
                  <div className="mb-4 bg-amber-950/40 border border-amber-900/50 p-2.5 rounded-xl flex items-center justify-between text-left">
                    <div className="max-w-[70%]">
                      <span className="text-[8px] font-bold uppercase tracking-wider text-amber-400 block">Гостевая сессия</span>
                      <span className="text-[9px] text-slate-300 mt-0.5 block leading-normal">
                        Хотите сохранить эти товары в аккаунт?
                      </span>
                    </div>
                    <button
                      onClick={handleMergeCart}
                      className="rounded-lg bg-amber-500 text-slate-950 px-2 py-1 text-[8px] font-black uppercase hover:bg-amber-400 transition-colors shrink-0 font-mono"
                    >
                      🤝 Слить
                    </button>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[9px] text-slate-400 uppercase tracking-widest font-semibold block">Итого к оплате</span>
                    <span className="block font-mono text-base font-extrabold text-cyan-400 neon-text mt-1">
                      {Math.round(cartTotal / 100).toLocaleString("ru-RU")} ₽
                    </span>
                  </div>
                  <button
                    onClick={handleSimulatedCheckout}
                    disabled={checkoutFinished}
                    className="rounded-xl bg-white text-slate-900 px-5 py-2.5 text-xs font-extrabold hover:bg-cyan-400 hover:text-slate-950 disabled:bg-emerald-600 disabled:text-white transition-all duration-200 shadow-lg"
                  >
                    {checkoutFinished ? "🎉 Оплата принята!" : "Купить активы"}
                  </button>
                </div>
                {checkoutFinished && (
                  <div className="mt-3 rounded-xl bg-emerald-950/80 border border-emerald-900/50 p-3 text-center text-[10px] text-emerald-400 font-semibold leading-relaxed">
                    Заказ NM-2026-000452 успешно создан! Отправлен на B2B-раннер. Права передаются через Безопасный Гарант.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Channel Details popup panel */}
      {selectedProductId && activeChannelDetail && (
        <ChannelDetailModal
          productId={selectedProductId}
          currentProduct={activeChannelDetail}
          setCurrentProduct={setActiveChannelDetail}
          onClose={() => {
            setSelectedProductId(null);
            setActiveChannelDetail(null);
          }}
          onAddToCart={handleAddToCart}
          onLoadProductDetail={handleLoadProductDetail}
          isFavorite={favorites.includes(selectedProductId)}
          onToggleFavorite={handleToggleFavorite}
          isSubscribed={subscriptions.includes(selectedProductId)}
          onToggleSubscription={handleToggleSubscription}
        />
      )}

    </div>
  );
}
