import React, { useState, useEffect } from "react";
import { SearchHeader } from "./components/SearchHeader";
import { HotelCard } from "./components/HotelCard";
import { HotelPassportModal } from "./components/HotelPassportModal";
import { WatchlistDrawer } from "./components/WatchlistDrawer";
import { TopDropsCarousel } from "./components/TopDropsCarousel";
import { AirportComparisonWidget } from "./components/AirportComparisonWidget";
import { FilterMonitorsView } from "./components/FilterMonitorsView";
import { GermanArbitrageView } from "./components/GermanArbitrageView";
import { SearchRequest, SearchHotelItem, WatchlistItem, PriceDropItem, AirportStat } from "./types";
import {
  searchTours,
  getWatchlist,
  addToWatchlist,
  deleteWatchlistItem,
  getTopPriceDrops,
  getAirportComparison,
} from "./services/api";
import { Bell, Flame, SlidersHorizontal, Sparkles, Radio, Search } from "lucide-react";

const CURRENT_USER_ID = "user_demo_01";

export const App: React.FC = () => {
  const [results, setResults] = useState<SearchHotelItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCached, setIsCached] = useState(false);
  const [activeHotelPassport, setActiveHotelPassport] = useState<string | null>(null);
  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState(false);
  const [topDrops, setTopDrops] = useState<PriceDropItem[]>([]);
  const [airportStats, setAirportStats] = useState<AirportStat[]>([]);
  const [sortBy, setSortBy] = useState<"price" | "deal_score">("price");
  const [activeTab, setActiveTab] = useState<"search" | "monitors" | "arbitrage">("monitors");

  // Initial load: fetch watchlist, top drops, airport stats & run default search for Turkey
  useEffect(() => {
    // 1. Fetch user's watchlist
    getWatchlist(CURRENT_USER_ID)
      .then((data) => setWatchlistItems(data.items))
      .catch((err) => console.warn("Watchlist fetch failed:", err));

    // 2. Fetch top price drops
    getTopPriceDrops(10)
      .then((drops) => setTopDrops(drops))
      .catch((err) => console.warn("Top drops fetch failed:", err));

    // 3. Fetch airport comparison stats
    getAirportComparison("turkey")
      .then((stats) => setAirportStats(stats))
      .catch((err) => console.warn("Airport stats fetch failed:", err));

    // 4. Perform initial instant search
    handleSearch({
      destination: "turkey",
      dates: { start_date_min: "2026-11-15", start_date_max: "2026-11-25" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 0, children_ages: [] },
      airports: ["WAW"],
    });
  }, []);

  const handleSearch = async (req: SearchRequest) => {
    setIsLoading(true);
    try {
      const resp = await searchTours(req);
      setResults(resp.results);
      setIsCached(resp.cached);
    } catch (err: any) {
      console.error("Search error:", err);
      alert("Ошибка поиска: " + (err.message || "Не удалось выполнить запрос"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleWatchlist = async (hotel: SearchHotelItem) => {
    const isAlreadyWatched = watchlistItems.some(
      (w) => w.cohort_hash === hotel.current_offer.cohort_hash
    );

    if (isAlreadyWatched) {
      const item = watchlistItems.find((w) => w.cohort_hash === hotel.current_offer.cohort_hash);
      if (item) {
        await deleteWatchlistItem(item.watch_id);
        setWatchlistItems((prev) => prev.filter((w) => w.watch_id !== item.watch_id));
      }
    } else {
      const targetPrompt = window.prompt(
        `Поставить "${hotel.hotel_name}" на мониторинг?\nТекущая цена: ${hotel.current_offer.total_price_pln} zł.\n\nУкажите целевую цену (zł) для уведомления (или оставьте пустым для любого снижения):`,
        String(Math.round(hotel.current_offer.total_price_pln * 0.95))
      );
      if (targetPrompt === null) return;

      const targetPrice = targetPrompt ? parseFloat(targetPrompt) : undefined;
      const newItem = await addToWatchlist({
        cohort_hash: hotel.current_offer.cohort_hash,
        user_chat_id: CURRENT_USER_ID,
        target_price_pln: targetPrice,
        notify_any_drop: true,
      });
      setWatchlistItems((prev) => [newItem, ...prev]);
      setIsWatchlistOpen(true);
    }
  };

  const handleDeleteWatchlist = async (watchId: string) => {
    await deleteWatchlistItem(watchId);
    setWatchlistItems((prev) => prev.filter((w) => w.watch_id !== watchId));
  };

  const handleSelectPreset = (monitor: any) => {
    setActiveTab("search");
    handleSearch({
      destination: monitor.destination || "turkey",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-25" },
      duration: { min_nights: 7, max_nights: 11 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW"],
    });
  };

  // Sorted items
  const sortedResults = [...results].sort((a, b) => {
    if (sortBy === "deal_score") {
      return b.intelligence.deal_score - a.intelligence.deal_score;
    }
    return a.current_offer.total_price_pln - b.current_offer.total_price_pln;
  });

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Navbar */}
      <header className="bg-slate-900 text-white py-3.5 px-4 sm:px-8 border-b border-slate-800">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-extrabold text-white shadow-lg shadow-blue-500/30">
              ✈️
            </div>
            <div>
              <div className="text-base font-black tracking-tight flex items-center gap-2">
                <span>TRAVEL MONITOR</span>
                <span className="text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded-full">
                  v2.0 DUAL-ENGINE
                </span>
              </div>
              <p className="text-[11px] text-slate-400">
                Интерактивный метапоиск и Hopper-радар низких цен на туры
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Navigation Tabs */}
            <nav className="hidden md:flex items-center gap-1 bg-slate-800/90 p-1 rounded-2xl border border-slate-700">
              <button
                type="button"
                onClick={() => setActiveTab("monitors")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "monitors"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                <span>📡 Радар фильтров (v1 24/7)</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("search")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "search"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <Search className="w-3.5 h-3.5 text-blue-400" />
                <span>🔍 Интерактивный поиск</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("arbitrage")}
                className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "arbitrage"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <span>🇩🇪 Немецкий арбитраж</span>
              </button>
            </nav>

            <button
              onClick={() => setIsWatchlistOpen(true)}
              className="relative inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-all border border-slate-700"
            >
              <Bell className="w-4 h-4 text-amber-400 fill-current" />
              <span>Watchlist</span>
              {watchlistItems.length > 0 && (
                <span className="w-5 h-5 rounded-full bg-amber-500 text-white text-[10px] font-bold flex items-center justify-center">
                  {watchlistItems.length}
                </span>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile Nav Tabs */}
      <div className="flex md:hidden bg-slate-900 border-b border-slate-800 px-4 py-2 gap-1 overflow-x-auto scrollbar-none">
        <button
          type="button"
          onClick={() => setActiveTab("monitors")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
            activeTab === "monitors" ? "bg-blue-600 text-white" : "text-slate-400"
          }`}
        >
          📡 Радар фильтров (24/7)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("search")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
            activeTab === "search" ? "bg-blue-600 text-white" : "text-slate-400"
          }`}
        >
          🔍 Метапоиск
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("arbitrage")}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap ${
            activeTab === "arbitrage" ? "bg-blue-600 text-white" : "text-slate-400"
          }`}
        >
          🇩🇪 Арбитраж
        </button>
      </div>

      {/* Hero Search Controls Header (shown when on search tab) */}
      {activeTab === "search" && (
        <SearchHeader onSearch={handleSearch} isLoading={isLoading} />
      )}

      {/* Main Results View */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full space-y-6">
        {activeTab === "monitors" && (
          <FilterMonitorsView onSelectMonitor={handleSelectPreset} />
        )}

        {activeTab === "arbitrage" && (
          <GermanArbitrageView />
        )}

        {activeTab === "search" && (
          <>
            {/* Market Analytics & Top Drops (V1 Intelligence Integration) */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2">
                <TopDropsCarousel drops={topDrops} onSelectHotel={(hotelId) => setActiveHotelPassport(hotelId)} />
              </div>
              <div className="lg:col-span-1">
                <AirportComparisonWidget stats={airportStats} />
              </div>
            </div>

            {/* Results Toolbar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-5 gap-3">
              <div>
                <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
                  <span>Предложения по турам</span>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
                    {results.length} найдено
                  </span>
                  {isCached && (
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-emerald-600" />
                      Мгновенно из кэша (43K+ база)
                    </span>
                  )}
                </h1>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <span className="text-slate-400 flex items-center gap-1 font-medium">
                  <SlidersHorizontal className="w-3.5 h-3.5" /> Сортировка:
                </span>
                <button
                  onClick={() => setSortBy("price")}
                  className={`px-3 py-1.5 rounded-lg font-semibold transition-colors ${
                    sortBy === "price"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  Сначала дешевле
                </button>
                <button
                  onClick={() => setSortBy("deal_score")}
                  className={`px-3 py-1.5 rounded-lg font-semibold transition-colors flex items-center gap-1 ${
                    sortBy === "deal_score"
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <Flame className="w-3.5 h-3.5 text-amber-500 fill-current" />
                  По Deal Score (Hopper)
                </button>
              </div>
            </div>

            {/* Results List */}
            {isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-44 bg-white rounded-2xl border border-slate-200 p-6 animate-pulse flex gap-5">
                    <div className="w-64 h-full bg-slate-200 rounded-xl shrink-0" />
                    <div className="flex-1 space-y-3 py-2">
                      <div className="h-4 bg-slate-200 rounded w-1/4" />
                      <div className="h-6 bg-slate-200 rounded w-1/2" />
                      <div className="h-4 bg-slate-100 rounded w-1/3" />
                    </div>
                  </div>
                ))}
              </div>
            ) : sortedResults.length > 0 ? (
              <div className="space-y-4">
                {sortedResults.map((hotel) => (
                  <HotelCard
                    key={hotel.current_offer.cohort_hash}
                    hotel={hotel}
                    onOpenPassport={(id) => setActiveHotelPassport(id)}
                    onToggleWatchlist={handleToggleWatchlist}
                    isWatched={watchlistItems.some(
                      (w) => w.cohort_hash === hotel.current_offer.cohort_hash
                    )}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center text-slate-500 max-w-lg mx-auto mt-8">
                <div className="text-4xl mb-3">🔍</div>
                <h3 className="text-lg font-bold text-slate-800">Предложения не найдены</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Попробуйте включить галочку «Принудительный live-добор с Fly.pl» в строке поиска или расширить диапазон дат.
                </p>
              </div>
            )}
          </>
        )}
      </main>

      {/* Hotel Passport History Modal with Plotly Chart */}
      <HotelPassportModal
        hotelId={activeHotelPassport}
        onClose={() => setActiveHotelPassport(null)}
      />

      {/* Watchlist Sidebar Drawer */}
      <WatchlistDrawer
        isOpen={isWatchlistOpen}
        onClose={() => setIsWatchlistOpen(false)}
        items={watchlistItems}
        onDeleteItem={handleDeleteWatchlist}
      />
    </div>
  );
};

