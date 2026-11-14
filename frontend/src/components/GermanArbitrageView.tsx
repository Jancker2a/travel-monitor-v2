import React, { useState, useEffect, useMemo } from "react";
import {
  Plane,
  TrendingDown,
  ArrowRight,
  ExternalLink,
  RefreshCw,
  Star,
  Users,
  Calendar,
  Table as TableIcon,
  LayoutGrid,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  X,
  Building2,
  Sparkles,
} from "lucide-react";
import { getArbitrageDeals } from "../services/api";
import { LoadingSpinner } from "./common/LoadingSpinner";

export interface ArbitrageDeal {
  hotel_id: string;
  hotel_name: string;
  german_hotel_name?: string;
  similarity_score?: number;
  country: string;
  stars: number;
  main_image_url?: string;
  checkin_date: string;
  duration_nights: number;
  german_duration_nights?: number;
  adults: number;
  children: number;
  berlin_airport: string;
  berlin_price_pln: number;
  berlin_operator: string;
  berlin_booking_url: string;
  polish_airport: string;
  polish_price_pln: number;
  polish_operator: string;
  polish_booking_url?: string;
  friction_pln: number;
  savings_pln: number;
  savings_pct: number;
  verdict: string;
}

export interface GermanArbitrageViewProps {
  filterId?: string | null;
  country?: string | null;
  filterTitle?: string | null;
  onOpenPassport?: (hotelId: string) => void;
  onToggleWatchlist?: (deal: ArbitrageDeal) => void;
  watchedCohortHashes?: Set<string>;
}

type SortField =
  | "savings_pln"
  | "savings_pct"
  | "berlin_price"
  | "polish_price"
  | "checkin_date"
  | "hotel_name";

