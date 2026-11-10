import React from "react";
import { ExternalLink, Star, ArrowUpDown, ArrowUp, ArrowDown, Bell } from "lucide-react";
import { SearchHotelItem } from "../types";
import { LoadingSpinner } from "./common/LoadingSpinner";

interface HotelTableViewProps {
  hotels: SearchHotelItem[];
  isLoading?: boolean;
  onOpenPassport: (hotelId: string) => void;
  onToggleWatchlist: (hotel: SearchHotelItem) => void;
  watchedCohortHashes: Set<string>;
  sortField: string;
  sortAsc: boolean;
  onSort: (field: string) => void;
}

export const HotelTableView: React.FC<HotelTableViewProps> = ({
  hotels,
  isLoading = false,
  onOpenPassport,
  onToggleWatchlist,
  watchedCohortHashes,
  sortField,
  sortAsc,
  onSort,
}) => {
  const renderSortIcon = (field: string) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 opacity-40 shrink-0" />;
    }
    return sortAsc ? (
      <ArrowUp className="w-3.5 h-3.5 text-blue-600 font-extrabold shrink-0" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-blue-600 font-extrabold shrink-0" />
    );
  };
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

      {/* Hotels Table or Full Skeleton */}
      {isLoading && hotels.length === 0 ? (
        <LoadingSpinner
          variant="skeleton-table"
          label="Загрузка каталога отелей..."
          description="Вычисляем актуальный Deal Score, 48ч динамику и исторический минимум"
        />
      ) : (
        <div className="hotels-table-container relative">
          {isLoading && (
            <LoadingSpinner
              variant="overlay"
              size="lg"
              label="Обновление каталога отелей..."
              description="Синхронизация котировок и пересчёт Deal Score"
            />
          )}
          <table className="hotels-table" id="hotelsTable">
          <thead>
            <tr className="bg-sky-50/80 border-b border-sky-100 text-sky-900 text-xs uppercase tracking-wider font-extrabold select-none">
              <th
                onClick={() => onSort("hotel")}
                className="cursor-pointer hover:text-blue-900 pl-4 py-3 rounded-l-xl transition-colors min-w-[280px]"
                style={{ width: "22%" }}
              >
                <div className="flex items-center gap-1.5">
                  <span>ОТЕЛЬ</span>
                  {renderSortIcon("hotel")}
                </div>
              </th>
              <th
                onClick={() => onSort("price")}
                className="cursor-pointer hover:text-blue-900 py-3 transition-colors min-w-[130px]"
                style={{ width: "12%" }}
              >
                <div className="flex items-center gap-1.5">
                  <span>ЦЕНА</span>
                  {renderSortIcon("price")}
                </div>
              </th>
              <th
                onClick={() => onSort("deal_score")}
                className="cursor-pointer hover:text-blue-900 py-3 transition-colors min-w-[125px]"
                style={{ width: "10%" }}
              >
                <div className="flex items-center gap-1.5">
                  <span>DEAL SCORE</span>
                  {renderSortIcon("deal_score")}
                </div>
              </th>
              <th style={{ width: "10%", textAlign: "center" }} className="py-3 min-w-[115px]">
                ПРОГНОЗ
              </th>
              <th
                onClick={() => onSort("ta_rating")}
                className="cursor-pointer hover:text-blue-900 py-3 text-center transition-colors min-w-[105px]"
                style={{ width: "8%" }}
                title="Рейтинг отеля на TripAdvisor"
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span className="font-extrabold text-[11px] tracking-tight text-emerald-800 bg-emerald-100/90 px-2 py-0.5 rounded-md border border-emerald-300">
                    TripAdvisor
                  </span>
                  {renderSortIcon("ta_rating")}
                </div>
              </th>
              <th
                onClick={() => onSort("delta48")}
                className="cursor-pointer hover:text-blue-900 py-3 text-center transition-colors min-w-[100px]"
                style={{ width: "7%" }}
                title="Изменение цены за последние 48 часов"
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span>Δ 48Ч</span>
                  {renderSortIcon("delta48")}
                </div>
              </th>
              <th
                onClick={() => onSort("delta_avg")}
                className="cursor-pointer hover:text-blue-900 py-3 text-center transition-colors min-w-[110px]"
                style={{ width: "7%" }}
                title="Отклонение от типичной (плато) средней цены отеля"
              >
                <div className="flex items-center justify-center gap-1.5">
                  <span>Δ К СРЕДНЕЙ</span>
                  {renderSortIcon("delta_avg")}
                </div>
              </th>
              <th style={{ width: "8%" }} className="py-3 min-w-[90px]">
                РЕГИОН
              </th>
              <th style={{ width: "10%" }} className="py-3 min-w-[125px]">
                ДАТЫ
              </th>
              <th style={{ width: "5%", textAlign: "center" }} className="py-3 min-w-[70px]">
                ДЛИТ.
              </th>
              <th style={{ width: "14%", textAlign: "right" }} className="py-3 pr-4 rounded-r-xl min-w-[195px]">
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

              // Forecast tip & pill
              const forecastTip = intel.recommendation
                ? `Прогноз Hopper AI: ${intel.recommendation}`
                : intel.deal_score >= 80
                ? "Прогноз Hopper AI: Рекомендуется покупать сейчас. Цена находится на выгодном уровне."
                : intel.deal_score < 45 || intel.hopper_verdict === "OVERPRICED"
                ? "Прогноз Hopper AI: Цена завышена относительно истории. Рекомендуется подождать снижения."
                : "Прогноз Hopper AI: Обычный уровень цен. Спешить с бронированием не требуется.";

              let forecastPill = (
                <span className="hopper-pill wait" data-tip={forecastTip}>🟡 ЖДАТЬ</span>
              );
              if (intel.deal_score >= 80) {
                forecastPill = (
                  <span className="hopper-pill buy-now" data-tip={forecastTip}>🟢 ПОКУПАТЬ</span>
                );
              } else if (intel.hopper_verdict === "OVERPRICED" || intel.deal_score < 45) {
                forecastPill = (
                  <span className="hopper-pill overpriced" data-tip={forecastTip}>🔴 ДОРОГО</span>
                );
              }

              // Delta values
              const delta48 = intel.drop_48h_pct;
              const deltaAvg = intel.delta_vs_typical_pct !== undefined ? intel.delta_vs_typical_pct : 0;

              return (
                <tr
                  key={offer.cohort_hash}
                  onClick={() => onOpenPassport(hotel.hotel_id)}
                  className="group cursor-pointer hover:bg-sky-50/60 transition-colors"
                >
                  {/* Hotel Cell */}
                  <td className="pl-4">
                    <div className="flex items-center gap-3.5">
                      <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl overflow-hidden bg-slate-100 shrink-0 border border-slate-200/90 shadow-xs">
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
                          className="font-black text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer text-[15px] sm:text-[16.5px] leading-snug line-clamp-1 tracking-tight"
                          title={`${hotel.hotel_name} — открыть паспорт`}
                        >
                          {hotel.hotel_name}
                        </div>
                        <div className="flex items-center gap-1 text-amber-400 mt-1">
                          {Array.from({ length: hotel.stars || 4 }).map((_, i) => (
                            <Star key={i} className="w-3.5 h-3.5 fill-current" />
                          ))}
                        </div>
                        <div className="flex items-center gap-2 mt-2 flex-wrap">
                          <span className="spec-badge spec-beach text-[11.5px] font-extrabold px-2 py-0.5 rounded-lg border border-sky-200">
                            🏖️ {hotel.beach_line || hotel.specs?.beach_line || 1} линия
                          </span>
                          {(hotel.has_aquapark || hotel.specs?.has_aquapark || hotel.hotel_name.toLowerCase().includes("aqua")) && (
                            <span className="spec-badge spec-aqua text-[11.5px] font-extrabold px-2 py-0.5 rounded-lg border border-cyan-200">🎢 Аквапарк</span>
                          )}
                          {(hotel.has_heated_pools || hotel.specs?.has_heated_pools) && (
                            <span className="spec-badge text-[11.5px] font-extrabold px-2 py-0.5 rounded-lg bg-amber-50 text-amber-700 border border-amber-200">🔥 Подогрев</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Price */}
                  <td className="whitespace-nowrap px-3">
                    <div className="text-[18px] sm:text-[21px] font-black text-slate-900 whitespace-nowrap tracking-tight">
                      {offer.total_price_pln.toLocaleString("ru-RU")} zł
                    </div>
                    <div className="text-[13px] text-slate-500 font-bold mt-0.5">
                      {offer.price_per_night_pax} zł/ночь
                    </div>
                  </td>

                  {/* Deal Score */}
                  <td className="whitespace-nowrap px-3">
                    <span className={`text-[13px] sm:text-[14px] font-black px-3.5 py-1.5 rounded-full border shadow-2xs whitespace-nowrap ${dealPillClass}`}>
                      {dealText}
                    </span>
                  </td>

                  {/* Forecast */}
                  <td style={{ textAlign: "center" }} className="whitespace-nowrap px-2">
                    <div className="text-[12.5px] font-black">
                      {forecastPill}
                    </div>
                  </td>

                  {/* TripAdvisor */}
                  <td style={{ textAlign: "center" }} className="whitespace-nowrap px-2">
                    <div className="inline-flex items-center gap-1 text-emerald-900 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-300 font-extrabold text-[12.5px] shadow-2xs" title={`TripAdvisor: ${hotel.ta_rating ? hotel.ta_rating.toFixed(1) : "4.5"}/5`}>
                      <span className="text-emerald-600 font-black">★</span>
                      <span>{hotel.ta_rating ? hotel.ta_rating.toFixed(1) : "4.5"}</span>
                    </div>
                  </td>

                  {/* Δ 48ч */}
                  <td style={{ textAlign: "center" }} className="whitespace-nowrap px-2">
                    {delta48 < 0 ? (
                      <span className="delta-badge-down inline-flex items-center justify-center gap-1 whitespace-nowrap text-[12.5px] font-black px-2.5 py-1 rounded-lg text-emerald-700 bg-emerald-50 border border-emerald-200 shadow-2xs select-none">
                        <span>↓</span>
                        <span>{delta48.toFixed(1)}%</span>
                      </span>
                    ) : delta48 > 0 ? (
                      <span className="delta-badge-up inline-flex items-center justify-center gap-1 whitespace-nowrap text-[12.5px] font-black px-2.5 py-1 rounded-lg text-rose-700 bg-rose-50 border border-rose-200 shadow-2xs select-none">
                        <span>↑</span>
                        <span>+{delta48.toFixed(1)}%</span>
                      </span>
                    ) : (
                      <span className="text-[13px] font-bold text-slate-400 select-none">—</span>
                    )}
                  </td>

                  {/* Δ к средней */}
                  <td style={{ textAlign: "center" }} className="whitespace-nowrap px-2">
                    {deltaAvg < 0 ? (
                      <span className="delta-badge-down inline-flex items-center justify-center gap-1 whitespace-nowrap text-[12.5px] font-black px-2.5 py-1 rounded-lg text-emerald-700 bg-emerald-50 border border-emerald-200 shadow-2xs select-none">
                        <span>↓</span>
                        <span>{deltaAvg.toFixed(1)}%</span>
                      </span>
                    ) : deltaAvg > 0 ? (
                      <span className="delta-badge-up inline-flex items-center justify-center gap-1 whitespace-nowrap text-[12.5px] font-black px-2.5 py-1 rounded-lg text-rose-700 bg-rose-50 border border-rose-200 shadow-2xs select-none">
                        <span>↑</span>
                        <span>+{deltaAvg.toFixed(1)}%</span>
                      </span>
                    ) : (
                      <span className="text-[13px] font-bold text-slate-400 select-none">0%</span>
                    )}
                  </td>

                  {/* Region */}
                  <td className="text-[13px] font-bold text-slate-700 truncate px-2">
                    {hotel.region || "Анталья"}
                  </td>

                  {/* Dates */}
                  <td className="whitespace-nowrap px-3">
                    <div className="text-[13.5px] font-black text-slate-900 whitespace-nowrap">
                      {offer.departure_date}
                    </div>
                    <div className="text-[12px] text-blue-700 font-black bg-blue-50 border border-blue-100 px-2 py-0.5 rounded-md inline-block uppercase tracking-wide mt-1">
                      {offer.airport}
                    </div>
                  </td>

                  {/* Duration */}
                  <td style={{ textAlign: "center" }} className="whitespace-nowrap px-2">
                    <span className="inline-flex items-center justify-center text-[13px] font-black text-slate-800 bg-slate-100 px-3 py-1.5 rounded-xl border border-slate-200 whitespace-nowrap select-none">
                      {offer.duration_nights}н
                    </span>
                  </td>

                  {/* Actions / Links */}
                  <td className="whitespace-nowrap pr-4 pl-2 text-right">
                    <div className="inline-flex items-center justify-end gap-2 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenPassport(hotel.hotel_id);
                        }}
                        className="px-3.5 py-2 text-[13px] font-black text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl border border-blue-200 shadow-2xs hover:shadow-xs transition-all whitespace-nowrap cursor-pointer"
                        title="Открыть AI Паспорт отеля справа"
                      >
                        Паспорт
                      </button>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onToggleWatchlist(hotel);
                        }}
                        className={`p-2.5 rounded-xl border transition-all cursor-pointer ${
                          isWatched
                            ? "bg-amber-500 text-white border-amber-600 shadow-xs"
                            : "bg-slate-50 hover:bg-slate-100 text-slate-600 border-slate-200"
                        }`}
                        title={isWatched ? "В отслеживаемых" : "Поставить на радар"}
                      >
                        <Bell className="w-4 h-4" />
                      </button>

                      {offer.booking_url && (
                        <a
                          href={offer.booking_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-blue-600 border border-slate-200 shadow-2xs transition-all cursor-pointer"
                          title="Открыть на Fly.pl"
                        >
                          <ExternalLink className="w-4 h-4" />
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
      )}
    </div>
  );
};
