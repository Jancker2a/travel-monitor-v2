import React from "react";
import { Search, Star, RotateCcw, LayoutGrid, Table, Globe, BellRing, Radio, ChevronDown } from "lucide-react";

export interface FilterState {
  search: string;
  priceMax: string;
  recommendation: string;
  tripAdvisor: string;
  change: string;
  region: string;
  onlyFavorites: boolean;
}

interface UniversalTableFiltersProps {
  viewMode: "cards" | "table" | "arbitrage";
  onViewModeChange: (mode: "cards" | "table" | "arbitrage") => void;
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  onClear: () => void;
  regions: string[];
  arbitrageCount?: number;
  showArbitrageTab?: boolean;
  onOpenMonitorAlerts?: () => void;
  onSaveSearchAsMonitor?: () => void;
}

export const UniversalTableFilters: React.FC<UniversalTableFiltersProps> = ({
  viewMode,
  onViewModeChange,
  filters,
  onFilterChange,
  onClear,
  regions,
  arbitrageCount,
  showArbitrageTab = true,
  onOpenMonitorAlerts,
  onSaveSearchAsMonitor,
}) => {
  return (
    <div className="space-y-3.5" id="globalFiltersWrap">
      {/* View Switcher Row */}
      <div className="flex items-center justify-between flex-wrap gap-2.5">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-extrabold text-slate-500 uppercase tracking-wider">
            Вид
          </span>
          <div className="inline-flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
            <button
              type="button"
              onClick={() => onViewModeChange("cards")}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-bold transition-all flex items-center gap-1.5 ${
                viewMode === "cards"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
              <span>Карточки</span>
            </button>

            <button
              type="button"
              onClick={() => onViewModeChange("table")}
              className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-bold transition-all flex items-center gap-1.5 ${
                viewMode === "table"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Table className="w-4 h-4" />
              <span>Таблица</span>
            </button>

            {showArbitrageTab && (
              <button
                id="modeBtnArbitrage"
                type="button"
                onClick={() => onViewModeChange("arbitrage")}
                className={`px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-bold transition-all flex items-center gap-1.5 ${
                  viewMode === "arbitrage"
                    ? "bg-white text-blue-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Globe className="w-4 h-4 text-blue-600" />
                <span>Арбитраж BER</span>
                {arbitrageCount != null && arbitrageCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-black bg-blue-100 text-blue-700">
                    {arbitrageCount}
                  </span>
                )}
              </button>
            )}
          </div>
        </div>

        {onSaveSearchAsMonitor ? (
          <button
            type="button"
            onClick={onSaveSearchAsMonitor}
            className="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-white cursor-pointer shadow-xs hover:shadow active:scale-[0.98] shrink-0 whitespace-nowrap"
            title="Отслеживать цены по этому поиску и получать уведомления в Telegram"
          >
            <Radio className="w-4 h-4 text-white animate-pulse shrink-0" />
            <span>Авто-мониторинг цен</span>
          </button>
        ) : onOpenMonitorAlerts ? (
          <button
            type="button"
            onClick={onOpenMonitorAlerts}
            className="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all flex items-center gap-2 bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 cursor-pointer shadow-xs active:scale-[0.98] shrink-0 whitespace-nowrap"
            title="Настроить гибкие Telegram-алерты, пороги цен и частоту дайджестов"
          >
            <BellRing className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Telegram-алерты</span>
          </button>
        ) : null}
      </div>

      {/* Filter Selects & Search Bar Row - hidden in arbitrage mode because arbitrage has its own specialized toolbar */}
      {viewMode !== "arbitrage" && (
        <div className="flex items-center gap-2.5 flex-wrap bg-white p-3 sm:p-3.5 rounded-2xl border border-slate-200 shadow-xs">
          {/* Search */}
          <div className="relative min-w-[200px] flex-1">
            <input
              type="text"
              id="searchInput"
              value={filters.search}
              onChange={(e) => onFilterChange({ ...filters, search: e.target.value })}
              placeholder="🔍 Поиск по отелям..."
              className="w-full px-3.5 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 font-medium text-slate-900"
            />
          </div>

          {/* Price Max Filter */}
          <div className="relative shrink-0">
            <select
              id="priceFilter"
              value={filters.priceMax}
              onChange={(e) => onFilterChange({ ...filters, priceMax: e.target.value })}
              className="appearance-none text-xs sm:text-sm py-2 pl-3.5 pr-10 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-colors"
            >
              <option value="all">Все цены (без потолка)</option>
              <option value="">Потолок фильтра (по умолч.)</option>
              <option value="8000">до 8 000 zł</option>
              <option value="10000">до 10 000 zł</option>
              <option value="12000">до 12 000 zł</option>
              <option value="14000">до 14 000 zł</option>
              <option value="18000">до 18 000 zł</option>
              <option value="25000">до 25 000 zł</option>
              <option value="50000">до 50 000 zł</option>
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Forecast / Recommendations Filter */}
          <div className="relative shrink-0">
            <select
              id="forecastFilter"
              value={filters.recommendation}
              onChange={(e) => onFilterChange({ ...filters, recommendation: e.target.value })}
              className="appearance-none text-xs sm:text-sm py-2 pl-3.5 pr-10 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-colors"
            >
              <option value="">Все рекомендации</option>
              <option value="buy">🟢 Покупать (80+)</option>
              <option value="wait">🟡 Ждать</option>
              <option value="expensive">🔴 Дорого</option>
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* TripAdvisor Filter */}
          <div className="relative shrink-0">
            <select
              id="taFilter"
              value={filters.tripAdvisor}
              onChange={(e) => onFilterChange({ ...filters, tripAdvisor: e.target.value })}
              className="appearance-none text-xs sm:text-sm py-2 pl-3.5 pr-10 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-colors"
            >
              <option value="">Все рейтинги TripAdvisor</option>
              <option value="4.5">Рейтинг ≥ 4.5</option>
              <option value="4.0">Рейтинг ≥ 4.0</option>
              <option value="3.5">Рейтинг ≥ 3.5</option>
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Price Changes Filter */}
          <div className="relative shrink-0">
            <select
              id="changeFilter"
              value={filters.change}
              onChange={(e) => onFilterChange({ ...filters, change: e.target.value })}
              className="appearance-none text-xs sm:text-sm py-2 pl-3.5 pr-10 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-colors"
            >
              <option value="">Все изменения</option>
              <option value="decrease">📉 Снижение цен</option>
              <option value="increase">📈 Рост цен</option>
              <option value="stable">Стабильные</option>
            </select>
            <ChevronDown className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Regions Filter */}
          <div className="relative shrink-0">
            <select
              id="regionFilter"
              value={filters.region}
              onChange={(e) => onFilterChange({ ...filters, region: e.target.value })}
              className="appearance-none text-xs sm:text-sm py-2 pl-3.5 pr-10 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 cursor-pointer transition-colors"
            >
              <option value="">Все регионы</option>
              {regions.map((reg) => (
                <option key={reg} value={reg}>
                  {reg}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Favorites button */}
          <button
            type="button"
            id="watchlistToggle"
            onClick={() => onFilterChange({ ...filters, onlyFavorites: !filters.onlyFavorites })}
            className={`px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold flex items-center gap-1.5 transition-colors border cursor-pointer ${
              filters.onlyFavorites
                ? "bg-amber-100 text-amber-900 border-amber-300 font-bold"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200"
            }`}
          >
            <Star className={`w-4 h-4 ${filters.onlyFavorites ? "fill-amber-500 text-amber-500" : "text-amber-500"}`} />
            <span>Избранные</span>
          </button>

          {/* Clear Filters Button */}
          <button
            type="button"
            id="clearFilters"
            onClick={onClear}
            className="px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 transition-colors shadow-xs cursor-pointer"
          >
            Очистить
          </button>
        </div>
      )}
    </div>
  );
};

