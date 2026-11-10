import React from "react";
import {
  Star,
  Bell,
  ExternalLink,
  Clock,
  ShieldCheck,
  Plane,
  FileText,
  Activity,
  MapPin,
} from "lucide-react";
import { SearchHotelItem } from "../types";

interface Props {
  hotel: SearchHotelItem;
  onOpenPassport: (hotelId: string) => void;
  onToggleWatchlist: (hotel: SearchHotelItem) => void;
  isWatched?: boolean;
}

export const HotelCard: React.FC<Props> = ({
  hotel,
  onOpenPassport,
  onToggleWatchlist,
  isWatched = false,
}) => {
  const { current_offer: offer, intelligence } = hotel;

  // Deal score badges & styling (aligned with Table view)
  const score = intelligence.deal_score ?? 50;
  let dealBadgeBg = "bg-slate-900/80 text-white border-slate-700/60";
  let dealBadgeText = `${score} Normal`;
  if (score >= 85) {
    dealBadgeBg = "bg-amber-500 text-white border-amber-400";
    dealBadgeText = `${score} 🔥 Hot`;
  } else if (score >= 70) {
    dealBadgeBg = "bg-emerald-600 text-white border-emerald-500";
    dealBadgeText = `${score} ✅ Good`;
  } else if (score < 45) {
    dealBadgeBg = "bg-rose-600 text-white border-rose-500";
    dealBadgeText = `${score} 📈 Bad`;
  }

  // Forecast pill
  let forecastPill = (
    <span className="hopper-pill wait text-[11px] font-black px-2 py-0.5 rounded-md">
      🟡 ЖДАТЬ
    </span>
  );
  if (score >= 80) {
    forecastPill = (
      <span className="hopper-pill buy-now text-[11px] font-black px-2 py-0.5 rounded-md">
        🟢 ПОКУПАТЬ
      </span>
    );
  } else if (intelligence.hopper_verdict === "OVERPRICED" || score < 45) {
    forecastPill = (
      <span className="hopper-pill overpriced text-[11px] font-black px-2 py-0.5 rounded-md">
        🔴 ДОРОГО
      </span>
    );
  }

  // Deltas
  const delta48 = intelligence.drop_48h_pct;
  const deltaAvg = intelligence.delta_vs_typical_pct !== undefined ? intelligence.delta_vs_typical_pct : 0;

  // Sparkline SVG path generation
  const sparklinePts = hotel.history_sparkline || [];
  let svgPath = "";
  let areaPath = "";
  if (sparklinePts.length >= 2) {
    const minVal = Math.min(...sparklinePts);
    const maxVal = Math.max(...sparklinePts);
    const range = maxVal - minVal || 1;
    const width = 100;
    const height = 26;

    const coords = sparklinePts.map((p, idx) => {
      const x = (idx / (sparklinePts.length - 1)) * width;
      const y = height - ((p - minVal) / range) * (height - 8) - 4;
      return [x, y];
    });
    svgPath = `M ${coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L ")}`;
    areaPath = `${svgPath} L ${width},${height} L 0,${height} Z`;
  }

  const gradientId = `spark-grad-${hotel.hotel_id.replace(/[^a-zA-Z0-9]/g, "-")}`;

  return (
    <div
      onClick={() => onOpenPassport(hotel.hotel_id)}
      className="bg-white rounded-2xl border border-slate-200/90 overflow-hidden shadow-2xs hover:shadow-xl hover:border-sky-300 transition-all duration-300 flex flex-col h-full group cursor-pointer relative select-none"
      title={`Кликните, чтобы открыть AI Паспорт ${hotel.hotel_name}`}
    >
      {/* 1. Hotel Image with Floating Badges */}
      <div className="relative w-full h-48 sm:h-52 shrink-0 bg-slate-100 overflow-hidden">
        <img
          src={
            hotel.main_image_url ||
            "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=600&q=80"
          }
          alt={hotel.hotel_name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          loading="lazy"
        />

        {/* Subtle Vignette Gradient for badge legibility */}
        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/70 via-transparent to-slate-950/40 pointer-events-none" />

        {/* Top-Left: Deal Score + 48h Delta */}
        <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5 flex-wrap max-w-[80%]">
          <span
            className={`text-[11.5px] font-black px-2.5 py-1 rounded-lg backdrop-blur-md border shadow-sm whitespace-nowrap ${dealBadgeBg}`}
          >
            {dealBadgeText}
          </span>

          {delta48 !== 0 && (
            <span
              className={`text-[11px] font-black px-2 py-0.5 rounded-lg backdrop-blur-md border shadow-sm whitespace-nowrap ${
                delta48 < 0
                  ? "bg-emerald-600/90 text-white border-emerald-400"
                  : "bg-rose-600/90 text-white border-rose-400"
              }`}
            >
              {delta48 < 0 ? `↓ ${Math.abs(delta48).toFixed(1)}%` : `↑ +${delta48.toFixed(1)}%`}
            </span>
          )}
        </div>

        {/* Top-Right: Watchlist Button */}
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggleWatchlist(hotel);
          }}
          title={isWatched ? "В отслеживаемых (клик для удаления)" : "Поставить на радар"}
          className={`absolute top-2.5 right-2.5 w-9 h-9 rounded-xl flex items-center justify-center backdrop-blur-md transition-all shadow-md cursor-pointer ${
            isWatched
              ? "bg-amber-500 text-white ring-2 ring-white scale-105"
              : "bg-white/85 text-slate-700 hover:bg-white hover:text-amber-500 hover:scale-105"
          }`}
        >
          <Bell className="w-4 h-4 fill-current" />
        </button>

        {/* Bottom Bar on Image: Specs & Duration */}
        <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-center justify-between gap-1.5 pointer-events-none">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-black/60 text-white backdrop-blur-md border border-white/20">
              🏖️ {hotel.beach_line || hotel.specs?.beach_line || 1} линия
            </span>
            {(hotel.has_aquapark ||
              hotel.specs?.has_aquapark ||
              hotel.hotel_name.toLowerCase().includes("aqua")) && (
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-cyan-900/70 text-cyan-200 backdrop-blur-md border border-cyan-400/30">
                🎢 Горки
              </span>
            )}
            {(hotel.has_heated_pools || hotel.specs?.has_heated_pools) && (
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-amber-900/70 text-amber-200 backdrop-blur-md border border-amber-400/30">
                🔥 Бассейн
              </span>
            )}
          </div>

          <span className="text-[11.5px] font-black px-2.5 py-0.5 rounded-md bg-slate-900/80 text-white backdrop-blur-md border border-slate-700/60 shadow-xs shrink-0">
            {offer.duration_nights}н
          </span>
        </div>
      </div>

      {/* 2. Main Content Body */}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          {/* Header row: Country/Region, Stars, TripAdvisor */}
          <div className="flex items-center justify-between gap-2 text-xs text-slate-500 mb-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="font-bold text-slate-700 truncate max-w-[130px]">
                {hotel.region || hotel.country}
              </span>
              <div className="flex items-center text-amber-400 shrink-0">
                {Array.from({ length: hotel.stars || 4 }).map((_, i) => (
                  <Star key={i} className="w-3 h-3 fill-current" />
                ))}
              </div>
            </div>

            {/* TripAdvisor Rating Pill */}
            <div className="inline-flex items-center gap-1 text-[11.5px] font-black text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-200 shadow-2xs shrink-0">
              <span>🦉 {hotel.ta_rating ? hotel.ta_rating.toFixed(1) : "4.5"}</span>
            </div>
          </div>

          {/* Hotel Name */}
          <h3
            className="text-[16px] sm:text-[17px] font-black text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1 tracking-tight leading-snug"
            title={hotel.hotel_name}
          >
            {hotel.hotel_name}
          </h3>

          {/* Tour Details Chips: Dates, Airport, Board */}
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-50 border border-slate-200/80 font-bold text-slate-800 text-[11.5px]">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span>{offer.departure_date}</span>
            </span>

            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-blue-50 border border-blue-100 font-extrabold text-blue-700 text-[11.5px] uppercase tracking-wide">
              <Plane className="w-3.5 h-3.5 text-blue-500" />
              <span>{offer.airport}</span>
            </span>

            <span className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-50 border border-slate-200/80 font-medium text-slate-700 text-[11.5px]">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              <span>All Inclusive</span>
            </span>
          </div>

          {/* Hopper Verdict Advice Pill */}
          <div className="mt-2.5 p-2 rounded-xl bg-slate-50/90 border border-slate-200/70 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 shrink-0">
              {forecastPill}
            </div>
            <p className="text-[11.5px] text-slate-600 truncate font-semibold">
              {intelligence.recommendation || "Следите за обновлениями цены"}
            </p>
          </div>

          {/* Sparkline Price Trend or Dynamic Median */}
          <div className="mt-2.5 px-2.5 py-1.5 rounded-xl bg-slate-50/70 border border-slate-200/60 flex items-center justify-between gap-2">
            {svgPath ? (
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-1 text-[10.5px] text-slate-500 font-bold">
                  <Activity className="w-3 h-3 text-blue-500" />
                  <span>Динамика ({sparklinePts.length} зам.)</span>
                </div>
                <div className="w-24 h-6">
                  <svg
                    viewBox="0 0 100 26"
                    preserveAspectRatio="none"
                    className="w-full h-full overflow-visible"
                  >
                    <defs>
                      <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>
                    <path d={areaPath} fill={`url(#${gradientId})`} />
                    <path
                      d={svgPath}
                      fill="none"
                      stroke={score >= 70 ? "#059669" : score < 45 ? "#e11d48" : "#2563eb"}
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between w-full text-[11px] text-slate-500 font-semibold">
                <span>Исторический мин.:</span>
                <b className="text-slate-800 font-bold">
                  {(intelligence.historic_min_pln || offer.total_price_pln).toLocaleString("ru-RU")} zł
                </b>
              </div>
            )}
          </div>
        </div>

        {/* 3. Footer: Pricing & Action Buttons */}
        <div className="mt-3.5 pt-3 border-t border-slate-100 flex flex-col justify-end">
          {/* Price & Delta Row */}
          <div className="flex items-baseline justify-between mb-2.5">
            <div>
              <div className="text-2xl font-black text-slate-900 tracking-tight leading-none">
                {offer.total_price_pln.toLocaleString("ru-RU")}{" "}
                <span className="text-sm font-extrabold text-slate-600">zł</span>
              </div>
              <div className="text-[11.5px] text-slate-400 font-bold mt-1">
                {offer.price_per_night_pax.toFixed(0)} zł / ночь / чел.
              </div>
            </div>

            {deltaAvg !== 0 && (
              <span
                className={`text-[11px] font-black px-2 py-0.5 rounded-lg border shadow-2xs whitespace-nowrap ${
                  deltaAvg < 0
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : "bg-rose-50 text-rose-700 border-rose-200"
                }`}
                title="Отклонение от типичной цены отеля"
              >
                {deltaAvg < 0 ? `↓ ${Math.abs(deltaAvg).toFixed(1)}% vs ср.` : `↑ +${deltaAvg.toFixed(1)}% vs ср.`}
              </span>
            )}
          </div>

          {/* Action Buttons: 50/50 Balanced Row, Never Overflows */}
          <div className="flex items-center gap-2 w-full">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onOpenPassport(hotel.hotel_id);
              }}
              className="flex-1 py-2.5 px-3 rounded-xl text-xs font-black text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 shadow-2xs hover:shadow-xs transition-all flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer active:scale-98"
              title="Открыть AI Паспорт отеля"
            >
              <FileText className="w-3.5 h-3.5 shrink-0" />
              <span>Паспорт</span>
            </button>

            {offer.booking_url ? (
              <a
                href={offer.booking_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="flex-1 py-2.5 px-3 rounded-xl text-xs font-black text-white bg-blue-600 hover:bg-blue-700 shadow-sm hover:shadow transition-all flex items-center justify-center gap-1.5 whitespace-nowrap cursor-pointer active:scale-98"
                title="Открыть предложение на Fly.pl"
              >
                <span>На Fly.pl</span>
                <ExternalLink className="w-3.5 h-3.5 shrink-0" />
              </a>
            ) : (
              <button
                type="button"
                disabled
                className="flex-1 py-2.5 px-3 rounded-xl text-xs font-black text-slate-400 bg-slate-100 border border-slate-200 cursor-not-allowed text-center whitespace-nowrap"
              >
                Нет ссылки
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
