import React, { useState, useEffect } from "react";
import { CatalogProductDetail, CatalogSku, CatalogProductCard } from "../types";
import { X, ShieldCheck, ShoppingCart, Info, TrendingUp, DollarSign, Award, Heart } from "lucide-react";

interface ChannelDetailModalProps {
  productId: string;
  onClose: () => void;
  onAddToCart: (sku: CatalogSku, productName: string) => void;
  onLoadProductDetail: (id: string) => Promise<CatalogProductDetail | null>;
  currentProduct: CatalogProductDetail;
  setCurrentProduct: (p: CatalogProductDetail) => void;
  isFavorite?: boolean;
  onToggleFavorite?: (id: string) => void;
}

export const ChannelDetailModal: React.FC<ChannelDetailModalProps> = ({
  productId,
  onClose,
  onAddToCart,
  onLoadProductDetail,
  currentProduct,
  setCurrentProduct,
  isFavorite = false,
  onToggleFavorite
}) => {
  const [selectedSku, setSelectedSku] = useState<CatalogSku | null>(null);
  const [similarProducts, setSimilarProducts] = useState<CatalogProductCard[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  const [addedMessage, setAddedMessage] = useState(false);
  const [imageError, setImageError] = useState(false);

  // Load similar products and select first SKU on load
  useEffect(() => {
    if (currentProduct) {
      if (currentProduct.skus && currentProduct.skus.length > 0) {
        setSelectedSku(currentProduct.skus[0]);
      } else {
        setSelectedSku(null);
      }
      loadSimilar(currentProduct.id);
    }
    setAddedMessage(false);
    setImageError(false);
  }, [currentProduct]);

  const loadSimilar = async (id: string) => {
    setLoadingSimilar(true);
    try {
      const res = await fetch(`/api/v1/catalog/products/${id}/similar`);
      if (res.ok) {
        const data = await res.json();
        setSimilarProducts(data);
      }
    } catch (err) {
      console.error("Error loading similar channels:", err);
    } finally {
      setLoadingSimilar(false);
    }
  };

  const handleSimilarClick = async (id: string) => {
    const freshDetail = await onLoadProductDetail(id);
    if (freshDetail) {
      setCurrentProduct(freshDetail);
    }
  };

  if (!currentProduct) return null;

  // Pricing math using selected SKU if available, otherwise fallback to base product
  const activePriceInKops = selectedSku ? selectedSku.price : currentProduct.min_price;
  // If SKU contains a discount parameter (or fake discount), handle strikethrough math in Rubles:
  const discountVal = (selectedSku as any)?.discount || 0;
  
  const rubPriceWithDiscount = Math.round((activePriceInKops - discountVal) / 100);
  const origRubPrice = discountVal > 0 ? Math.round(activePriceInKops / 100) : (currentProduct.old_price ? Math.round(currentProduct.old_price / 100) : null);

  const handleCartClick = () => {
    if (selectedSku) {
      onAddToCart(selectedSku, currentProduct.name);
      setAddedMessage(true);
      setTimeout(() => setAddedMessage(false), 3000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-md">
      <div className="relative flex h-full max-h-[90vh] w-full max-w-4xl flex-col rounded-3xl border border-slate-800 bg-slate-900/95 shadow-2xl animate-in fade-in zoom-in duration-200 overflow-hidden text-slate-100 glass">
        
        {/* Header Ribbon */}
        <div className="flex shrink-0 items-center justify-between border-b border-slate-800/80 px-6 py-4 bg-slate-950">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center rounded-lg bg-cyan-950/80 border border-cyan-900/40 px-2.5 py-1 text-xs font-bold text-cyan-400 uppercase tracking-widest">
              {currentProduct.category?.name || "Телеграм Канал"}
            </span>
            {currentProduct.verified && (
              <span className="flex items-center gap-1 rounded-lg bg-emerald-950/80 border border-emerald-900/40 px-2.5 py-1 text-xs font-bold text-emerald-400">
                <ShieldCheck className="h-4 w-4" />
                Проверен
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-xl p-2 text-slate-400 hover:bg-slate-850 hover:text-white transition-colors duration-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Content Scroll Area */}
        <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-8">
          
          {/* Main Top Grid */}
          <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
            
            {/* Left Column: Visual Carousel/Image & Key Info */}
            <div className="space-y-4">
              <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-sm">
                {currentProduct.images && currentProduct.images[0] && !imageError ? (
                  <img
                    src={currentProduct.images[0].url}
                    alt={currentProduct.name}
                    referrerPolicy="no-referrer"
                    onError={() => setImageError(true)}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-cyan-950/80 text-2xl font-bold text-cyan-400">
                    {currentProduct.name[0]}
                  </div>
                )}
                {/* Float Subscribers Count */}
                <div className="absolute bottom-3 left-3 rounded-xl bg-slate-950/90 px-3 py-1.5 text-xs font-bold text-white border border-slate-800 backdrop-blur-sm">
                  {currentProduct.subscribers.toLocaleString("ru-RU")} подписчиков
                </div>
              </div>

              {/* Quick Metrics Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div className="flex flex-col rounded-xl bg-slate-950/60 p-3 text-center border border-slate-800">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">ER Охват</span>
                  <span className="mt-1 font-mono text-base font-bold text-cyan-400">{currentProduct.er}%</span>
                </div>
                <div className="flex flex-col rounded-xl bg-slate-950/60 p-3 text-center border border-slate-800">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Доход/мес</span>
                  <span className="mt-1 font-mono text-base font-bold text-emerald-400">
                    {Math.round(currentProduct.monthly_income / 100).toLocaleString("ru-RU")} ₽
                  </span>
                </div>
                <div className="flex flex-col rounded-xl bg-slate-950/60 p-3 text-center border border-slate-800">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Окупаемость</span>
                  <span className="mt-1 font-sans text-xs font-bold text-purple-400">
                    ~{Math.max(1, Math.round(currentProduct.min_price / (currentProduct.monthly_income || 1)))} мес
                  </span>
                </div>
              </div>

              {/* Description */}
              <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
                <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-400">
                  <Info className="h-4 w-4 text-cyan-400" /> Описание канала
                </h4>
                <p className="mt-2 font-sans text-xs leading-relaxed text-slate-300">
                  {currentProduct.description}
                </p>
              </div>
            </div>

            {/* Right Column: Dynamic Price Engine, Package Tiers, characteristics */}
            <div className="flex flex-col justify-between">
              
              <div className="space-y-6">
                <div>
                  <h2 className="font-sans text-2xl font-black text-white leading-tight">
                    {currentProduct.name}
                  </h2>
                  <span className="mt-1 block text-xs text-slate-400">
                    Продавец: <span className="font-semibold text-cyan-400">{currentProduct.seller?.display_name || "Гарант NeoMarket"}</span>
                  </span>
                </div>

                {/* Sku Packages Selector */}
                {currentProduct.skus && currentProduct.skus.length > 0 && (
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-slate-400 block mb-2">
                      Выберите пакет сделки (SKU):
                    </label>
                    <div className="mt-2 flex flex-col gap-2">
                      {currentProduct.skus.map((sku) => {
                        const isSelected = selectedSku?.id === sku.id;
                        return (
                          <button
                            key={sku.id}
                            onClick={() => setSelectedSku(sku)}
                            className={`flex items-center justify-between rounded-xl border p-3.5 text-left transition-all duration-200 ${
                              isSelected
                                ? "border-cyan-400 bg-cyan-950/30 shadow-md shadow-cyan-950/50 accent-glow"
                                : "border-slate-850 bg-slate-950/50 hover:bg-slate-900"
                            }`}
                          >
                            <div>
                              <span className={`block text-xs font-bold ${isSelected ? "text-cyan-400" : "text-slate-200"}`}>
                                {sku.name}
                              </span>
                              <span className="block text-[10px] text-slate-450 mt-0.5">
                                Код: <span className="font-mono">{sku.sku_code}</span>
                              </span>
                            </div>
                            <div className="text-right">
                              <span className="block font-mono text-sm font-extrabold text-white">
                                {Math.round(sku.price / 100).toLocaleString("ru-RU")} ₽
                              </span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Characteristics Specification list */}
                <div>
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400 block pb-2 border-b border-slate-800">
                    Характеристики актива
                  </label>
                  <table className="mt-3 w-full text-xs">
                    <tbody>
                      {currentProduct.characteristics && currentProduct.characteristics.map((char, index) => (
                        <tr key={index} className="border-b border-slate-850/55">
                          <td className="py-2 font-medium text-slate-450 pr-4">{char.name}</td>
                          <td className="py-2 font-bold text-slate-200 text-right">{char.value}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Price block and checkout action */}
              <div className="mt-8 border-t border-slate-800 pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs text-slate-450 uppercase tracking-widest font-semibold block">Итого к оплате</span>
                    <div className="flex items-baseline mt-1.5">
                      {origRubPrice && (
                        <span className="mr-2 text-xs text-slate-500 line-through font-mono">
                          {origRubPrice.toLocaleString("ru-RU")} ₽
                        </span>
                      )}
                      <span className="font-mono text-2xl font-black text-cyan-400 neon-text">
                        {rubPriceWithDiscount.toLocaleString("ru-RU")}{" "}
                        <span className="text-sm font-normal text-slate-350 font-mono">₽</span>
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col gap-1.5 shrink-0 align-right items-end">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onToggleFavorite?.(currentProduct.id)}
                        className={`flex h-12 w-12 items-center justify-center rounded-2xl border transition-all duration-200 ${
                          isFavorite 
                            ? "bg-rose-950/80 text-rose-500 border-rose-900/50 hover:bg-rose-900/40 hover:text-rose-400" 
                            : "bg-slate-900 text-slate-300 border-slate-800 hover:bg-slate-800 hover:text-rose-500"
                        }`}
                        title={isFavorite ? "Удалить из избранного" : "Добавить в избранное"}
                      >
                        <Heart className={`h-5 w-5 ${isFavorite ? "fill-rose-500" : ""}`} />
                      </button>
                      <button
                        onClick={handleCartClick}
                        disabled={!selectedSku}
                        className="flex items-center gap-2 rounded-2xl bg-white text-slate-950 px-6 py-3.5 font-sans text-sm font-extrabold transition-all duration-200 hover:bg-cyan-400 hover:text-slate-950 hover:accent-glow active:scale-95 disabled:bg-slate-700 disabled:text-slate-400 disabled:cursor-not-allowed text-nowrap"
                      >
                        <ShoppingCart className="h-4 w-4" /> В корзину B2C
                      </button>
                    </div>
                    <span className="text-[9px] text-slate-500 uppercase tracking-wider">Безопасный Гарант сделок</span>
                  </div>
                </div>

                {addedMessage && (
                  <div className="mt-3 rounded-xl bg-cyan-950/80 border border-cyan-800 p-2.5 text-center text-xs font-bold text-cyan-400 uppercase tracking-wide animate-bounce">
                    🎉 Товар добавлен в корзину NeoMarket B2C!
                  </div>
                )}
              </div>

            </div>
          </div>

          {/* Bottom Module: Similar Channels suggested (B2C-4) */}
          <div className="border-t border-slate-800 pt-8">
            <h3 className="flex items-center gap-2 font-sans font-bold text-white uppercase tracking-wider text-xs">
              <Award className="h-5 w-5 text-amber-400" /> Похожие каналы для инвестирования
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Рекомендованные каналы той же тематики по алгоритму B2C-4.
            </p>

            {loadingSimilar ? (
              <div className="mt-6 text-center text-xs text-slate-500 font-medium font-mono">
                Поиск похожих каналов...
              </div>
            ) : similarProducts.length === 0 ? (
              <div className="mt-6 rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500 italic">
                В этой категории больше нет других доступных каналов.
              </div>
            ) : (
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
                {similarProducts.slice(0, 3).map((item) => {
                  const itemPrice = Math.round(item.min_price / 100);
                  return (
                    <div
                      key={item.id}
                      onClick={() => handleSimilarClick(item.id)}
                      className="group/item flex flex-col justify-between rounded-xl p-4 transition-all duration-200 glass hover:border-cyan-400/50 hover:bg-slate-900/40 cursor-pointer"
                    >
                      <div>
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-bold text-slate-450 flex items-center gap-1 font-mono">
                            👥 {item.subscribers.toLocaleString("ru-RU")}
                          </span>
                          {item.verified && (
                            <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest bg-cyan-950/80 px-1 py-0.5 rounded border border-cyan-900/50">VIP</span>
                          )}
                        </div>
                        <h4 className="mt-2.5 font-sans text-xs font-extrabold text-slate-200 group-hover/item:text-cyan-400 transition-colors">
                          {item.name}
                        </h4>
                      </div>
                      <div className="mt-4 flex items-baseline justify-between pt-2.5 border-t border-slate-850/80">
                        <span className="text-[10px] text-slate-500 uppercase font-semibold">Цена</span>
                        <span className="font-mono text-xs font-bold text-white">
                          {itemPrice.toLocaleString("ru-RU")} ₽
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};
