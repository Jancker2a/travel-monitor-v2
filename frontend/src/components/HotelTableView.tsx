import React, { useState, useMemo } from "react";
import {
  ExternalLink,
  Search,
  Sparkles,
  Flame,
  Star,
  SlidersHorizontal,
  Table as TableIcon,
  LayoutGrid,
  CheckCircle2,
  Bell,
  ArrowUpDown,
} from "lucide-react";
import { SearchHotelItem } from "../types";

interface HotelTableViewProps {
  hotels: SearchHotelItem[];
  onOpenPassport: (hotelId: string) => void;
  onToggleWatchlist: (hotel: SearchHotelItem) => void;
  watchedCohortHashes: Set<string>;
  viewMode: "table" | "cards";
  onViewModeChange: (mode: "table" | "cards") => void;
}

export const HotelTableView: React.FC<HotelTableViewProps> = ({
  hotels,
  onOpenPassport,
  onToggleWatchlist,
  watchedCohortHashes,
  viewMode,
  onViewModeChange,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [activeFilterTag, setActiveFilterTag] = useState<string>("all");
  const [sortField, setSortField] = useState<"price" | "deal_score" | "ta_rating" | "stars">("price");
  const [sortAsc, setSortAsc] = useState(true);

  // Filter and sort items
  const filteredAndSortedHotels = useMemo(() => {
    let result = hotels.filter((h) => {
      const matchSearch =
        h.hotel_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (h.region && h.region.toLowerCase().includes(searchTerm.toLowerCase()));

      if (!matchSearch) return false;

      if (activeFilterTag === "buy_now") {
        return h.intelligence.deal_score >= 80;
      }
      if (activeFilterTag === "stars_5") {
        return h.stars >= 5;
      }
      if (activeFilterTag === "beach") {
        return (
          h.specs?.beach_line === 1 ||
          h.hotel_name.toLowerCase().includes("beach") ||
          h.hotel_name.toLowerCase().includes("resort")
        );
      }
      if (activeFilterTag === "aquapark") {
        return (
          h.specs?.aquapark ||
          h.hotel_name.toLowerCase().includes("aqua") ||
          h.hotel_name.toLowerCase().includes("park")
        );
      }
      if (activeFilterTag === "kids") {
        return h.specs?.kids_facilities || h.stars >= 4;
      }

      return true;
    });

    result.sort((a, b) => {
      let diff = 0;
      if (sortField === "price") {
        diff = a.current_offer.total_price_pln - b.current_offer.total_price_pln;
      } else if (sortField === "deal_score") {
        diff = b.intelligence.deal_score - a.intelligence.deal_score;
      } else if (sortField === "ta_rating") {
        diff = (b.ta_rating || 0) - (a.ta_rating || 0);
      } else if (sortField === "stars") {
        diff = b.stars - a.stars;
      }
      return sortAsc ? diff : -diff;
    });

    return result;
  }, [hotels, searchTerm, activeFilterTag, sortField, sortAsc]);

  const handleSort = (field: "price" | "deal_score" | "ta_rating" | "stars") => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === "price");
    }
  };

  return (
    <div className="space-y-4">
      {/* Table Toolbar & View Switcher */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 bg-white p-3.5 rounded-2xl border border-slate-200/90 shadow-sm">
        {/* Quick Search Input */}
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            id="tableSearchInput"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Быстрый поиск по названию или региону..."
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-500 text-slate-900 placeholder:text-slate-400 font-medium"
          />
        </div>

        {/* Filter Quick Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1">
          <button
            type="button"
            onClick={() => setActiveFilterTag("all")}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              activeFilterTag === "all"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            Все ({hotels.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveFilterTag("buy_now")}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap flex items-center gap-1 transition-colors ${
              activeFilterTag === "buy_now"
                ? "bg-emerald-600 text-white"
                : "bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100"
            }`}
          >
            <Flame className="w-3 h-3 fill-current text-amber-400" />
            <span>🔥 Buy Now (80+)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveFilterTag("beach")}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              activeFilterTag === "beach"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            🏖️ 1-я линия
          </button>
          <button
            type="button"
            onClick={() => setActiveFilterTag("aquapark")}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              activeFilterTag === "aquapark"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            🎢 Аквапарк
          </button>
          <button
            type="button"
            onClick={() => setActiveFilterTag("stars_5")}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors ${
              activeFilterTag === "stars_5"
                ? "bg-blue-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            ⭐ Только 5★
          </button>
        </div>

        {/* View Mode Switcher (Табличный вид vs Карточный вид) */}
        <div className="flex items-center justify-between lg:justify-end gap-3 pt-2 lg:pt-0 border-t lg:border-t-0 border-slate-100">
          <div className="mode-switch-box">
            <button
              type="button"
              onClick={() => onViewModeChange("table")}
              className={`mode-btn ${viewMode === "table" ? "active" : ""}`}
              id="modeBtnTable"
            >
              <TableIcon className="w-3.5 h-3.5" />
              <span>Таблица</span>
            </button>
            <button
              type="button"
              onClick={() => onViewModeChange("cards")}
              className={`mode-btn ${viewMode === "cards" ? "active" : ""}`}
              id="modeBtnCards"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
              <span>Карточки</span>
            </button>
          </div>
        </div>
      </div>

      {/* Counter bar */}
      <div className="flex items-center justify-between text-xs text-slate-500 px-1 font-medium">
        <div>
          Показано: <b className="text-slate-800">{filteredAndSortedHotels.length}</b> из {hotels.length} предложений
        </div>
        <div className="text-[11px] text-slate-400">
          Цены перепроверяются каждый час круглосуточно
        </div>
      </div>

      {/* Table Mode */}
      {viewMode === "table" && (
        <div className="hotels-table-container">
          <table className="hotels-table" id="hotelsTable">
            <thead>
              <tr>
                <th
                  onClick={() => handleSort("stars")}
                  className="cursor-pointer hover:text-blue-800"
                  style={{ width: "28%" }}
                >
                  <div className="flex items-center gap-1">
                    <span>Отель / Категория</span>
                    <ArrowUpDown className="w-3 h-3 opacity-60" />
                  </div>
                </th>
                <th style={{ width: "16%" }}>Питание / Номер</th>
                <th style={{ width: "16%" }}>Вылет / Даты</th>
                <th
                  onClick={() => handleSort("ta_rating")}
                  className="cursor-pointer hover:text-blue-800"
                  style={{ width: "11%" }}
                >
                  <div className="flex items-center gap-1">
                    <span>TripAdvisor</span>
                    <ArrowUpDown className="w-3 h-3 opacity-60" />
                  </div>
                </th>
                <th style={{ width: "9%", textAlign: "center" }}>Δ 48ч</th>
                <th
                  onClick={() => handleSort("price")}
                  className="cursor-pointer hover:text-blue-800"
                  style={{ width: "12%" }}
                >
                  <div className="flex items-center gap-1">
                    <span>Цена (PLN)</span>
                    <ArrowUpDown className="w-3 h-3 opacity-60" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort("deal_score")}
                  className="cursor-pointer hover:text-blue-800"
                  style={{ width: "14%" }}
                >
                  <div className="flex items-center gap-1">
                    <span>Hopper Deal</span>
                    <ArrowUpDown className="w-3 h-3 opacity-60" />
                  </div>
                </th>
                <th style={{ width: "14%", textAlign: "right" }}>Действия</th>
              </tr>
            </thead>
            <tbody>
              {filteredAndSortedHotels.map((hotel) => {
                const offer = hotel.current_offer;
                const intel = hotel.intelligence;
                const isWatched = watchedCohortHashes.has(offer.cohort_hash);

                // Hopper pill classes
                let hopperCls = "hopper-pill wait";
                let hopperText = `⏳ WAIT (${intel.deal_score})`;
                if (intel.deal_score >= 80) {
                  hopperCls = "hopper-pill buy-now";
                  hopperText = `🟢 BUY NOW (${intel.deal_score})`;
                } else if (intel.hopper_verdict === "OVERPRICED" || intel.deal_score < 45) {
                  hopperCls = "hopper-pill overpriced";
                  hopperText = `🔴 ДОРОГО (${intel.deal_score})`;
                }

                // Delta 48h
                const deltaDrop = intel.drop_48h_pct;

                return (
                  <tr key={offer.cohort_hash} className="group">
                    {/* Hotel Name & Category */}
                    <td>
                      <div className="flex items-start gap-3">
                        <div className="w-14 h-14 rounded-xl overflow-hidden bg-slate-100 shrink-0 border border-slate-200/80 shadow-sm">
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
                          <div className="flex items-center gap-1 text-amber-400 text-xs">
                            {Array.from({ length: hotel.stars || 4 }).map((_, i) => (
                              <Star key={i} className="w-3 h-3 fill-current" />
                            ))}
                          </div>
                          <div
                            onClick={() => onOpenPassport(hotel.hotel_id)}
                            className="font-bold text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer text-sm line-clamp-1"
                            title={hotel.hotel_name}
                          >
                            {hotel.hotel_name}
                          </div>
                          <div className="text-[11px] text-slate-500 truncate">
                            {hotel.region || hotel.country}
                          </div>

                          {/* Amenity / Spec Badges */}
                          <div className="flex items-center gap-1 mt-1 flex-wrap">
                            <span className="spec-badge spec-beach">🏖️ 1 линия</span>
                            {hotel.hotel_name.toLowerCase().includes("aqua") && (
                              <span className="spec-badge spec-aqua">🎢 Аквапарк</span>
                            )}
                            <span className="spec-badge spec-kids">👶 Дети</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Board & Room */}
                    <td>
                      <div className="text-xs font-bold text-slate-800">
                        All Inclusive
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Стандартный номер
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        {offer.operator || "Корал / ТУИ"}
                      </div>
                    </td>

                    {/* Airport & Dates */}
                    <td>
                      <div className="flex items-center gap-1.5">
                        <span className="font-extrabold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded text-[10px] border border-blue-200">
                          {offer.airport}
                        </span>
                        <span className="text-xs font-semibold text-slate-800">
                          {offer.departure_date}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5">
                        {offer.duration_nights} ночей в туре
                      </div>
                    </td>

                    {/* TripAdvisor */}
                    <td>
                      <div className="inline-flex items-center gap-1 bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-200 text-emerald-800 font-bold text-xs">
                        <span>● {hotel.ta_rating ? hotel.ta_rating.toFixed(1) : "4.5"}</span>
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        {hotel.ta_reviews ? `${hotel.ta_reviews} отзывов` : "1 250 отзывов"}
                      </div>
                    </td>

                    {/* 24h Delta */}
                    <td style={{ textAlign: "center" }}>
                      {deltaDrop > 0 ? (
                        <div className="delta-down text-xs font-extrabold">
                          ↓ −{deltaDrop}%
                        </div>
                      ) : (
                        <div className="delta-flat text-xs">—</div>
                      )}
                    </td>

                    {/* Price PLN */}
                    <td>
                      <div className="text-sm font-black text-slate-900 whitespace-nowrap">
                        {offer.total_price_pln.toLocaleString("ru-RU")} zł
                      </div>
                      <div className="text-[10px] text-slate-500 font-medium">
                        {offer.price_per_night_pax ? `${offer.price_per_night_pax} zł/ночь` : "за тур"}
                      </div>
                    </td>

                    {/* Hopper Pill */}
                    <td>
                      <div className={hopperCls} title={intel.recommendation}>
                        {hopperText}
                      </div>
                    </td>

                    {/* Actions */}
                    <td>
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          onClick={() => onOpenPassport(hotel.hotel_id)}
                          className="px-2.5 py-1 text-xs font-bold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors whitespace-nowrap shadow-xs"
                          title="Открыть AI Паспорт с полной историей цен и Hopper анализом"
                        >
                          AI Паспорт
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
                          <Bell className="w-3.5 h-3.5" />
                        </button>

                        {offer.booking_url && (
                          <a
                            href={offer.booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-blue-600 border border-slate-200 transition-colors"
                            title="Открыть тур на Fly.pl"
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
      )}
    </div>
  );
};
