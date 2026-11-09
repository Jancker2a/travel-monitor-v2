import React from "react";
import { ExternalLink, Star, ArrowUpDown, Bell } from "lucide-react";
import { SearchHotelItem } from "../types";

interface HotelTableViewProps {
  hotels: SearchHotelItem[];
  onOpenPassport: (hotelId: string) => void;
  onToggleWatchlist: (hotel: SearchHotelItem) => void;
  watchedCohortHashes: Set<string>;
  sortField: string;
  sortAsc: boolean;
  onSort: (field: string) => void;
}

export const HotelTableView: React.FC<HotelTableViewProps> = ({
  hotels,
  onOpenPassport,
  onToggleWatchlist,
  watchedCohortHashes,
  sortField,
  sortAsc,
  onSort,
}) => {
  return (
    <div className="space-y-4" id="tableSection">
      {/* Table Section Title */}
      <div className="flex items-center justify-between">
        <h3 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
          <span>🏨</span>
          <span>Все отели • клик по отелю откроет паспорт справа</span>
        </h3>
        <span className="text-sm text-slate-500 font-semibold">
          Показано <b className="text-slate-900 font-black">{hotels.length}</b> отелей
        </span>
      </div>

      {/* Deal Score Legend */}
      <div className="deal-legend bg-slate-50 border border-slate-200/90 rounded-2xl p-3.5 text-xs text-slate-700 leading-relaxed shadow-2xs">
        <strong className="text-slate-900 font-bold">Как читать Deal Score:</strong>{" "}
        <span className="inline-flex items-center gap-0.5 font-extrabold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
          🔥 Hot
        </span>{" "}
        = очень сильная возможность,{" "}
        <span className="inline-flex items-center gap-0.5 font-extrabold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
          ✅ Good
        </span>{" "}
        = хороший момент,{" "}
        <span className="inline-flex items-center gap-0.5 font-extrabold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
          ↔ Normal
        </span>{" "}
        = обычный уровень (~50),{" "}
        <span className="inline-flex items-center gap-0.5 font-extrabold text-red-700 bg-red-50 px-1.5 py-0.5 rounded border border-red-200">
          📈 Bad
        </span>{" "}
        = подорожало за 48ч и vs средней,{" "}
        <span className="inline-flex items-center gap-0.5 font-extrabold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
          ⏳ Warm-up
        </span>{" "}
        = пока мало истории. Confidence: Low / Medium / High — степень надежности оценки. TripAdvisor слегка сдвигает Deal Score; без отзывов влияние минимально.
      </div>

      {/* Hotels Table */}
      <div className="hotels-table-container">
        <table className="hotels-table" id="hotelsTable">
          <thead>
            <tr className="bg-sky-50/80 border-b border-sky-100 text-sky-900 text-xs uppercase tracking-wider font-extrabold">
              <th
                onClick={() => onSort("hotel")}
                className="cursor-pointer hover:text-blue-900 pl-4 py-3 rounded-l-xl"
                style={{ width: "24%" }}
              >
                <div className="flex items-center gap-1.5">
                  <span>ОТЕЛЬ</span>
                  <ArrowUpDown className="w-3.5 h-3.5 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("price")}
                className="cursor-pointer hover:text-blue-900 py-3"
                style={{ width: "12%" }}
              >
                <div className="flex items-center gap-1.5">
                  <span>ЦЕНА</span>
                  <ArrowUpDown className="w-3.5 h-3.5 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("deal_score")}
                className="cursor-pointer hover:text-blue-900 py-3"
                style={{ width: "11%" }}
              >
                <div className="flex items-center gap-1.5">
                  <span>DEAL SCORE</span>
                  <ArrowUpDown className="w-3.5 h-3.5 opacity-60" />
                </div>
              </th>
              <th style={{ width: "11%", textAlign: "center" }} className="py-3">
                ПРОГНОЗ
              </th>
              <th
                onClick={() => onSort("ta_rating")}
                className="cursor-pointer hover:text-blue-900 py-3 text-center"
                style={{ width: "7%" }}
                title="TripAdvisor"
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span>🦉</span>
                  <ArrowUpDown className="w-3.5 h-3.5 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("delta48")}
                className="cursor-pointer hover:text-blue-900 py-3 text-center"
                style={{ width: "7%" }}
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span>Δ 48Ч</span>
                  <ArrowUpDown className="w-3.5 h-3.5 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("delta_avg")}
                className="cursor-pointer hover:text-blue-900 py-3 text-center"
                style={{ width: "8%" }}
                title="Отклонение от средней цены"
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span>Δ К СРЕДНЕЙ</span>
                  <ArrowUpDown className="w-3.5 h-3.5 opacity-60" />
                </div>
              </th>
              <th style={{ width: "9%" }} className="py-3">
                РЕГИОН
              </th>
              <th style={{ width: "11%" }} className="py-3">
                ДАТЫ
              </th>
              <th style={{ width: "5%", textAlign: "center" }} className="py-3">
                ДЛИТ.
              </th>
              <th style={{ width: "11%", textAlign: "right" }} className="py-3 pr-4 rounded-r-xl">
                ССЫЛКА
              </th>
            </tr>
          </thead>
          <tbody>
            {hotels.map((hotel) => {
              const offer = hotel.current_offer;
              const intel = hotel.intelligence;
              const isWatched = watchedCohortHashes.has(offer.cohort_hash);

              // Deal score pill
              let dealPillClass = "deal-badge-normal";
              let dealText = `${intel.deal_score} Normal`;
              if (intel.deal_score >= 85) {
                dealPillClass = "deal-badge-hot";
                dealText = `${intel.deal_score} 🔥 Hot`;
              } else if (intel.deal_score >= 70) {
                dealPillClass = "deal-badge-good";
                dealText = `${intel.deal_score} ✅ Good`;
              } else if (intel.deal_score < 45) {
                dealPillClass = "deal-badge-bad";
                dealText = `${intel.deal_score} 📈 Bad`;
              }

              // Forecast pill
              let forecastPill = (
                <span className="hopper-pill wait">🟡 ЖДАТЬ</span>
              );
              if (intel.deal_score >= 80) {
                forecastPill = (
                  <span className="hopper-pill buy-now">🟢 ПОКУПАТЬ</span>
                );
              } else if (intel.hopper_verdict === "OVERPRICED" || intel.deal_score < 45) {
                forecastPill = (
                  <span className="hopper-pill overpriced">🔴 ДОРОГО</span>
                );
              }

              // Delta values
              const delta48 = intel.drop_48h_pct;
              const deltaAvg = intel.drop_48h_pct > 0 ? -intel.drop_48h_pct : 0;

              return (
                <tr key={offer.cohort_hash} className="group">
                  {/* Hotel Cell */}
                  <td>
                    <div className="flex items-start gap-3">
                      <div className="w-14 h-14 rounded-xl overflow-hidden bg-slate-100 shrink-0 border border-slate-200/80 shadow-2xs">
                        <img
                          src={
                            hotel.main_image_url ||
                            "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=300&q=80"
                          }
                          alt={hotel.hotel_name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          loading="lazy"
                        />
                      </div>
                      <div className="min-w-0">
                        <div
                          onClick={() => onOpenPassport(hotel.hotel_id)}
                          className="font-extrabold text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer text-[13.5px] leading-snug line-clamp-1"
                          title={`${hotel.hotel_name} — открыть паспорт`}
                        >
                          {hotel.hotel_name}
                        </div>
                        <div className="flex items-center gap-0.5 text-amber-400 mt-1">
                          {Array.from({ length: hotel.stars || 4 }).map((_, i) => (
                            <Star key={i} className="w-3 h-3 fill-current" />
                          ))}
                        </div>
                        <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                          <span className="spec-badge spec-beach text-[10px] font-bold px-1.5 py-0.5 rounded-md">🏖️ 1 линия</span>
                          {hotel.hotel_name.toLowerCase().includes("aqua") && (
                            <span className="spec-badge spec-aqua text-[10px] font-bold px-1.5 py-0.5 rounded-md">🎢 Аквапарк</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Price */}
                  <td>
                    <div className="text-[15.5px] font-black text-slate-900 whitespace-nowrap tracking-tight">
                      {offer.total_price_pln.toLocaleString("ru-RU")} zł
                    </div>
                    <div className="text-xs text-slate-500 font-medium mt-0.5">
                      {offer.price_per_night_pax} zł/ночь
                    </div>
                  </td>

                  {/* Deal Score */}
                  <td>
                    <span className={`text-xs font-black px-2.5 py-1 rounded-full border shadow-2xs whitespace-nowrap ${dealPillClass}`}>
                      {dealText}
                    </span>
                  </td>

                  {/* Forecast */}
                  <td style={{ textAlign: "center" }}>
                    {forecastPill}
                  </td>

                  {/* TripAdvisor */}
                  <td style={{ textAlign: "center" }}>
                    <div className="inline-flex items-center gap-1 text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200/80 font-black text-xs shadow-2xs">
                      <span>● {hotel.ta_rating ? hotel.ta_rating.toFixed(1) : "4.5"}</span>
                    </div>
                  </td>

                  {/* Δ 48ч */}
                  <td style={{ textAlign: "center" }}>
                    {delta48 > 0 ? (
                      <span className="delta-down text-xs font-black px-2 py-0.5 rounded-md">↓ −{delta48}%</span>
                    ) : (
                      <span className="delta-flat text-xs font-bold text-slate-400">—</span>
                    )}
                  </td>

                  {/* Δ к средней */}
                  <td style={{ textAlign: "center" }}>
                    {deltaAvg < 0 ? (
                      <span className="delta-down text-xs font-black px-2 py-0.5 rounded-md">↓ {deltaAvg}%</span>
                    ) : (
                      <span className="delta-flat text-xs font-bold text-slate-400">0%</span>
                    )}
                  </td>

                  {/* Region */}
                  <td className="text-xs font-semibold text-slate-700 truncate">
                    {hotel.region || "Анталья"}
                  </td>

                  {/* Dates */}
                  <td>
                    <div className="text-xs font-bold text-slate-900 whitespace-nowrap">
                      {offer.departure_date}
                    </div>
                    <div className="text-[11px] text-blue-600 font-extrabold uppercase tracking-wide mt-0.5">
                      {offer.airport}
                    </div>
                  </td>

                  {/* Duration */}
                  <td style={{ textAlign: "center" }}>
                    <span className="inline-block text-xs font-black text-slate-800 bg-slate-100 px-2.5 py-1 rounded-lg border border-slate-200/70">
                      {offer.duration_nights}н
                    </span>
                  </td>

                  {/* Actions / Links */}
                  <td>
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => onOpenPassport(hotel.hotel_id)}
                        className="px-3 py-1.5 text-xs font-black text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl border border-blue-200 shadow-2xs transition-colors whitespace-nowrap"
                        title="Открыть AI Паспорт отеля справа"
                      >
                        Паспорт
                      </button>

                      <button
                        type="button"
                        onClick={() => onToggleWatchlist(hotel)}
                        className={`p-2 rounded-xl border transition-colors ${
                          isWatched
                            ? "bg-amber-500 text-white border-amber-600 shadow-2xs"
                            : "bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200"
                        }`}
                        title={isWatched ? "В отслеживаемых" : "Поставить на радар"}
                      >
                        <Bell className="w-3.5 h-3.5" />
                      </button>

                      {offer.booking_url && (
                        <a
                          href={offer.booking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-blue-600 border border-slate-200 shadow-2xs transition-colors"
                          title="Открыть на Fly.pl"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