export const GermanArbitrageView: React.FC<GermanArbitrageViewProps> = ({
  filterId,
  country,
  filterTitle,
  onOpenPassport,
  onToggleWatchlist,
  watchedCohortHashes,
}) => {
  const [deals, setDeals] = useState<ArbitrageDeal[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [minSavings, setMinSavings] = useState(300);

  // View mode: Table (default) vs Cards
  const [viewMode, setViewMode] = useState<"table" | "cards">("table");

  // Filtering states
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCountry, setSelectedCountry] = useState("all");
  const [selectedAirport, setSelectedAirport] = useState("all");
  const [selectedStars, setSelectedStars] = useState("all");

  // Sorting state (default: maximum net savings first)
  const [sortField, setSortField] = useState<SortField>("savings_pln");
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const loadDeals = async () => {
    setIsLoading(true);
    try {
      const data = await getArbitrageDeals(minSavings, filterId, country);
      setDeals(data);
    } catch (err) {
      console.error("Failed to load arbitrage deals:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDeals();
  }, [minSavings, filterId, country]);

  // Dynamically extract unique countries and Polish airports
  const availableCountries = useMemo(() => {
    const set = new Set<string>();
    deals.forEach((d) => {
      if (d.country) set.add(d.country);
    });
    return Array.from(set).sort();
  }, [deals]);

  const availableAirports = useMemo(() => {
    const set = new Set<string>();
    deals.forEach((d) => {
      if (d.polish_airport) set.add(d.polish_airport);
    });
    return Array.from(set).sort();
  }, [deals]);

  // Filtered deals
  const filteredDeals = useMemo(() => {
    return deals.filter((deal) => {
      // Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const hotelMatch = deal.hotel_name.toLowerCase().includes(q);
        const germanMatch = deal.german_hotel_name?.toLowerCase().includes(q) ?? false;
        const countryMatch = deal.country.toLowerCase().includes(q);
        const airportMatch = deal.polish_airport.toLowerCase().includes(q);
        const operatorMatch =
          deal.polish_operator.toLowerCase().includes(q) ||
          deal.berlin_operator.toLowerCase().includes(q);
        if (!hotelMatch && !germanMatch && !countryMatch && !airportMatch && !operatorMatch) {
          return false;
        }
      }

      // Country filter
      if (selectedCountry !== "all" && deal.country !== selectedCountry) {
        return false;
      }

      // Airport filter
      if (selectedAirport !== "all" && deal.polish_airport !== selectedAirport) {
        return false;
      }

      // Stars filter
      if (selectedStars !== "all") {
        const starVal = Number(selectedStars);
        if (starVal === 5 && deal.stars !== 5) return false;
        if (starVal === 4 && deal.stars < 4) return false;
        if (starVal === 3 && deal.stars < 3) return false;
      }

      return true;
    });
  }, [deals, searchQuery, selectedCountry, selectedAirport, selectedStars]);

  // Sorted deals
  const sortedDeals = useMemo(() => {
    const list = [...filteredDeals];
    list.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "savings_pln":
          cmp = a.savings_pln - b.savings_pln;
          break;
        case "savings_pct":
          cmp = a.savings_pct - b.savings_pct;
          break;
        case "berlin_price":
          cmp = a.berlin_price_pln - b.berlin_price_pln;
          break;
        case "polish_price":
          cmp = a.polish_price_pln - b.polish_price_pln;
          break;
        case "checkin_date":
          cmp = a.checkin_date.localeCompare(b.checkin_date);
          break;
        case "hotel_name":
          cmp = a.hotel_name.localeCompare(b.hotel_name);
          break;
      }
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [filteredDeals, sortField, sortAsc]);

  // Handle column header clicks
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      // Sensible default direction: savings/savings_pct desc, prices asc, names asc, dates asc
      if (field === "savings_pln" || field === "savings_pct") {
        setSortAsc(false);
      } else {
        setSortAsc(true);
      }
    }
  };

  const renderSortIndicator = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 opacity-35 shrink-0 inline-block ml-1" />;
    }
    return sortAsc ? (
      <ArrowUp className="w-3.5 h-3.5 text-blue-600 font-extrabold shrink-0 inline-block ml-1" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-blue-600 font-extrabold shrink-0 inline-block ml-1" />
    );
  };

  const isFiltered =
    searchQuery.trim() !== "" ||
    selectedCountry !== "all" ||
    selectedAirport !== "all" ||
    selectedStars !== "all";

  const handleClearFilters = () => {
    setSearchQuery("");
    setSelectedCountry("all");
    setSelectedAirport("all");
    setSelectedStars("all");
  };

  // Check if deal is watched in watchlist
  const isDealWatched = (deal: ArbitrageDeal): boolean => {
    if (!watchedCohortHashes) return false;
    const syntheticHash = `arb_${deal.hotel_id}_${deal.checkin_date}_${deal.duration_nights}`;
    return watchedCohortHashes.has(syntheticHash) || watchedCohortHashes.has(deal.hotel_id);
  };

  const totalSavingsSum = useMemo(() => {
    return sortedDeals.reduce((sum, d) => sum + (d.savings_pln || 0), 0);
  }, [sortedDeals]);

  return (
    <div className="space-y-5">
      {/* 1. Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-5 sm:p-6 rounded-3xl shadow-lg border border-slate-800">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-2xl">🇩🇪</span>
              <h2 className="text-lg sm:text-xl font-black tracking-tight text-white">
                НЕМЕЦКИЙ АРБИТРАЖ (БЕРЛИН BER vs ПОЛЬША)
              </h2>
              <span className="text-[10px] font-extrabold bg-amber-400 text-slate-950 px-2 py-0.5 rounded-full shadow-xs">
                CROSS-BORDER RADAR
              </span>
              {country && (
                <span className="text-[11px] font-bold bg-blue-500/20 text-blue-300 border border-blue-400/30 px-2.5 py-0.5 rounded-full">
                  {country}
                </span>
              )}
              {deals.length > 0 && (
                <span className="text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 px-2.5 py-0.5 rounded-full">
                  {deals.length} спредов цен
                </span>
              )}
            </div>
            <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
              {filterTitle ? `${filterTitle} • ` : ""}
              Сравнение идентичных отелей, дат вылета и состава туристов при вылете из Берлина (Check24 / TUI) против аэропортов Польши с учетом расходов на дорогу до Берлина (-250 zł).
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0 self-start lg:self-center">
            <div className="flex items-center gap-2 text-xs bg-slate-800/90 px-3 py-1.5 rounded-xl border border-slate-700 shadow-xs">
              <span className="text-slate-400 font-semibold">Мин. выгода:</span>
              <select
                value={minSavings}
                onChange={(e) => setMinSavings(Number(e.target.value))}
                className="bg-transparent text-amber-400 font-bold focus:outline-none cursor-pointer"
              >
                <option value="100" className="bg-slate-900 text-white">от 100 zł</option>
                <option value="300" className="bg-slate-900 text-white">от 300 zł</option>
                <option value="500" className="bg-slate-900 text-white">от 500 zł</option>
                <option value="1000" className="bg-slate-900 text-white">от 1 000 zł</option>
                <option value="2000" className="bg-slate-900 text-white">от 2 000 zł</option>
              </select>
            </div>

            <button
              onClick={loadDeals}
              disabled={isLoading}
              className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white transition-colors border border-slate-700 shadow-xs cursor-pointer disabled:opacity-50"
              title="Обновить предложения"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-400" : ""}`} />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Controls Toolbar: View Switcher, Search, Filters & Sorting */}
      <div className="bg-white p-3.5 sm:p-4 rounded-2xl border border-slate-200 shadow-xs space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          {/* View Mode Toggle: Таблица vs Карточки */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-extrabold text-slate-500 uppercase tracking-wider">
              Режим:
            </span>
            <div className="inline-flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
              <button
                id="arbModeTable"
                type="button"
                onClick={() => setViewMode("table")}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  viewMode === "table"
                    ? "bg-white text-blue-700 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <TableIcon className="w-3.5 h-3.5" />
                <span>Таблица</span>
              </button>
              <button
                id="arbModeCards"
                type="button"
                onClick={() => setViewMode("cards")}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  viewMode === "cards"
                    ? "bg-white text-blue-700 shadow-xs"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span>Карточки</span>
              </button>
            </div>
          </div>

          {/* Quick Counter */}
          <div className="text-xs font-semibold text-slate-600 flex items-center gap-2">
            <span>
              Показано: <b className="text-slate-900 font-extrabold">{sortedDeals.length}</b> из {deals.length}
            </span>
            {sortedDeals.length > 0 && totalSavingsSum > 0 && (
              <span className="hidden sm:inline-block text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-md font-bold border border-emerald-200">
                Экономия до {totalSavingsSum.toLocaleString("ru-RU")} zł
              </span>
            )}
          </div>
        </div>

        {/* Filter Inputs Row */}
        <div className="flex items-center gap-2.5 flex-wrap pt-1 border-t border-slate-100">
          {/* Search Input */}
          <div className="relative min-w-[200px] flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 Поиск по отелю, туроператору или городу..."
              className="w-full pl-3.5 pr-8 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium text-slate-900"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Country Filter */}
          <select
            value={selectedCountry}
            onChange={(e) => setSelectedCountry(e.target.value)}
            className="text-xs sm:text-sm py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer"
          >
            <option value="all">Все страны</option>
            {availableCountries.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          {/* Polish Departure Airport Filter */}
          <select
            value={selectedAirport}
            onChange={(e) => setSelectedAirport(e.target.value)}
            className="text-xs sm:text-sm py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer"
          >
            <option value="all">Все аэропорты Польши</option>
            {availableAirports.map((ap) => (
              <option key={ap} value={ap}>
                🇵🇱 {ap}
              </option>
            ))}
          </select>

          {/* Stars Filter */}
          <select
            value={selectedStars}
            onChange={(e) => setSelectedStars(e.target.value)}
            className="text-xs sm:text-sm py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer"
          >
            <option value="all">Все звёзды</option>
            <option value="5">5★ отели</option>
            <option value="4">4★ и выше</option>
            <option value="3">3★ и выше</option>
          </select>

          {/* Sort By Select */}
          <select
            value={`${sortField}_${sortAsc ? "asc" : "desc"}`}
            onChange={(e) => {
              const [f, d] = e.target.value.split("_");
              setSortField(f as SortField);
              setSortAsc(d === "asc");
            }}
            className="text-xs sm:text-sm py-2 px-3 bg-slate-50 border border-slate-200 rounded-xl font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer"
          >
            <option value="savings_pln_desc">💰 Выгода zł (макс сначала)</option>
            <option value="savings_pln_asc">💰 Выгода zł (мин сначала)</option>
            <option value="savings_pct_desc">📉 Скидка % (макс сначала)</option>
            <option value="berlin_price_asc">🇩🇪 Берлин (сначала дешевые)</option>
            <option value="berlin_price_desc">🇩🇪 Берлин (сначала дорогие)</option>
            <option value="polish_price_desc">🇵🇱 Польша (сначала дорогие)</option>
            <option value="polish_price_asc">🇵🇱 Польша (сначала дешевые)</option>
            <option value="checkin_date_asc">📅 Дата вылета (ранние)</option>
            <option value="checkin_date_desc">📅 Дата вылета (поздние)</option>
            <option value="hotel_name_asc">🏨 Название отеля (А-Я)</option>
          </select>

          {/* Clear Filters Button */}
          {isFiltered && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="text-xs font-bold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 px-3 py-2 rounded-xl transition-colors cursor-pointer border border-rose-200"
            >
              Сбросить
            </button>
          )}
        </div>
      </div>

      {/* 3. Main Content: Table View vs Cards View */}
      {isLoading ? (
        <LoadingSpinner
          variant="card"
          size="lg"
          label="Сканируем спреды цен Берлин vs Польша..."
          description="Поиск сопоставимых предложений немецких туроператоров с учетом состава пассажиров, дат и трансфера"
        />
      ) : sortedDeals.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 text-center border border-slate-200 shadow-sm max-w-xl mx-auto">
          <div className="text-4xl mb-3">🔍</div>
          <h3 className="text-base font-bold text-slate-800 mb-1">
            {deals.length === 0
              ? "Нет активных спредов цен для данного фильтра"
              : "По заданным условиям ничего не найдено"}
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed mb-4">
            {deals.length === 0
              ? `При строгом сопоставлении отелей, дат вылета и состава гостей с выгодой от ${minSavings} zł предложений не обнаружено.`
              : "Попробуйте изменить поисковый запрос, сбросить фильтры аэропорта или снизить порог выгоды."}
          </p>
          {isFiltered ? (
            <button
              onClick={handleClearFilters}
              className="text-xs font-bold text-blue-600 hover:text-blue-700 bg-blue-50 px-4 py-2 rounded-xl transition-colors cursor-pointer"
            >
              Сбросить фильтры
            </button>
          ) : (
            <button
              onClick={() => setMinSavings(100)}
              className="text-xs font-bold text-blue-600 hover:text-blue-700 bg-blue-50 px-4 py-2 rounded-xl transition-colors cursor-pointer"
            >
              Попробовать с порогом от 100 zł
            </button>
          )}
        </div>
      ) : viewMode === "table" ? (
        /* TABLE VIEW */
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/90 border-b border-slate-200 text-slate-600 text-xs uppercase tracking-wider font-extrabold select-none">
                  {/* Hotel & Rating */}
                  <th
                    onClick={() => handleSort("hotel_name")}
                    className="cursor-pointer hover:text-blue-700 pl-4 py-3.5 transition-colors min-w-[260px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>Отель & Направление</span>
                      {renderSortIndicator("hotel_name")}
                    </div>
                  </th>

                  {/* Dates & Party */}
                  <th
                    onClick={() => handleSort("checkin_date")}
                    className="cursor-pointer hover:text-blue-700 px-3 py-3.5 transition-colors min-w-[140px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>Даты & Ночи</span>
                      {renderSortIndicator("checkin_date")}
                    </div>
                  </th>

                  {/* Polish Departure */}
                  <th
                    onClick={() => handleSort("polish_price")}
                    className="cursor-pointer hover:text-blue-700 px-3 py-3.5 transition-colors min-w-[150px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>🇵🇱 Вылет из Польши</span>
                      {renderSortIndicator("polish_price")}
                    </div>
                  </th>

                  {/* Berlin Departure */}
                  <th
                    onClick={() => handleSort("berlin_price")}
                    className="cursor-pointer hover:text-blue-700 px-3 py-3.5 transition-colors min-w-[160px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>🇩🇪 Вылет из Берлина (BER)</span>
                      {renderSortIndicator("berlin_price")}
                    </div>
                  </th>

                  {/* Net Savings */}
                  <th
                    onClick={() => handleSort("savings_pln")}
                    className="cursor-pointer hover:text-blue-700 px-3 py-3.5 transition-colors min-w-[150px]"
                  >
                    <div className="flex items-center gap-1">
                      <span>Чистая выгода</span>
                      {renderSortIndicator("savings_pln")}
                    </div>
                  </th>

                  {/* Actions */}
                  <th className="pr-4 py-3.5 text-right min-w-[200px]">Действия</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-800">
                {sortedDeals.map((deal, idx) => {
                  const watched = isDealWatched(deal);
                  const isNearBottom = idx >= sortedDeals.length - 2 && sortedDeals.length > 3;
                  return (
                    <tr
                      key={`${deal.hotel_id}_${deal.checkin_date}_${idx}`}
                      className="hover:bg-blue-50/30 transition-colors group hover:relative hover:z-30"
                    >
                      {/* 1. Hotel thumbnail, name, stars, country */}
                      <td className="pl-4 py-3">
                        <div className="flex items-center gap-3.5">
                          {/* 104x70 Aspect 16:10 Image with Glass Overlay Star & Hover Zoom Popover */}
                          <div className="relative group/thumb shrink-0">
                            <div className="w-[104px] h-[70px] rounded-xl overflow-hidden bg-slate-100 border border-slate-200/90 shadow-2xs group-hover/thumb:shadow transition-shadow">
                              <img
                                src={
                                  deal.main_image_url ||
                                  "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=300&q=80"
                                }
                                alt={deal.hotel_name}
                                className="w-full h-full object-cover group-hover/thumb:scale-105 transition-transform duration-300"
                                loading="lazy"
                              />
                              {onToggleWatchlist && (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onToggleWatchlist(deal);
                                  }}
                                  className={`absolute top-1.5 left-1.5 p-1 rounded-lg transition-all cursor-pointer shadow-xs z-10 ${
                                    watched
                                      ? "bg-amber-400 text-slate-950 shadow-xs"
                                      : "bg-black/40 hover:bg-black/70 backdrop-blur-md text-amber-300 hover:text-amber-200"
                                  }`}
                                  title={watched ? "В избранном (нажмите для удаления)" : "Добавить в избранное"}
                                >
                                  <Star className={`w-3.5 h-3.5 ${watched ? "fill-slate-950 text-slate-950" : "fill-current"}`} />
                                </button>
                              )}
                            </div>

                            {/* Large Hover Zoom Popover */}
                            <div
                              className={`hidden group-hover/thumb:block absolute left-0 ${
                                isNearBottom ? "bottom-0" : "top-0"
                              } z-50 w-[360px] sm:w-[400px] rounded-2xl overflow-hidden bg-white shadow-2xl border-2 border-white ring-1 ring-slate-900/15 pointer-events-none transition-all duration-200 animate-in fade-in zoom-in-95`}
                            >
                              <div className="relative h-[240px] bg-slate-900">
                                <img
                                  src={
                                    deal.main_image_url ||
                                    "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=600&q=80"
                                  }
                                  alt={deal.hotel_name}
                                  className="w-full h-full object-cover"
                                />
                                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-black/30 pointer-events-none" />

                                <div className="absolute top-2.5 right-3 bg-emerald-600 text-white text-[10px] font-black px-2 py-0.5 rounded-full flex items-center gap-1 shadow-sm">
                                  <span>-{deal.savings_pln.toLocaleString("ru-RU")} zł ({deal.savings_pct}%)</span>
                                </div>

                                <div className="absolute bottom-3 left-3.5 right-3.5 text-white">
                                  <div className="flex items-center justify-between text-amber-400 mb-0.5">
                                    <span className="text-[10px] font-black uppercase tracking-wider text-slate-300">
                                      {deal.country}
                                    </span>
                                    <div className="flex items-center">
                                      {Array.from({ length: deal.stars || 4 }).map((_, i) => (
                                        <Star key={i} className="w-3 h-3 fill-current" />
                                      ))}
                                    </div>
                                  </div>
                                  <div className="font-black text-white text-[15px] line-clamp-1 drop-shadow-sm">
                                    {deal.hotel_name}
                                  </div>
                                  {deal.german_hotel_name && (
                                    <div className="text-[11px] text-slate-300 italic truncate">
                                      В Германии: {deal.german_hotel_name}
                                    </div>
                                  )}
                                  <div className="flex items-center justify-between text-xs mt-1.5 pt-1.5 border-t border-white/20">
                                    <span className="text-slate-300">
                                      🇩🇪 BER: <b className="text-emerald-400 font-extrabold">{deal.berlin_price_pln.toLocaleString("ru-RU")} zł</b>
                                    </span>
                                    <span className="text-slate-300 line-through">
                                      🇵🇱 {deal.polish_price_pln.toLocaleString("ru-RU")} zł
                                    </span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">
                                {deal.country}
                              </span>
                              <div className="flex items-center text-amber-500">
                                {Array.from({ length: deal.stars || 4 }).map((_, i) => (
                                  <Star key={i} className="w-2.5 h-2.5 fill-current" />
                                ))}
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => onOpenPassport?.(deal.hotel_id)}
                              className="font-black text-slate-900 hover:text-blue-600 transition-colors text-left text-[14px] line-clamp-1 group-hover:underline cursor-pointer tracking-tight"
                              title="Нажмите, чтобы открыть паспорт отеля"
                            >
                              {deal.hotel_name}
                            </button>
                            {deal.german_hotel_name && deal.german_hotel_name !== deal.hotel_name && (
                              <div
                                className="text-[10.5px] text-slate-400 italic truncate max-w-[240px] mt-0.5"
                                title={`Check24: ${deal.german_hotel_name}`}
                              >
                                DE: {deal.german_hotel_name}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* 2. Dates & Party */}
                      <td className="px-3 py-3">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1 font-semibold text-slate-800">
                            <Calendar className="w-3 h-3 text-slate-400 shrink-0" />
                            <span>{deal.checkin_date}</span>
                          </div>
                          <div className="text-[11px] text-slate-500">
                            <span>{deal.duration_nights} ночей</span>
                            {deal.german_duration_nights && deal.german_duration_nights !== deal.duration_nights && (
                              <span className="text-[10px] text-amber-600 font-bold ml-1">
                                (DE: {deal.german_duration_nights}н)
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-slate-400 flex items-center gap-0.5">
                            <Users className="w-2.5 h-2.5" />
                            <span>
                              {deal.adults} взр {deal.children > 0 ? `+ ${deal.children} реб` : ""}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* 3. Polish Departure */}
                      <td className="px-3 py-3">
                        <div className="space-y-0.5">
                          <div className="inline-flex items-center gap-1 font-bold text-slate-700 bg-slate-100 px-2 py-0.5 rounded-md text-[11px]">
                            <span>🇵🇱 {deal.polish_airport}</span>
                          </div>
                          <div className="text-[10px] text-slate-400 truncate max-w-[130px]">
                            {deal.polish_operator}
                          </div>
                          <div className="font-bold text-slate-600 line-through text-xs">
                            {deal.polish_price_pln.toLocaleString("ru-RU")} zł
                          </div>
                        </div>
                      </td>

                      {/* 4. Berlin Departure */}
                      <td className="px-3 py-3">
                        <div className="space-y-0.5">
                          <div className="inline-flex items-center gap-1 font-bold text-blue-800 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-md text-[11px]">
                            <span>🇩🇪 {deal.berlin_airport}</span>
                          </div>
                          <div className="text-[10px] text-slate-400 truncate max-w-[130px]">
                            {deal.berlin_operator}
                          </div>
                          <div className="font-extrabold text-emerald-700 text-sm">
                            {deal.berlin_price_pln.toLocaleString("ru-RU")} zł
                          </div>
                          <div className="text-[9px] text-slate-400">
                            -250 zł трансфер
                          </div>
                        </div>
                      </td>

                      {/* 5. Net Savings */}
                      <td className="px-3 py-3">
                        <div className="space-y-1">
                          <div className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-800 border border-emerald-200 font-black px-2 py-0.5 rounded-lg text-xs">
                            <TrendingDown className="w-3 h-3 text-emerald-600" />
                            <span>-{deal.savings_pln.toLocaleString("ru-RU")} zł</span>
                          </div>
                          <div className="text-[11px] font-extrabold text-emerald-600">
                            -{deal.savings_pct}% экономия
                          </div>
                          <div className="text-[10px] text-slate-500 font-medium">
                            {deal.verdict}
                          </div>
                        </div>
                      </td>

                      {/* 6. Actions */}
                      <td className="pr-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5 flex-wrap">
                          {/* Check24 Link */}
                          <a
                            href={deal.berlin_booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 py-1.5 px-2.5 rounded-xl bg-[#034ea2] hover:bg-[#023b7a] text-white text-[11px] font-bold transition-colors shadow-xs"
                            title="Открыть тур на Check24"
                          >
                            <span>🇩🇪 Check24</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>

                          {/* Polish Link */}
                          {deal.polish_booking_url && (
                            <a
                              href={deal.polish_booking_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 py-1.5 px-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-bold transition-colors border border-slate-200"
                              title="Открыть тур в Польше"
                            >
                              <span>🇵🇱 Польша</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}

                          {/* Passport Button */}
                          {onOpenPassport && (
                            <button
                              type="button"
                              onClick={() => onOpenPassport(deal.hotel_id)}
                              className="p-1.5 rounded-xl bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-600 border border-slate-200 transition-colors cursor-pointer"
                              title="Открыть паспорт отеля (история цен и прогноз)"
                            >
                              <Sparkles className="w-3.5 h-3.5" />
                            </button>
                          )}

                          {/* Watchlist Toggle */}
                          {onToggleWatchlist && (
                            <button
                              type="button"
                              onClick={() => onToggleWatchlist(deal)}
                              className={`p-1.5 rounded-xl border transition-colors cursor-pointer ${
                                watched
                                  ? "bg-amber-50 text-amber-500 border-amber-300"
                                  : "bg-slate-100 hover:bg-slate-200 text-slate-400 hover:text-slate-600 border-slate-200"
                              }`}
                              title={watched ? "В вотчлисте" : "Добавить в вотчлист"}
                            >
                              <Star className={`w-3.5 h-3.5 ${watched ? "fill-amber-500 text-amber-500" : ""}`} />
                            </button>
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
      ) : (
        /* CARDS VIEW */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {sortedDeals.map((d, idx) => {
            const watched = isDealWatched(d);
            return (
              <div
                key={`${d.hotel_id}_${idx}`}
                className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs hover:shadow-md transition-all flex flex-col justify-between"
              >
                {/* Hotel Header Image */}
                <div className="relative h-44 bg-slate-100 overflow-hidden">
                  <img
                    src={
                      d.main_image_url ||
                      "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=600&q=80"
                    }
                    alt={d.hotel_name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                  <div className="absolute top-3 right-3 bg-rose-600 text-white text-xs font-black px-2.5 py-1 rounded-xl shadow-md flex items-center gap-1">
                    <TrendingDown className="w-3.5 h-3.5" />
                    <span>-{d.savings_pln.toLocaleString("ru-RU")} zł</span>
                  </div>

                  {/* Quick Passport button overlay */}
                  {onOpenPassport && (
                    <button
                      type="button"
                      onClick={() => onOpenPassport(d.hotel_id)}
                      className="absolute top-3 left-3 bg-slate-900/75 hover:bg-slate-900 text-white text-[11px] font-bold px-2.5 py-1 rounded-xl shadow-md backdrop-blur-xs flex items-center gap-1 transition-colors cursor-pointer"
                    >
                      <Sparkles className="w-3 h-3 text-amber-400" />
                      <span>Паспорт</span>
                    </button>
                  )}
                </div>

                {/* Hotel Info */}
                <div className="p-4 flex-1">
                  <div className="flex items-center justify-between gap-1.5 text-xs text-slate-500 mb-1">
                    <span className="font-semibold text-slate-700">{d.country}</span>
                    <div className="flex items-center text-amber-500">
                      {Array.from({ length: d.stars || 4 }).map((_, i) => (
                        <Star key={i} className="w-3 h-3 fill-current" />
                      ))}
                    </div>
                  </div>

                  <h3
                    onClick={() => onOpenPassport?.(d.hotel_id)}
                    className="font-bold text-slate-900 text-sm line-clamp-1 mb-1 hover:text-blue-600 cursor-pointer transition-colors"
                    title={d.hotel_name}
                  >
                    {d.hotel_name}
                  </h3>

                  {d.german_hotel_name && d.german_hotel_name !== d.hotel_name && (
                    <div
                      className="text-[10px] text-slate-400 mb-1 italic truncate"
                      title={`В каталоге Check24: ${d.german_hotel_name}`}
                    >
                      В Check24: {d.german_hotel_name}
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-[11px] text-slate-500 mb-3 flex-wrap">
                    <span>
                      📅 Вылет: <b>{d.checkin_date}</b> ({d.duration_nights}н)
                    </span>
                    <span className="text-slate-300">•</span>
                    <span>
                      👥 {d.adults} взр {d.children > 0 ? `+ ${d.children} реб` : ""}
                    </span>
                  </div>

                  {/* Price Comparison Block */}
                  <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-500 flex items-center gap-1">
                        <span>🇵🇱 {d.polish_airport}</span>
                        <span className="text-[10px] text-slate-400">({d.polish_operator})</span>
                      </span>
                      <span className="font-bold text-slate-600 line-through">
                        {d.polish_price_pln.toLocaleString("ru-RU")} zł
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs font-bold">
                      <span className="text-blue-700 flex items-center gap-1">
                        <span>🇩🇪 {d.berlin_airport}</span>
                        <span className="text-[10px] text-blue-500">({d.berlin_operator})</span>
                      </span>
                      <span className="text-emerald-700 text-sm font-extrabold">
                        {d.berlin_price_pln.toLocaleString("ru-RU")} zł
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-200/50">
                      <span>Трансфер до Берлина:</span>
                      <span>-250 zł (учтен в расчете)</span>
                    </div>
                  </div>
                </div>

                {/* Bottom CTA */}
                <div className="px-4 pb-4 pt-1 space-y-2">
                  <div className="w-full py-1.5 px-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold text-center">
                    {d.verdict}
                  </div>
                  <div className="flex items-center gap-2">
                    <a
                      href={d.berlin_booking_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 py-2 px-3 rounded-xl bg-[#034ea2] hover:bg-[#023b7a] text-white text-xs font-bold text-center flex items-center justify-center gap-1 transition-colors shadow-xs"
                    >
                      <span>
                        {d.berlin_booking_url && d.berlin_booking_url.includes("check24")
                          ? "🇩🇪 Check24 BER"
                          : "🇩🇪 BER Вылет"}
                      </span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                    {d.polish_booking_url && (
                      <a
                        href={d.polish_booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex-1 py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold text-center flex items-center justify-center gap-1 transition-colors border border-slate-200"
                      >
                        <span>🇵🇱 Польша</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {onToggleWatchlist && (
                      <button
                        type="button"
                        onClick={() => onToggleWatchlist(d)}
                        className={`p-2 rounded-xl border transition-colors cursor-pointer ${
                          watched
                            ? "bg-amber-50 text-amber-500 border-amber-300"
                            : "bg-slate-100 hover:bg-slate-200 text-slate-400 hover:text-slate-600 border-slate-200"
                        }`}
                        title={watched ? "В вотчлисте" : "Добавить в вотчлист"}
                      >
                        <Star className={`w-4 h-4 ${watched ? "fill-amber-500 text-amber-500" : ""}`} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
