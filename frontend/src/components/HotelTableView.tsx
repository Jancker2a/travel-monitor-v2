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
    <div className="space-y-3" id="tableSection">
      {/* Table Section Title */}
      <div className="flex items-center justify-between">
        <h3 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
          <span>🏨</span>
          <span>Все отели • клик по отелю откроет паспорт справа</span>
        </h3>
        <span className="text-xs text-slate-500 font-medium">
          Показано <b className="text-slate-800">{hotels.length}</b> отелей
        </span>
      </div>

      {/* Deal Score Legend */}
      <div className="deal-legend bg-slate-50 border border-slate-200/90 rounded-xl p-3 text-[11px] text-slate-700 leading-relaxed shadow-2xs">
        <strong className="text-slate-900">Как читать Deal Score:</strong>{" "}
        <span className="inline-flex items-center gap-0.5 font-bold text-amber-700 bg-amber-50 px-1 py-0.2 rounded border border-amber-200">
          🔥 Hot
        </span>{" "}
        = очень сильная возможность,{" "}
        <span className="inline-flex items-center gap-0.5 font-bold text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded border border-emerald-200">
          ✅ Good
        </span>{" "}
        = хороший момент,{" "}
        <span className="inline-flex items-center gap-0.5 font-bold text-slate-700 bg-slate-100 px-1 py-0.2 rounded border border-slate-200">
          ↔ Normal
        </span>{" "}
        = обычный уровень (~50),{" "}
        <span className="inline-flex items-center gap-0.5 font-bold text-red-700 bg-red-50 px-1 py-0.2 rounded border border-red-200">
          📈 Bad
        </span>{" "}
        = подорожало за 48ч и vs средней,{" "}
        <span className="inline-flex items-center gap-0.5 font-bold text-blue-700 bg-blue-50 px-1 py-0.2 rounded border border-blue-200">
          ⏳ Warm-up
        </span>{" "}
        = пока мало истории. Confidence: Low / Medium / High — степень надежности оценки. TripAdvisor слегка сдвигает Deal Score; без отзывов влияние минимально.
      </div>

      {/* Hotels Table */}
      <div className="hotels-table-container">
        <table className="hotels-table" id="hotelsTable">
          <thead>
            <tr className="bg-sky-50/80 border-b border-sky-100 text-sky-800 text-[11px] uppercase tracking-wider">
              <th
                onClick={() => onSort("hotel")}
                className="cursor-pointer hover:text-blue-900 pl-3 py-2.5 rounded-l-xl"
                style={{ width: "24%" }}
              >
                <div className="flex items-center gap-1">
                  <span>ОТЕЛЬ</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("price")}
                className="cursor-pointer hover:text-blue-900 py-2.5"
                style={{ width: "12%" }}
              >
                <div className="flex items-center gap-1">
                  <span>ЦЕНА</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("deal_score")}
                className="cursor-pointer hover:text-blue-900 py-2.5"
                style={{ width: "11%" }}
              >
                <div className="flex items-center gap-1">
                  <span>DEAL SCORE</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th style={{ width: "11%", textAlign: "center" }} className="py-2.5">
                ПРОГНОЗ
              </th>
              <th
                onClick={() => onSort("ta_rating")}
                className="cursor-pointer hover:text-blue-900 py-2.5 text-center"
                style={{ width: "7%" }}
                title="TripAdvisor"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>🦉</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("delta48")}
                className="cursor-pointer hover:text-blue-900 py-2.5 text-center"
                style={{ width: "7%" }}
              >
                <div className="flex items-center justify-center gap-1">
                  <span>Δ 48Ч</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th
                onClick={() => onSort("delta_avg")}
                className="cursor-pointer hover:text-blue-900 py-2.5 text-center"
                style={{ width: "8%" }}
                title="Отклонение от средней цены"
              >
                <div className="flex items-center justify-center gap-1">
                  <span>Δ К СРЕДНЕЙ</span>
                  <ArrowUpDown className="w-3 h-3 opacity-60" />
                </div>
              </th>
              <th style={{ width: "9%" }} className="py-2.5">
                РЕГИОН
              </th>
              <th style={{ width: "11%" }} className="py-2.5">
                ДАТЫ
              </th>
              <th style={{ width: "6%", textAlign: "center" }} className="py-2.5">
                ДЛИТ.
              </th>
              <th style={{ width: "10%", textAlign: "right" }} className="py-2.5 pr-3 rounded-r-xl">
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
                    <div className="flex items-start gap-2.5">
                      <div className="w-12 h-12 rounded-lg overflow-hidden bg-slate-100 shrink-0 border border-slate-200">
                        <img
                          src={
                            hotel.main_image_url ||
                            "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=300&q=80"
                          }
                          alt={hotel.hotel_name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                          loading="lazy"
                        />
                      </div>
                      <div className="min-w-0">
                        <div
                          onClick={() => onOpenPassport(hotel.hotel_id)}
                          className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer text-xs line-clamp-1"
                          title={`${hotel.hotel_name} — открыть паспорт`}
                        >
                          {hotel.hotel_name}
                        </div>
                        <div className="flex items-center gap-0.5 text-amber-400 text-[10px] mt-0.5">
                          {Array.from({ length: hotel.stars || 4 }).map((_, i) => (
                            <Star key={i} className="w-2.5 h-2.5 fill-current" />
                          ))}
                        </div>
                        <div className="flex items-center gap-1 mt-1 flex-wrap">
                          <span className="spec-badge spec-beach text-[9px]">🏖️ 1 линия</span>
                          {hotel.hotel_name.toLowerCase().includes("aqua") && (
                            <span className="spec-badge spec-aqua text-[9px]">🎢 Аквапарк</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Price */}
                  <td>
                    <div className="text-xs font-black text-slate-900 whitespace-nowrap">
                      {offer.total_price_pln.toLocaleString("ru-RU")} zł
                    </div>
                    <div className="text-[10px] text-slate-400">
                      {offer.price_per_night_pax} zł/ночь
                    </div>
                  </td>

                  {/* Deal Score */}
                  <td>
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${dealPillClass}`}>
                      {dealText}
                    </span>
                  </td>

                  {/* Forecast */}
                  <td style={{ textAlign: "center" }}>
                    {forecastPill}
                  </td>

                  {/* TripAdvisor */}
                  <td style={{ textAlign: "center" }}>
                    <div className="inline-flex items-center gap-0.5 text-emerald-800 font-extrabold text-[11px]">
                      <span>● {hotel.ta_rating ? hotel.ta_rating.toFixed(1) : "4.5"}</span>
                    </div>
                  </td>

                  {/* Δ 48ч */}
                  <td style={{ textAlign: "center" }}>
                    {delta48 > 0 ? (
                      <span className="delta-down text-xs">↓ −{delta48}%</span>
                    ) : (
                      <span className="delta-flat text-xs">—</span>
                    )}
                  </td>

                  {/* Δ к средней */}
                  <td style={{ textAlign: "center" }}>
                    {deltaAvg < 0 ? (
                      <span className="delta-down text-xs">↓ {deltaAvg}%</span>
                    ) : (
                      <span className="delta-flat text-xs">0%</span>
                    )}
                  </td>

                  {/* Region */}
                  <td className="text-xs text-slate-600 truncate">
                    {hotel.region || "Анталья"}
                  </td>

                  {/* Dates */}
                  <td>
                    <div className="text-[11px] font-semibold text-slate-800 whitespace-nowrap">
                      {offer.departure_date}
                    </div>
                    <div className="text-[10px] text-blue-600 font-bold">
                      {offer.airport}
                    </div>
                  </td>

                  {/* Duration */}
                  <td style={{ textAlign: "center" }} className="text-xs text-slate-700 font-medium">
                    {offer.duration_nights}н
                  </td>

                  {/* Actions / Links */}
                  <td>
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        type="button"
                        onClick={() => onOpenPassport(hotel.hotel_id)}
                        className="px-2 py-1 text-[11px] font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors whitespace-nowrap"
                        title="Открыть AI Паспорт отеля справа"
                      >
                        Паспорт
                      </button>

                      <button
                        type="button"
                        onClick={() => onToggleWatchlist(hotel)}
                        className={`p-1.5 rounded-lg border transition-colors ${
                          isWatched
                            ? "bg-amber-500 text-white border-amber-600"
                            : "bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200"
                        }`}
                        title={isWatched ? "В отслеживаемых" : "Поставить на радар"}
                      >
                        <Bell className="w-3 h-3" />
                      </button>

                      {offer.booking_url && (
                        <a
                          href={offer.booking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-blue-600 border border-slate-200 transition-colors"
                          title="Открыть на Fly.pl"
                        >
                          <ExternalLink className="w-3 h-3" />
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
