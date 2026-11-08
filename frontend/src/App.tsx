import React, { useState, useEffect, useMemo } from "react";
import { SidebarNavigation } from "./components/SidebarNavigation";
import { HeroTerminal } from "./components/HeroTerminal";
import { AiMarketBriefing } from "./components/AiMarketBriefing";
import { Top10TimelineChart } from "./components/Top10TimelineChart";
import { AnalyticsFold } from "./components/AnalyticsFold";
import { UniversalTableFilters, FilterState } from "./components/UniversalTableFilters";
import { HotelTableView } from "./components/HotelTableView";
import { HotelCard } from "./components/HotelCard";
import { HotelPassportDrawer } from "./components/HotelPassportDrawer";
import { WatchlistDrawer } from "./components/WatchlistDrawer";
import { SearchHeader } from "./components/SearchHeader";
import { GermanArbitrageView } from "./components/GermanArbitrageView";
import {
  SearchRequest,
  SearchHotelItem,
  WatchlistItem,
  PriceDropItem,
  AirportStat,
} from "./types";
import {
  searchTours,
  getWatchlist,
  addToWatchlist,
  deleteWatchlistItem,
  getTopPriceDrops,
  getAirportComparison,
} from "./services/api";
import { Bell, Menu, Radio, Sparkles } from "lucide-react";

const CURRENT_USER_ID = "user_demo_01";

const FILTER_PRESETS: Record<
  string,
  {
    title: string;
    countryBadge: string;
    destination: string;
    targetUrl: string;
    chips: {
      airports: string;
      dates: string;
      party: string;
      hotelClass: string;
      budget: string;
    };
    searchReq: SearchRequest;
  }
> = {
  turkey_7_10_days: {
    title: "🇹🇷 Турция — 7–10 ночей (2 взр + 1 реб)",
    countryBadge: "🇹🇷 ТУРЦИЯ",
    destination: "turkey",
    targetUrl: "https://fly.pl/wczasy/turcja/?od-2027-05-25&do-2027-06-25&dorosli=2&dzieci=1&wiek=6&dlugosc=7-10",
    chips: {
      airports: "WAW, WRO, KTW, POZ, GDN",
      dates: "25.05.2027 — 25.06.2027",
      party: "2 взр + 1 реб (до 12 лет)",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 12 000 zł",
    },
    searchReq: {
      destination: "turkey",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-25" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WRO", "KTW"],
    },
  },
  turkey_11_14_days: {
    title: "🇹🇷 Турция — 11–14 ночей (2 взр + 1 реб)",
    countryBadge: "🇹🇷 ТУРЦИЯ ДЛИТЕЛЬНЫЙ",
    destination: "turkey",
    targetUrl: "https://fly.pl/wczasy/turcja/?od-2027-05-25&do-2027-06-25&dorosli=2&dzieci=1&wiek=6&dlugosc=11-14",
    chips: {
      airports: "WAW, KTW, WRO",
      dates: "25.05.2027 — 25.06.2027",
      party: "2 взр + 1 реб (6 лет)",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 16 000 zł",
    },
    searchReq: {
      destination: "turkey",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-25" },
      duration: { min_nights: 11, max_nights: 14 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW"],
    },
  },
  turkey_7_10_adults: {
    title: "🇹🇷 Турция — 7–10 ночей (только 2 взрослых)",
    countryBadge: "🇹🇷 ТУРЦИЯ ПАРА",
    destination: "turkey",
    targetUrl: "https://fly.pl/wczasy/turcja/?od-2027-05-25&do-2027-06-25&dorosli=2&dlugosc=7-10",
    chips: {
      airports: "WAW, WRO, KTW, GDN",
      dates: "25.05.2027 — 25.06.2027",
      party: "2 взрослых (без детей)",
      hotelClass: "4★ – 5★ AI / Adults Only",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "turkey",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-25" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 0, children_ages: [] },
      airports: ["WAW", "WRO"],
    },
  },
  turkey_aquapark: {
    title: "🇹🇷 Турция — Аквапарки и 1-я линия",
    countryBadge: "🇹🇷 АКВАПАРКИ",
    destination: "turkey",
    targetUrl: "https://fly.pl/wczasy/turcja/?od-2027-05-25&do-2027-06-25&dorosli=2&dzieci=1&wiek=6&hotel=aquapark",
    chips: {
      airports: "WAW, KTW, WRO, POZ",
      dates: "01.06.2027 — 30.06.2027",
      party: "2 взр + 1 реб (6 лет)",
      hotelClass: "5★ Ultra All Inclusive",
      budget: "до 15 000 zł",
    },
    searchReq: {
      destination: "turkey",
      dates: { start_date_min: "2027-06-01", start_date_max: "2027-06-30" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW"],
    },
  },
  egypt_7_10_days: {
    title: "🇪🇬 Египет — 7–10 ночей (2 взр + 1 реб)",
    countryBadge: "🇪🇬 ЕГИПЕТ",
    destination: "egypt",
    targetUrl: "https://fly.pl/wczasy/egipt/?od-2027-04-15&do-2027-05-30&dorosli=2&dzieci=1&wiek=6&dlugosc=7-10",
    chips: {
      airports: "WAW, KTW, WRO",
      dates: "15.04.2027 — 30.05.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      dates: { start_date_min: "2027-04-15", start_date_max: "2027-05-30" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW"],
    },
  },
};

