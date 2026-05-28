import React, { useState } from "react";
import { CatalogProductCard } from "../types";
import { Users, TrendingUp, DollarSign, ShieldCheck, Star } from "lucide-react";

interface ChannelCardProps {
  channel: CatalogProductCard;
  onClick: () => void;
}

export const ChannelCard: React.FC<ChannelCardProps> = ({ channel, onClick }) => {
  const [imageError, setImageError] = useState(false);
  // Convert kopecks to rubles
  const rubPrice = Math.round(channel.min_price / 100);
  const oldRubPrice = channel.old_price ? Math.round(channel.old_price / 100) : null;
  const rubIncome = Math.round(channel.monthly_income / 100);

  const getBorderColor = (categoryName?: string) => {
    const name = (categoryName || "").toLowerCase();
    if (name.includes("crypto") || name.includes("крипт") || name.includes("финанс") || name.includes("экономика")) {
      return "border-l-4 border-l-cyan-400";
    }
    if (name.includes("tech") || name.includes("it") || name.includes("новости") || name.includes("наука")) {
      return "border-l-4 border-l-purple-500";
    }
    if (name.includes("life") || name.includes("лайф") || name.includes("блог") || name.includes("юмор") || name.includes("рецепт")) {
      return "border-l-4 border-l-emerald-400";
    }
    return "border-l-4 border-l-cyan-400";
  };

  const borderClass = getBorderColor(channel.category?.name);

  return (
    <div
      id={`channel-card-${channel.id}`}
      onClick={onClick}
      className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl p-5 shadow-lg glass transition-all duration-300 hover:-translate-y-1 hover:border-cyan-500/50 hover:shadow-cyan-500/10 cursor-pointer ${borderClass}`}
    >
      {/* Visual background glow */}
      <div className="absolute -top-10 -right-10 h-28 w-28 rounded-full bg-cyan-500/5 blur-2xl group-hover:bg-cyan-500/15 transition-colors duration-300" />

      {/* Header Info */}
      <div>
        <div className="flex items-start justify-between gap-2">
          <span className="inline-flex items-center rounded-lg bg-cyan-950/80 border border-cyan-900/40 px-2 py-1 text-[11px] font-bold text-cyan-400 uppercase tracking-widest">
            {channel.category?.name || "Канал"}
          </span>
          {channel.verified && (
            <span className="flex items-center gap-1 rounded-lg bg-emerald-950/80 border border-emerald-900/40 px-2 py-1 text-[11px] font-bold text-emerald-400">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              Проверен
            </span>
          )}
        </div>

        {/* Channel Icon or Placeholder & Name */}
        <div className="mt-4 flex items-center gap-3">
          <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-900">
            {channel.images && channel.images[0] && !imageError ? (
              <img
                src={channel.images[0].url}
                alt={channel.name}
                referrerPolicy="no-referrer"
                onError={() => setImageError(true)}
                className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center bg-cyan-950 text-cyan-400 font-mono text-lg font-black uppercase">
                {channel.name.slice(0, 2)}
              </div>
            )}
          </div>
          <div>
            <h3 className="font-sans font-extrabold text-white leading-tight group-hover:text-cyan-400 transition-colors duration-200 text-sm">
              {channel.name}
            </h3>
            <div className="flex items-center gap-1 mt-1">
              <Star className="h-3.5 w-3.5 fill-amber-400 stroke-amber-400" />
              <span className="font-mono text-xs font-bold text-slate-200">{channel.rating}</span>
              <span className="text-[10px] text-slate-400">({channel.reviews_count} отзывов)</span>
            </div>
          </div>
        </div>

        {/* Core Channel Indicators */}
        <div className="mt-5 grid grid-cols-3 gap-2 border-t border-b border-slate-800/80 py-3.5">
          <div className="flex flex-col">
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-slate-400 font-bold">
              <Users className="h-3 w-3 text-cyan-400" /> Подп.
            </span>
            <span className="mt-1 font-mono text-xs font-extrabold text-white">
              {channel.subscribers.toLocaleString("ru-RU")}
            </span>
          </div>

          <div className="flex flex-col">
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-slate-400 font-bold">
              <TrendingUp className="h-3 w-3 text-purple-400" /> ER-Клик
            </span>
            <span className="mt-1 font-mono text-xs font-extrabold text-white">
              {channel.er}%
            </span>
          </div>

          <div className="flex flex-col">
            <span className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-slate-400 font-bold">
              <DollarSign className="h-3 w-3 text-emerald-400" /> Доход/мес
            </span>
            <span className="mt-1 font-mono text-xs font-extrabold text-white">
              {rubIncome.toLocaleString("ru-RU")} ₽
            </span>
          </div>
        </div>
      </div>

      {/* Pricing and Action */}
      <div className="mt-4 flex items-end justify-between">
        <div>
          <span className="block text-[10px] text-slate-400 uppercase tracking-widest font-semibold">Цена</span>
          {oldRubPrice && (
            <span className="text-xs text-slate-500 line-through mr-1.5 font-mono">
              {oldRubPrice.toLocaleString("ru-RU")} ₽
            </span>
          )}
          <span className="font-mono text-base font-extrabold text-cyan-400 neon-text">
            {rubPrice.toLocaleString("ru-RU")}{" "}
            <span className="text-[11px] font-normal text-slate-400 font-mono">₽</span>
          </span>
        </div>
        <button
          className="rounded-xl bg-white text-slate-900 px-3.5 py-1.5 font-sans text-xs font-extrabold hover:bg-cyan-400 hover:text-slate-950 hover:accent-glow transition-all duration-200"
          onClick={(e) => {
            e.stopPropagation();
            onClick();
          }}
        >
          Купить
        </button>
      </div>
    </div>
  );
};
