import React from "react";
import { Star, Bell, ExternalLink, TrendingDown, Clock, ShieldCheck, Activity } from "lucide-react";
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

  // Badge styling
  const isSuperDeal = intelligence.deal_badge === "SUPER_DEAL";
  const isGoodDeal = intelligence.deal_badge === "GOOD_DEAL";
  const isOverpriced = intelligence.deal_badge === "OVERPRICED";

  const badgeBg = isSuperDeal
    ? "bg-emerald-500 text-white"
    : isGoodDeal
    ? "bg-blue-600 text-white"
    : isOverpriced
    ? "bg-rose-500 text-white"
    : "bg-amber-100 text-amber-800";

  // Sparkline SVG path generation
  const sparklinePts = hotel.history_sparkline || [];
  let svgPath = "";
  if (sparklinePts.length >= 2) {
    const minVal = Math.min(...sparklinePts);
    const maxVal = Math.max(...sparklinePts);
    const range = maxVal - minVal || 1;
    const width = 120;
    const height = 30;

    const coords = sparklinePts.map((p, idx) => {
      const x = (idx / (sparklinePts.length - 1)) * width;
      const y = height - ((p - minVal) / range) * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    svgPath = `M ${coords.join(" L ")}`;
  }

  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col md:flex-row group">
      {/* Hotel Image with Badges */}
      <div className="relative md:w-72 h-48 md:h-auto shrink-0 bg-slate-100 overflow-hidden">
        <img
          src={hotel.main_image_url || "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=600&q=80"}
          alt={hotel.hotel_name}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          loading="lazy"
        />
        <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
          <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shadow-sm ${badgeBg}`}>
            {intelligence.deal_badge.replace("_", " ")}
          </span>
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-black/60 text-white backdrop-blur-sm">
            {intelligence.deal_score}/100
          </span>
        </div>

        {/* Watchlist Quick Action Button */}
        <button
          onClick={() => onToggleWatchlist(hotel)}
          title={isWatched ? "В вашем Watchlist (клик для удаления)" : "Поставить на мониторинг"}
          className={`absolute top-2.5 right-2.5 p-2 rounded-full backdrop-blur-md shadow-md transition-all ${
            isWatched
              ? "bg-amber-500 text-white ring-2 ring-white"
              : "bg-white/80 text-slate-700 hover:bg-white hover:text-amber-500"
          }`}
        >
          <Bell className="w-4 h-4 fill-current" />
        </button>
      </div>

      {/* Main Content Info */}
      <div className="flex-1 p-5 flex flex-col justify-between">
        <div>
          {/* Header row: stars, country, airport */}
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1.5">
            <div className="flex items-center gap-1">
              <span className="font-semibold text-slate-700">{hotel.country}</span>
              {hotel.region && <span>• {hotel.region}</span>}
              <span className="mx-1 text-slate-300">|</span>
              <div className="flex items-center text-amber-500">
                {Array.from({ length: hotel.stars || 4 }).map((_, i) => (
                  <Star key={i} className="w-3.5 h-3.5 fill-current" />
                ))}
              </div>
            </div>
            <span className="bg-slate-100 font-semibold px-2 py-0.5 rounded text-slate-600">
              🛫 {offer.airport}
            </span>
          </div>

          {/* Hotel Name */}
          <h3 className="text-base sm:text-lg font-bold text-slate-900 group-hover:text-blue-600 transition-colors line-clamp-1">
            {hotel.hotel_name}
          </h3>

          {/* Tour Details: Dates, Duration, Operator */}
          <div className="mt-2 flex flex-wrap items-center gap-y-1 gap-x-3 text-xs text-slate-600">
            <span className="inline-flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <b>{offer.departure_date}</b> ({offer.duration_nights} ночей)
            </span>
            <span className="inline-flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              All Inclusive
            </span>
            {offer.operator && (
              <span className="text-[11px] font-medium bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                {offer.operator}
              </span>
            )}
          </div>

          {/* Hopper Verdict Advice Pill */}
          <div className="mt-3 p-2 rounded-xl bg-slate-50 border border-slate-100 flex items-start gap-2">
            <span className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded uppercase shrink-0 ${
              intelligence.hopper_verdict === "BUY NOW"
                ? "bg-emerald-100 text-emerald-800"
                : intelligence.hopper_verdict === "WAIT"
                ? "bg-amber-100 text-amber-800"
                : "bg-rose-100 text-rose-800"
            }`}>
              {intelligence.hopper_verdict}
            </span>
            <p className="text-xs text-slate-600 line-clamp-1 font-medium">
              {intelligence.recommendation}
            </p>
          </div>

          {/* Standard Normalized Benchmark Pill (Point 5) */}
          {hotel.normalized_benchmark_1p_8n && (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-600 bg-blue-50/70 border border-blue-100/80 px-2.5 py-1.5 rounded-xl">
              <span className="font-bold text-blue-700 flex items-center gap-1">
                <span>🏷️ Норм. эталон:</span>
                <span className="text-blue-900 font-extrabold">{hotel.normalized_benchmark_1p_8n.toLocaleString("ru-RU")} zł</span>
              </span>
              <span className="text-slate-300">•</span>
              <span>1 чел. / 8 ночей {hotel.pure_hotel_night_pln ? `(~${hotel.pure_hotel_night_pln} zł/ночь отель)` : ""}</span>
              <span
                className="ml-auto text-[10px] text-blue-600 bg-blue-100/70 px-1.5 py-0.5 rounded font-semibold cursor-help"
                title="Нормализованный индекс приведен к эталону 1 чел. на 8 ночей. Исключает искажения дат, состава семьи и разницы чартеров для объективного сравнения отелей."
              >
                ℹ️ Индекс сравнения
              </span>
            </div>
          )}
        </div>

        {/* Footer: Sparkline & Price + CTA */}
        <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col sm:flex-row sm:items-end justify-between gap-3">
          {/* Sparkline Graph */}
          <div className="flex items-center gap-2">
            {svgPath ? (
              <div>
                <div className="flex items-center gap-1 text-[10px] text-slate-400 uppercase font-semibold mb-0.5">
                  <Activity className="w-3 h-3 text-blue-500" />
                  <span>Динамика ({sparklinePts.length} замера)</span>
                </div>
                <svg width="120" height="30" className="overflow-visible">
                  <path
                    d={svgPath}
                    fill="none"
                    stroke={isSuperDeal ? "#10b981" : isGoodDeal ? "#2563eb" : "#94a3b8"}
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            ) : (
              <span className="text-[11px] text-slate-400 italic">Первый замер цены</span>
            )}
          </div>

          {/* Pricing & Buttons */}
          <div className="flex items-center justify-between sm:justify-end gap-3 w-full sm:w-auto">
            <div className="text-right">
              <div className="text-xl sm:text-2xl font-extrabold text-slate-900 leading-tight">
                {offer.total_price_pln.toLocaleString("ru-RU")} <span className="text-sm font-semibold text-slate-600">zł</span>
              </div>
              <div className="text-[11px] text-slate-500 font-medium">
                {offer.price_per_night_pax.toFixed(0)} zł / ночь / чел.
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onOpenPassport(hotel.hotel_id)}
                className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                title="Посмотреть всю историю цен этого отеля"
              >
                Паспорт
              </button>

              {offer.booking_url && (
                <a
                  href={offer.booking_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3.5 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm flex items-center gap-1.5 active:scale-95"
                >
                  <span>На Fly.pl</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