const INITIAL_FILTERS: FilterState = {
  search: "",
  priceMax: "",
  recommendation: "",
  tripAdvisor: "",
  change: "",
  region: "",
  onlyFavorites: false,
};

export const App: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"filter" | "search" | "arbitrage">("filter");
  const [activeFilterId, setActiveFilterId] = useState<string>("turkey_7_10_days");
  const [viewMode, setViewMode] = useState<"cards" | "table" | "arbitrage">("table");

  const [results, setResults] = useState<SearchHotelItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeHotelPassport, setActiveHotelPassport] = useState<string | null>(null);

  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState(false);

  const [topDrops, setTopDrops] = useState<PriceDropItem[]>([]);
  const [airportStats, setAirportStats] = useState<AirportStat[]>([]);

  // Filter state
  const [tableFilters, setTableFilters] = useState<FilterState>(INITIAL_FILTERS);
  const [sortField, setSortField] = useState("price");
  const [sortAsc, setSortAsc] = useState(true);

  // Current active preset config
  const currentPreset = FILTER_PRESETS[activeFilterId] || FILTER_PRESETS["turkey_7_10_days"];

  useEffect(() => {
    // 1. Fetch user watchlist
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

    // 4. Load initial filter results
    loadFilterResults("turkey_7_10_days");
  }, []);

  const loadFilterResults = async (filterId: string) => {
    const preset = FILTER_PRESETS[filterId] || FILTER_PRESETS["turkey_7_10_days"];
    setIsLoading(true);
    try {
      const resp = await searchTours(preset.searchReq);
      setResults(resp.results);
    } catch (err: any) {
      console.error("Filter search error:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectFilter = (filterId: string) => {
    setActiveFilterId(filterId);
    setActiveTab("filter");
    loadFilterResults(filterId);
    setIsSidebarOpen(false);
  };

  const handleSearch = async (req: SearchRequest) => {
    setIsLoading(true);
    try {
      const resp = await searchTours(req);
      setResults(resp.results);
    } catch (err: any) {
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
      const item = watchlistItems.find(
        (w) => w.cohort_hash === hotel.current_offer.cohort_hash
      );
      if (item) {
        await deleteWatchlistItem(item.watch_id);
        setWatchlistItems((prev) => prev.filter((w) => w.watch_id !== item.watch_id));
      }
    } else {
      const targetPrompt = window.prompt(
        `Поставить "${hotel.hotel_name}" на мониторинг?\nТекущая цена: ${hotel.current_offer.total_price_pln.toLocaleString(
          "ru-RU"
        )} zł.\n\nУкажите целевую цену (zł) для уведомления (или оставьте пустым для любого снижения):`,
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

  const watchedCohortHashes = useMemo(
    () => new Set(watchlistItems.map((w) => w.cohort_hash)),
    [watchlistItems]
  );

  // Available regions list
  const availableRegions = useMemo(() => {
    const s = new Set<string>();
    results.forEach((h) => {
      if (h.region) s.add(h.region);
    });
    return Array.from(s).sort();
  }, [results]);

  // Filtered & Sorted Hotels
  const filteredHotels = useMemo(() => {
    let res = results.filter((h) => {
      // Search
      if (tableFilters.search) {
        const q = tableFilters.search.toLowerCase();
        const match =
          h.hotel_name.toLowerCase().includes(q) ||
          (h.region && h.region.toLowerCase().includes(q));
        if (!match) return false;
      }

      // Max price
      if (tableFilters.priceMax) {
        const maxP = parseFloat(tableFilters.priceMax);
        if (h.current_offer.total_price_pln > maxP) return false;
      }

      // Recommendation
      if (tableFilters.recommendation === "buy" && h.intelligence.deal_score < 75) {
        return false;
      }
      if (
        tableFilters.recommendation === "wait" &&
        (h.intelligence.deal_score >= 75 || h.intelligence.deal_score < 45)
      ) {
        return false;
      }
      if (tableFilters.recommendation === "expensive" && h.intelligence.deal_score >= 45) {
        return false;
      }

      // TripAdvisor
      if (tableFilters.tripAdvisor) {
        const minRating = parseFloat(tableFilters.tripAdvisor);
        if (!h.ta_rating || h.ta_rating < minRating) return false;
      }

      // Change
      if (tableFilters.change === "decrease" && h.intelligence.drop_48h_pct <= 0) {
        return false;
      }
      if (tableFilters.change === "stable" && h.intelligence.drop_48h_pct !== 0) {
        return false;
      }

      // Region
      if (tableFilters.region && h.region !== tableFilters.region) {
        return false;
      }

      // Favorites
      if (tableFilters.onlyFavorites && !watchedCohortHashes.has(h.current_offer.cohort_hash)) {
        return false;
      }

      return true;
    });

    // Sort
    res.sort((a, b) => {
      let diff = 0;
      if (sortField === "price") {
        diff = a.current_offer.total_price_pln - b.current_offer.total_price_pln;
      } else if (sortField === "deal_score") {
        diff = b.intelligence.deal_score - a.intelligence.deal_score;
      } else if (sortField === "ta_rating") {
        diff = (b.ta_rating || 0) - (a.ta_rating || 0);
      } else if (sortField === "hotel") {
        diff = a.hotel_name.localeCompare(b.hotel_name);
      } else if (sortField === "delta48") {
        diff = b.intelligence.drop_48h_pct - a.intelligence.drop_48h_pct;
      }
      return sortAsc ? diff : -diff;
    });

    return res;
  }, [results, tableFilters, sortField, sortAsc, watchedCohortHashes]);

  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field === "price");
    }
  };

  // Live KPI metrics
  const heroKpi = useMemo(() => {
    if (!results.length) {
      return {
        minPricePln: 0,
        minPriceHotel: "—",
        minPriceDate: "",
        buyNowCount: 0,
        dropped48hPln: 0,
        lastUpdatedText: "5 мин. назад",
      };
    }

    const minOffer = [...results].sort(
      (a, b) => a.current_offer.total_price_pln - b.current_offer.total_price_pln
    )[0];

    const buyNowHotels = results.filter((h) => h.intelligence.deal_score >= 80);
    const dropHotel = results.find((h) => h.intelligence.drop_48h_pct > 0);

    return {
      minPricePln: minOffer ? minOffer.current_offer.total_price_pln : 0,
      minPriceHotel: minOffer ? minOffer.hotel_name : "",
      minPriceDate: minOffer ? minOffer.current_offer.departure_date : "",
      buyNowCount: buyNowHotels.length,
      dropped48hPln: dropHotel
        ? Math.round(
            dropHotel.current_offer.total_price_pln *
              (dropHotel.intelligence.drop_48h_pct / 100)
          )
        : 420,
      lastUpdatedText: "12 мин. назад",
    };
  }, [results]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* V1 Collapsible Left Sidebar */}
      <SidebarNavigation
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        activeFilterId={activeFilterId}
        onSelectFilter={handleSelectFilter}
        onOpenSearch={() => {
          setActiveTab("search");
          setIsSidebarOpen(false);
        }}
        onOpenArbitrage={() => {
          setViewMode("arbitrage");
          setIsSidebarOpen(false);
        }}
        activeTab={activeTab}
      />

      {/* Top Navbar */}
      <header className="bg-slate-900 text-white py-3 px-4 sm:px-6 border-b border-slate-800 sticky top-0 z-30 shadow-md">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              id="sidebarToggle"
              type="button"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700"
              title="Открыть меню фильтров"
            >
              <Menu className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-extrabold text-white shadow-md shadow-blue-500/20">
                ✈️
              </div>
              <div>
                <div className="text-sm font-black tracking-tight flex items-center gap-2">
                  <span>TRAVEL MONITOR</span>
                  <span className="text-[9px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded-full">
                    v2.0 DUAL-ENGINE
                  </span>
                </div>
                <p className="text-[10px] text-slate-400">
                  {currentPreset.title}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-1 bg-slate-800/90 p-1 rounded-2xl border border-slate-700">
              <button
                type="button"
                onClick={() => {
                  setActiveTab("filter");
                  setViewMode("table");
                }}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "filter" && viewMode !== "arbitrage"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <Radio className="w-3.5 h-3.5 text-emerald-400" />
                <span>Радар фильтров</span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("search")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "search"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <span>🔍 Интерактивный поиск</span>
              </button>

              <button
                type="button"
                onClick={() => setViewMode("arbitrage")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  viewMode === "arbitrage"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <span>🇩🇪 Берлин (BER)</span>
              </button>
            </div>

            <button
              onClick={() => setIsWatchlistOpen(true)}
              className="relative inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-all border border-slate-700"
            >
              <Bell className="w-4 h-4 text-amber-400 fill-current" />
              <span className="hidden sm:inline">Watchlist</span>
              {watchlistItems.length > 0 && (
                <span className="w-5 h-5 rounded-full bg-amber-500 text-white text-[10px] font-bold flex items-center justify-center">
                  {watchlistItems.length}
                </span>
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5 flex-1 w-full space-y-5">
        {/* If in Search Tab */}
        {activeTab === "search" && (
          <div className="mb-4">
            <SearchHeader onSearch={handleSearch} isLoading={isLoading} />
          </div>
        )}

        {/* 1. Hero Terminal Banner with Metadata Chips & 4 White KPI Cards */}
        <HeroTerminal
          title={
            activeTab === "filter"
              ? currentPreset.title
              : "🔍 Результаты метапоиска"
          }
          countryBadge={
            activeTab === "filter"
              ? currentPreset.countryBadge
              : "ПОЛЬЗОВАТЕЛЬСКИЙ ПОИСК"
          }
          targetUrl={activeTab === "filter" ? currentPreset.targetUrl : undefined}
          chips={activeTab === "filter" ? currentPreset.chips : undefined}
          kpi={heroKpi}
        />

        {/* 2. Top Fold: 🧠 AI-анализ рынка и прогноз цен */}
        <AiMarketBriefing
          filterTitle={currentPreset.chips.dates}
          buyNowCount={heroKpi.buyNowCount}
        />

        {/* 3. Time Series Chart: 📉 Средняя цена ТОП-10 дешёвых предложений */}
        <Top10TimelineChart destination={currentPreset.destination} />

        {/* 4. Second Fold: 📊 Расширенная аналитика и тренды рынка */}
        <AnalyticsFold
          hotels={results}
          topDrops={topDrops}
          airportStats={airportStats}
          onSelectHotel={(hotelId) => setActiveHotelPassport(hotelId)}
        />

        {/* 5. Universal Toolbar: Вид (Карточки / Таблица / Арбитраж) + Фильтры */}
        <UniversalTableFilters
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          filters={tableFilters}
          onFilterChange={setTableFilters}
          onClear={() => setTableFilters(INITIAL_FILTERS)}
          regions={availableRegions}
        />

        {/* 6. Mode Switch Views */}
        {viewMode === "arbitrage" ? (
          <GermanArbitrageView />
        ) : viewMode === "table" ? (
          <HotelTableView
            hotels={filteredHotels}
            onOpenPassport={(id) => setActiveHotelPassport(id)}
            onToggleWatchlist={handleToggleWatchlist}
            watchedCohortHashes={watchedCohortHashes}
            sortField={sortField}
            sortAsc={sortAsc}
            onSort={handleSort}
          />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredHotels.map((hotel) => (
                <HotelCard
                  key={hotel.current_offer.cohort_hash}
                  hotel={hotel}
                  onOpenPassport={(id) => setActiveHotelPassport(id)}
                  onToggleWatchlist={handleToggleWatchlist}
                  isWatched={watchedCohortHashes.has(
                    hotel.current_offer.cohort_hash
                  )}
                />
              ))}
            </div>
          </div>
        )}
      </main>

      {/* 7. Hotel AI Passport Drawer (Slides out from RIGHT) */}
      <HotelPassportDrawer
        hotelId={activeHotelPassport}
        onClose={() => setActiveHotelPassport(null)}
      />

      {/* Watchlist Drawer */}
      <WatchlistDrawer
        isOpen={isWatchlistOpen}
        onClose={() => setIsWatchlistOpen(false)}
        items={watchlistItems}
        onDeleteItem={handleDeleteWatchlist}
      />
    </div>
  );
};
