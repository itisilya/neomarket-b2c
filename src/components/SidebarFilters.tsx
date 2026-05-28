import React from "react";
import { CategoryRef, FacetsResponse } from "../types";
import { SlidersHorizontal, Check, RefreshCw, Layers } from "lucide-react";

interface SidebarFiltersProps {
  categories: CategoryRef[];
  selectedCategoryId: string | null;
  onSelectCategory: (id: string | null) => void;
  priceMin: string;
  priceMax: string;
  setPriceMin: (v: string) => void;
  setPriceMax: (v: string) => void;
  verifiedOnly: boolean;
  setVerifiedOnly: (v: boolean) => void;
  facets: FacetsResponse | null;
  onReset: () => void;
}

export const SidebarFilters: React.FC<SidebarFiltersProps> = ({
  categories,
  selectedCategoryId,
  onSelectCategory,
  priceMin,
  priceMax,
  setPriceMin,
  setPriceMax,
  verifiedOnly,
  setVerifiedOnly,
  facets,
  onReset
}) => {
  // Extract facets counts for categories and verification state
  const getCategoryCount = (catId: string, catName: string) => {
    if (!facets) return null;
    const catFacetGroup = facets.facets.find(g => g.name === "category");
    if (!catFacetGroup) return 0;
    const fItem = catFacetGroup.values.find(v => v.text_value === catId || v.value === catName);
    return fItem ? fItem.count : 0;
  };

  const getVerifiedCount = (verifiedStr: "true" | "false") => {
    if (!facets) return 0;
    const verifiedFacetGroup = facets.facets.find(g => g.name === "verified");
    if (!verifiedFacetGroup) return 0;
    const fItem = verifiedFacetGroup.values.find(v => v.text_value === verifiedStr);
    return fItem ? fItem.count : 0;
  };

  return (
    <div id="sidebar-filters-container" className="flex flex-col gap-6 rounded-2xl p-5 shadow-lg glass animate-in fade-in duration-200">
      {/* Title */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-4">
        <h3 className="flex items-center gap-2 font-sans font-bold text-white uppercase tracking-wider text-xs">
          <SlidersHorizontal className="h-4 w-4 text-cyan-400" /> Фильтры B2C
        </h3>
        <button
          onClick={onReset}
          className="flex items-center gap-1 rounded-lg bg-slate-900 border border-slate-800 px-2 py-1 text-[11px] font-bold text-slate-300 hover:bg-slate-800 hover:text-cyan-400 transition-all duration-200"
        >
          <RefreshCw className="h-3 w-3" /> Сбросить
        </button>
      </div>

      {/* Categories flat or tree list */}
      <div>
        <h4 className="flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
          <Layers className="h-3 w-3 text-cyan-400" /> Категория канала
        </h4>
        <div className="mt-3 flex flex-col gap-1 max-h-[220px] overflow-y-auto pr-1">
          <button
            onClick={() => onSelectCategory(null)}
            className={`flex items-center justify-between rounded-xl px-3 py-2 text-left text-xs font-semibold transition-all duration-200 ${
              selectedCategoryId === null
                ? "bg-cyan-500 text-slate-950 font-extrabold shadow-sm"
                : "text-slate-300 hover:bg-slate-900/50 hover:text-white"
            }`}
          >
            <span>Все тематики</span>
            <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-md ${selectedCategoryId === null ? 'bg-cyan-600 text-white' : 'bg-slate-900 text-slate-500'}`}>
              all
            </span>
          </button>

          {categories.map((cat) => {
            const count = getCategoryCount(cat.id, cat.name);
            const indentClass = cat.level > 0 ? "ml-4 text-[11px] border-l-2 border-slate-800 pl-2" : "";
            const isSelected = selectedCategoryId === cat.id;
            
            return (
              <button
                key={cat.id}
                onClick={() => onSelectCategory(cat.id)}
                className={`flex items-center justify-between rounded-xl px-3 py-2 text-left text-xs font-semibold transition-all duration-200 ${indentClass} ${
                  isSelected
                    ? "bg-cyan-500 text-slate-950 font-extrabold shadow-sm"
                    : "text-slate-300 hover:bg-slate-900/50 hover:text-white"
                }`}
              >
                <span className="truncate pr-2">{cat.name}</span>
                {count !== null && count > 0 && (
                  <span
                    className={`shrink-0 rounded-md px-1.5 py-0.5 text-[9px] font-bold font-mono ${
                      isSelected
                        ? "bg-cyan-605 text-slate-950 bg-cyan-100"
                        : "bg-cyan-950/85 text-cyan-400 border border-cyan-900/60"
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Verification Facets */}
      <div className="border-t border-slate-800/80 pt-5">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Статус верификации</h4>
        <div className="mt-3 flex flex-col gap-2">
          <label className="relative flex cursor-pointer items-start gap-3 rounded-xl border border-slate-800 bg-slate-900/50 p-3 hover:bg-slate-850/50 transition-all duration-200">
            <input
              type="checkbox"
              checked={verifiedOnly}
              onChange={(e) => setVerifiedOnly(e.target.checked)}
              className="peer sr-only"
            />
            <div className="flex h-4 w-4 shrink-0 items-center justify-center rounded-md border border-slate-700 bg-slate-950 transition-all peer-checked:border-cyan-400 peer-checked:bg-cyan-400">
              <Check className="h-3 w-3 text-slate-950 scale-0 transition-transform peer-checked:scale-100 font-extrabold" />
            </div>
            <div className="flex flex-col select-none">
              <span className="text-xs font-semibold text-slate-200 leading-none">Только проверенные</span>
              <span className="text-[10px] text-slate-400 mt-1">Доверенные продавцы / VIP</span>
            </div>
            {facets && (
              <span className="ml-auto rounded-md bg-slate-900 border border-slate-800 px-1.5 py-0.5 text-[9px] font-bold text-cyan-400 font-mono">
                {getVerifiedCount("true")}
              </span>
            )}
          </label>
        </div>
      </div>

      {/* Price filter (Rubles - automatically scaled to kopecks for API backend) */}
      <div className="border-t border-slate-800/80 pt-5">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Бюджет (₽)</h4>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label className="text-[10px] text-slate-400 font-semibold uppercase">От</label>
            <input
              type="number"
              value={priceMin}
              placeholder="0"
              onChange={(e) => setPriceMin(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 placeholder:text-slate-700 focus:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400 font-mono"
            />
          </div>
          <div>
            <label className="text-[10px] text-slate-400 font-semibold uppercase">До</label>
            <input
              type="number"
              value={priceMax}
              placeholder="500 000"
              onChange={(e) => setPriceMax(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 placeholder:text-slate-700 focus:border-cyan-400 focus:outline-none focus:ring-1 focus:ring-cyan-400 font-mono"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
