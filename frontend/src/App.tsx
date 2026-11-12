import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
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
import { AuthModal } from "./components/AuthModal";
import { CreateMonitorModal } from "./components/CreateMonitorModal";
import { UserMonitorsView } from "./components/UserMonitorsView";
import { LoadingSpinner } from "./components/common/LoadingSpinner";
import {
  SearchRequest,
  SearchHotelItem,
  WatchlistItem,
  PriceDropItem,
  AirportStat,
  HotelCatalogCard,
  UserProfile,
  UserMonitor,
} from "./types";
import {
  searchTours,
  getWatchlist,
  addToWatchlist,
  deleteWatchlistItem,
  getTopPriceDrops,
  getAirportComparison,
  getFilterHotelsCatalog,
  getArbitrageDeals,
  getStoredUser,
  getStoredToken,
  fetchCurrentUser,
  logoutUser,
  listUserMonitors,
  getAdminStatus,
  claimAdmin,
} from "./services/api";
import { Bell, Menu, Radio, Sparkles, User as UserIcon, LogOut, Plus, Crown, RefreshCw, Layers, ExternalLink, TrendingDown, Clock, ArrowLeft } from "lucide-react";

const CURRENT_USER_ID = "user_demo_01";

export { FILTER_PRESETS } from "./constants/presets";
import { FILTER_PRESETS } from "./constants/presets";

const INITIAL_FILTERS: FilterState = {
  search: "",
  priceMax: "",
  recommendation: "",
  tripAdvisor: "",
  change: "",
  region: "",
  onlyFavorites: false,
};

function catalogCardToSearchItem(c: HotelCatalogCard, preset?: any): SearchHotelItem {
  const duration = c.cheapest_duration_nights || preset?.searchReq?.duration?.min_nights || 7;
  const nights = duration > 0 ? duration : 7;
  const adults = preset?.searchReq?.travelers?.adults ?? (preset?.searchReq?.filter_id?.includes("1p") ? 1 : 2);
  const children = preset?.searchReq?.travelers?.children ?? 0;
  const totalPax = Math.max(1, adults + children);
  return {
    hotel_id: c.hotel_id,
    hotel_name: c.display_name,
    stars: c.stars || 4,
    region: c.region || c.country,
    country: c.country,
    main_image_url: c.main_image_url,
    ta_rating: c.ta_rating,
    ta_reviews: c.ta_reviews,
    beach_line: c.beach_line,
    beach_type: c.beach_type,
    has_aquapark: c.has_aquapark,
    has_heated_pools: c.has_heated_pools,
    specs: {
      beach_line: c.beach_line,
      beach_type: c.beach_type,
      has_aquapark: c.has_aquapark,
      has_heated_pools: c.has_heated_pools,
    },
    current_offer: {
      cohort_hash: `${c.hotel_id}_${c.cheapest_checkin_date || "date"}_${nights}`,
      total_price_pln: c.current_min_price,
      price_per_night_pax: Math.round(c.current_min_price / nights / totalPax),
      departure_date: c.cheapest_checkin_date || "",
      duration_nights: nights,
      airport: c.cheapest_airport_code || "WAW",
      booking_url: c.cheapest_offer_url,
      adults: adults,
      children: children,
    },
    intelligence: {
      deal_score: c.deal_score,
      deal_badge:
        c.badges && c.badges.length > 0
          ? c.badges[0]
          : c.deal_score >= 80
          ? "🔥 Hot"
          : "✅ Good",
      hopper_verdict:
        c.deal_score >= 80
          ? "BUY NOW"
          : c.deal_score < 45
          ? "OVERPRICED"
          : "WAIT",
      hopper_confidence: c.deal_confidence === "High" ? 0.9 : 0.7,
      recommendation:
        c.badges && c.badges.length > 0
          ? c.badges.join(" • ")
          : "Стабильная цена",
      drop_48h_pct: c.change_48h_pct !== undefined ? c.change_48h_pct : c.change_24h_pct,
      delta_vs_typical_pct: c.delta_vs_typical_pct,
      historic_min_pln: c.historical_min_price,
      typical_median_pln: c.typical_median_price,
    },
    history_sparkline: [],
  };
}

export const App: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"filter" | "search" | "arbitrage" | "my_monitors">("filter");
  const [activeFilterId, setActiveFilterId] = useState<string>("turkey_7_10");
  const [viewMode, setViewMode] = useState<"cards" | "table" | "arbitrage">("table");

  // Auth & Multi-tenant State
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(() => getStoredUser());
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalReason, setAuthModalReason] = useState<string | null>(null);
  const [adminStatus, setAdminStatus] = useState<{ has_admin: boolean; admin_email?: string | null }>({ has_admin: true });
  const [isCreateMonitorOpen, setIsCreateMonitorOpen] = useState(false);
  const [userMonitors, setUserMonitors] = useState<UserMonitor[]>([]);
  const userMonitorsRef = useRef<UserMonitor[]>([]);
  userMonitorsRef.current = userMonitors;
  const [activeUserMonitor, setActiveUserMonitor] = useState<UserMonitor | null>(null);
  const activeUserMonitorRef = useRef<UserMonitor | null>(null);
  activeUserMonitorRef.current = activeUserMonitor;
  const [isLoadingMonitors, setIsLoadingMonitors] = useState(false);

  const isAdmin = currentUser?.role === "ADMIN";

  // Auto-refresh profile on app launch to sync role updates from server
  useEffect(() => {
    if (getStoredToken()) {
      fetchCurrentUser()
        .then((u) => {
          setCurrentUser(u);
        })
        .catch(() => {});
    }
  }, []);

  useEffect(() => {
    getAdminStatus().then((st) => setAdminStatus(st)).catch(() => {});
  }, [currentUser]);

  const handleClaimAdmin = async () => {
    try {
      const updated = await claimAdmin();
      setCurrentUser(updated);
      setAdminStatus({ has_admin: true, admin_email: updated.email });
      alert("👑 Поздравляем! Ваш аккаунт успешно назначен Администратором системы. Канонические радары теперь доступны вам.");
    } catch (err: any) {
      try {
        const u = await fetchCurrentUser();
        if (u.role === "ADMIN") {
          setCurrentUser(u);
          setAdminStatus({ has_admin: true, admin_email: u.email });
          alert("👑 Статус Администратора подтверждён! Все радары разблокированы.");
          return;
        }
      } catch {}
      alert(err.message || "Ошибка назначения администратора");
    }
  };

  const loadUserMonitors = useCallback(async () => {
    if (!currentUser) {
      setUserMonitors([]);
      return;
    }
    setIsLoadingMonitors(true);
    try {
      const list = await listUserMonitors();
      setUserMonitors(list);
    } catch (err) {
      console.warn("Could not load user monitors:", err);
    } finally {
      setIsLoadingMonitors(false);
    }
  }, [currentUser]);

  useEffect(() => {
    loadUserMonitors();
  }, [loadUserMonitors]);

  const [results, setResults] = useState<SearchHotelItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [totalFound, setTotalFound] = useState<number>(0);
  const [searchPage, setSearchPage] = useState<number>(1);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [isLoadingMore, setIsLoadingMore] = useState<boolean>(false);
  const [lastSearchReq, setLastSearchReq] = useState<SearchRequest | null>(null);
  const [activeHotelPassport, setActiveHotelPassport] = useState<string | null>(null);

  const [watchlistItems, setWatchlistItems] = useState<WatchlistItem[]>([]);
  const [isWatchlistOpen, setIsWatchlistOpen] = useState(false);

  const [topDrops, setTopDrops] = useState<PriceDropItem[]>([]);
  const [airportStats, setAirportStats] = useState<AirportStat[]>([]);
  const [arbitrageCount, setArbitrageCount] = useState<number>(0);

  // Filter state
  const [tableFilters, setTableFilters] = useState<FilterState>(INITIAL_FILTERS);
  const [sortField, setSortField] = useState("price");
  const [sortAsc, setSortAsc] = useState(true);

  // Current active preset config
  const currentPreset = FILTER_PRESETS[activeFilterId] || FILTER_PRESETS["turkey_7_10_days"];

  // Navigation tab switcher synced with URL hash (#/search, #/radar/:id, #/arbitrage, #/monitors)
  const navigateToTab = (tab: "filter" | "search" | "arbitrage" | "my_monitors", filterId?: string) => {
    setActiveTab(tab);
    if (tab === "search") {
      setActiveUserMonitor(null);
      window.location.hash = "#/search";
      if (viewMode === "arbitrage") {
        setViewMode("table");
      }
    } else if (tab === "arbitrage") {
      setActiveUserMonitor(null);
      window.location.hash = "#/arbitrage";
      setViewMode("arbitrage");
    } else if (tab === "my_monitors") {
      setActiveUserMonitor(null);
      window.location.hash = "#/monitors";
    } else {
      const target = filterId || activeFilterId;
      window.location.hash = `#/radar/${target}`;
    }
  };

  // URL Hash Sync for standalone pages on mount & back/forward navigation
  useEffect(() => {
    const syncFromHash = () => {
      const hash = window.location.hash.toLowerCase();
      if (hash.includes("search")) {
        setActiveUserMonitor(null);
        setActiveTab("search");
        if (viewMode === "arbitrage") {
          setViewMode("table");
        }
      } else if (hash.includes("arbitrage")) {
        setActiveUserMonitor(null);
        setActiveTab("filter");
        setViewMode("arbitrage");
      } else if (hash.includes("monitors")) {
        setActiveUserMonitor(null);
        setActiveTab("my_monitors");
      } else if (hash.startsWith("#/monitor/")) {
        const monitorId = hash.replace("#/monitor/", "").split("?")[0];
        if (activeUserMonitorRef.current?.id.toLowerCase() === monitorId.toLowerCase()) {
          setActiveTab("filter");
          return;
        }
        const currentList = userMonitorsRef.current;
        const found = currentList.find((m) => m.id.toLowerCase() === monitorId.toLowerCase());
        if (found) {
          handleOpenMonitorDashboard(found);
        } else if (currentList.length > 0) {
          setActiveTab("my_monitors");
        }
      } else if (hash.startsWith("#/radar/") || hash.startsWith("#/filter/")) {
        // Canonical radars are strictly reserved for the Administrator
        if (!isAdmin) {
          window.location.hash = "#/search";
          setActiveTab("search");
          return;
        }
        const rawId = hash.replace("#/radar/", "").replace("#/filter/", "").split("?")[0];
        if (rawId && FILTER_PRESETS[rawId]) {
          setActiveFilterId(rawId);
          loadFilterResults(rawId);
        }
        setActiveTab("filter");
      } else {
        if (!isAdmin) {
          setActiveTab("search");
        }
      }
    };

    syncFromHash();
    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, [isAdmin]);

  useEffect(() => {
    const hash = window.location.hash.toLowerCase();
    if (hash.startsWith("#/monitor/") && userMonitors.length > 0) {
      const monitorId = hash.replace("#/monitor/", "").split("?")[0];
      if (!activeUserMonitor || activeUserMonitor.id.toLowerCase() !== monitorId.toLowerCase()) {
        const found = userMonitors.find((m) => m.id.toLowerCase() === monitorId.toLowerCase());
        if (found) {
          handleOpenMonitorDashboard(found);
        }
      }
    }
  }, [userMonitors, activeUserMonitor]);

  useEffect(() => {
    // 1. Critical path: Admin loads default radar; regular users and guests land on interactive search
    const hash = window.location.hash;
    if (isAdmin) {
      const hasExplicitFilter = hash.startsWith("#/radar/") || hash.startsWith("#/filter/") || hash.startsWith("#/monitor/");
      if (!hasExplicitFilter && !hash.startsWith("#/search") && !hash.startsWith("#/monitors")) {
        loadFilterResults("turkey_7_10");
      }
    } else {
      if (!hash.includes("arbitrage") && !hash.includes("monitors") && !hash.includes("monitor")) {
        setActiveTab("search");
        if (!hash.includes("search")) {
          window.location.hash = "#/search";
        }
      }
    }

    // 2. User watchlist (lightweight)
    getWatchlist(CURRENT_USER_ID)
      .then((data) => setWatchlistItems(data.items))
      .catch((err) => console.warn("Watchlist fetch failed:", err));

    // 3. Background analytics (non-blocking for main table)
    getTopPriceDrops(10)
      .then((drops) => setTopDrops(drops))
      .catch((err) => console.warn("Top drops fetch failed:", err));

    getAirportComparison("turkey")
      .then((stats) => setAirportStats(stats))
      .catch((err) => console.warn("Airport stats fetch failed:", err));
  }, []);

  const dashboardArbitrageScope = useMemo(() => {
    if (activeUserMonitor) {
      const dest = (activeUserMonitor.filter_params?.destination || "").toLowerCase();
      let country: string | undefined = undefined;
      if (dest.includes("egypt")) country = "Египет";
      else if (dest.includes("turkey")) country = "Турция";
      else if (dest.includes("greece")) country = "Греция";
      else if (dest.includes("cyprus")) country = "Кипр";
      else if (dest.includes("spain")) country = "Испания";

      return {
        filterId: `monitor_${activeUserMonitor.id}`,
        country: country,
        title: activeUserMonitor.title,
      };
    }
    const preset = FILTER_PRESETS[activeFilterId];
    const country =
      preset?.destination === "turkey"
        ? "Турция"
        : preset?.destination === "egypt"
        ? "Египет"
        : preset?.destination === "greece"
        ? "Греция"
        : preset?.destination === "cyprus"
        ? "Кипр"
        : undefined;

    return {
      filterId: activeFilterId,
      country: country,
      title: preset?.title,
    };
  }, [activeUserMonitor, activeFilterId]);

  useEffect(() => {
    if (activeTab !== "filter") {
      setArbitrageCount(0);
      return;
    }

    const { filterId, country } = dashboardArbitrageScope;

    getArbitrageDeals(300, filterId, country)
      .then((deals) => setArbitrageCount(deals.length))
      .catch((err) => {
        console.warn("Arbitrage count fetch failed:", err);
        setArbitrageCount(0);
      });
  }, [activeTab, dashboardArbitrageScope]);

  const loadFilterResults = async (filterId: string) => {
    setIsLoading(true);
    try {
      const preset = FILTER_PRESETS[filterId] || FILTER_PRESETS["turkey_7_10_days"];
      const catResp = await getFilterHotelsCatalog(filterId, {
        maxPrice: preset?.displayPriceCeiling,
      });
      if (catResp.hotels && catResp.hotels.length > 0) {
        setResults(catResp.hotels.map((h) => catalogCardToSearchItem(h, preset)));
        return;
      }
      const resp = await searchTours(preset.searchReq);
      setResults(resp.results);
    } catch (err: any) {
      console.warn("Catalog fetch failed, falling back to search:", err);
      try {
        const preset = FILTER_PRESETS[filterId] || FILTER_PRESETS["turkey_7_10_days"];
        const resp = await searchTours(preset.searchReq);
        setResults(resp.results);
      } catch (e) {
        console.error("Filter search error:", e);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectFilter = (filterId: string) => {
    setActiveUserMonitor(null);
    setActiveFilterId(filterId);
    setActiveTab("filter");
    setTableFilters(INITIAL_FILTERS);
    loadFilterResults(filterId);
    window.location.hash = `#/radar/${filterId}`;
    setIsSidebarOpen(false);
  };

  const handleOpenMonitorDashboard = (monitor: UserMonitor) => {
    setActiveUserMonitor(monitor);
    setActiveTab("filter");
    setTableFilters(INITIAL_FILTERS);
    window.location.hash = `#/monitor/${monitor.id}`;
    if (monitor.filter_params) {
      handleSearch({
        ...(monitor.filter_params as unknown as SearchRequest),
        filter_id: `monitor_${monitor.id}`,
      });
    }
    setIsSidebarOpen(false);
  };

  const handleSearch = async (req: SearchRequest) => {
    setIsLoading(true);
    setLastSearchReq(req);
    try {
      const resp = await searchTours(req);
      setResults(resp.results);
      setTotalFound(resp.total_found || resp.results.length);
      setSearchPage(resp.page || 1);
      setHasMore(Boolean(resp.has_more));
    } catch (err: any) {
      alert("Ошибка поиска: " + (err.message || "Не удалось выполнить запрос"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadMore = async () => {
    if (!lastSearchReq || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const nextPage = searchPage + 1;
      const resp = await searchTours({
        ...lastSearchReq,
        page: nextPage,
        force_live_refresh: true,
      });

      // Merge and deduplicate by hotel_id
      setResults((prev) => {
        const existingIds = new Set(prev.map((h) => h.hotel_id));
        const newItems = resp.results.filter((item) => !existingIds.has(item.hotel_id));
        return [...prev, ...newItems];
      });

      setSearchPage(nextPage);
      setHasMore(Boolean(resp.has_more));
      if (resp.total_found) {
        setTotalFound(resp.total_found);
      }
    } catch (err: any) {
      console.warn("Failed to load more offers:", err);
    } finally {
      setIsLoadingMore(false);
    }
  };

  const handleToggleWatchlist = async (hotel: SearchHotelItem) => {
    if (!currentUser) {
      setAuthModalReason("🔒 Чтобы сохранить отель в избранное и отслеживать изменение цен, войдите или зарегистрируйтесь.");
      setIsAuthModalOpen(true);
      return;
    }

    const cohortHash = hotel.current_offer.cohort_hash;
    const isAlreadyWatched = watchlistItems.some(
      (w) => w.cohort_hash === cohortHash
    );

    if (isAlreadyWatched) {
      const item = watchlistItems.find(
        (w) => w.cohort_hash === cohortHash
      );
      // Optimistic instant remove (<1ms)
      setWatchlistItems((prev) => prev.filter((w) => w.cohort_hash !== cohortHash));
      if (item && item.watch_id && !item.watch_id.startsWith("temp-")) {
        try {
          await deleteWatchlistItem(item.watch_id);
        } catch (e) {
          console.warn("Failed to delete watchlist item on server:", e);
        }
      }
    } else {
      // Optimistic instant add (<1ms) with sensible 5% drop target
      const tempId = `temp-${Date.now()}`;
      const defaultTarget = Math.round(hotel.current_offer.total_price_pln * 0.95);
      const optimisticItem: WatchlistItem = {
        watch_id: tempId,
        user_chat_id: CURRENT_USER_ID,
        cohort_hash: cohortHash,
        hotel_id: hotel.hotel_id,
        hotel_name: hotel.hotel_name,
        country: hotel.country,
        departure_date: hotel.current_offer.departure_date,
        duration_nights: hotel.current_offer.duration_nights,
        airport: hotel.current_offer.airport,
        target_price_pln: defaultTarget,
        latest_price_pln: hotel.current_offer.total_price_pln,
        deal_score: hotel.intelligence?.deal_score || 50,
        deal_badge: hotel.intelligence?.deal_badge || "",
        hopper_verdict: hotel.intelligence?.hopper_verdict || "STABLE",
        target_reached: false,
        created_at: new Date().toISOString(),
      };

      setWatchlistItems((prev) => [optimisticItem, ...prev]);

      try {
        const savedItem = await addToWatchlist({
          cohort_hash: cohortHash,
          user_chat_id: CURRENT_USER_ID,
          target_price_pln: defaultTarget,
          notify_any_drop: true,
        });
        if (savedItem && savedItem.watch_id) {
          setWatchlistItems((prev) =>
            prev.map((w) => (w.watch_id === tempId ? { ...savedItem, hotel_name: hotel.hotel_name } : w))
          );
        }
      } catch (err) {
        console.warn("Failed to persist watchlist item to server:", err);
      }
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
      } else if (activeTab === "filter" && currentPreset?.displayPriceCeiling) {
        if (h.current_offer.total_price_pln > currentPreset.displayPriceCeiling) return false;
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
      if (tableFilters.change === "decrease") {
        const drop = h.intelligence.drop_48h_pct ?? 0;
        if (drop > -0.5) return false;
      }
      if (tableFilters.change === "increase") {
        const drop = h.intelligence.drop_48h_pct ?? 0;
        if (drop < 0.5) return false;
      }
      if (tableFilters.change === "stable") {
        const drop = Math.abs(h.intelligence.drop_48h_pct ?? 0);
        if (drop >= 0.5) return false;
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
        diff = a.intelligence.deal_score - b.intelligence.deal_score;
      } else if (sortField === "ta_rating") {
        diff = (a.ta_rating || 0) - (b.ta_rating || 0);
      } else if (sortField === "hotel") {
        diff = a.hotel_name.localeCompare(b.hotel_name);
      } else if (sortField === "delta48") {
        const a48 = a.intelligence.drop_48h_pct ?? 0;
        const b48 = b.intelligence.drop_48h_pct ?? 0;
        diff = a48 - b48;
      } else if (sortField === "delta_avg") {
        const aAvg = a.intelligence.delta_vs_typical_pct ?? 0;
        const bAvg = b.intelligence.delta_vs_typical_pct ?? 0;
        diff = aAvg - bAvg;
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
      if (field === "deal_score" || field === "ta_rating") {
        setSortAsc(false);
      } else {
        setSortAsc(true);
      }
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
        dropped48hCount: 0,
        dropped48hMaxPln: 0,
        dropped48hMaxPct: 0,
        dropped48hTopHotel: "",
        dropped48hPln: 0,
        lastUpdatedText: "5 мин. назад",
      };
    }

    const minOffer = [...results].sort(
      (a, b) => a.current_offer.total_price_pln - b.current_offer.total_price_pln
    )[0];

    const buyNowHotels = results.filter((h) => h.intelligence.deal_score >= 80);

    // Filter hotels with noticeable price drops over last 48h (ignore <= 0.3% / tiny rounding noise)
    const droppedHotels = results
      .filter((h) => (h.intelligence.drop_48h_pct ?? 0) <= -0.5)
      .map((h) => {
        const pct = Math.abs(h.intelligence.drop_48h_pct ?? 0);
        const savingPln = Math.round(h.current_offer.total_price_pln * (pct / 100));
        return {
          hotel: h,
          pct,
          savingPln,
        };
      })
      .sort((a, b) => b.savingPln - a.savingPln);

    const topDrop = droppedHotels[0] || null;

    return {
      minPricePln: minOffer ? minOffer.current_offer.total_price_pln : 0,
      minPriceHotel: minOffer ? minOffer.hotel_name : "",
      minPriceDate: minOffer ? minOffer.current_offer.departure_date : "",
      buyNowCount: buyNowHotels.length,
      dropped48hCount: droppedHotels.length,
      dropped48hMaxPln: topDrop ? topDrop.savingPln : 0,
      dropped48hMaxPct: topDrop ? Math.round(topDrop.pct) : 0,
      dropped48hTopHotel: topDrop ? topDrop.hotel.hotel_name : "",
      dropped48hPln: topDrop ? topDrop.savingPln : 0,
      lastUpdatedText: "12 мин. назад",
    };
  }, [results]);

  const activeQuickFilter = useMemo<"buy_now" | "drops" | null>(() => {
    if (tableFilters.recommendation === "hot") return "buy_now";
    if (tableFilters.change === "decrease") return "drops";
    return null;
  }, [tableFilters.recommendation, tableFilters.change]);

  const handleQuickFilter = (type: "buy_now" | "drops") => {
    if (type === "buy_now") {
      setTableFilters((prev) => ({
        ...prev,
        recommendation: prev.recommendation === "hot" ? "" : "hot",
      }));
    } else if (type === "drops") {
      setTableFilters((prev) => ({
        ...prev,
        change: prev.change === "decrease" ? "" : "decrease",
      }));
    }
  };

  const dashboardTitle = useMemo(() => {
    if (activeUserMonitor) return activeUserMonitor.title;
    return currentPreset.title;
  }, [activeUserMonitor, currentPreset]);

  const dashboardCountryBadge = useMemo(() => {
    if (activeUserMonitor) {
      const dest = (activeUserMonitor.filter_params?.destination || "").toLowerCase();
      if (dest.includes("egypt")) return "🇪🇬 Египет";
      if (dest.includes("turkey")) return "🇹🇷 Турция";
      if (dest.includes("greece")) return "🇬🇷 Греция";
      if (dest.includes("cyprus")) return "🇨🇾 Кипр";
      if (dest.includes("spain")) return "🇪🇸 Испания";
      return "✈️ Персональный радар";
    }
    return currentPreset.countryBadge;
  }, [activeUserMonitor, currentPreset]);

  const dashboardTargetUrl = useMemo(() => {
    if (activeUserMonitor) {
      return activeUserMonitor.fly_source_url || "";
    }
    return currentPreset.targetUrl;
  }, [activeUserMonitor, currentPreset]);

  const dashboardChips = useMemo(() => {
    if (activeUserMonitor && activeUserMonitor.filter_params) {
      const p = activeUserMonitor.filter_params;
      const ap = p.airports?.length ? p.airports.join(", ") : "Все аэропорты Польши";
      const dates = p.dates?.start_date_min ? `${p.dates.start_date_min} — ${p.dates.start_date_max}` : "Гибкие даты";
      const party = p.travelers ? `${p.travelers.adults || 2} взр` + (p.travelers.children ? ` + ${p.travelers.children} реб` : "") : "2 взр";
      const hotelClass = `${p.stars_min || 4}★ – 5★ ${p.catering === "all_inclusive" ? "All Inclusive" : "С питанием"}`;
      const budget = activeUserMonitor.max_budget_pln ? `до ${activeUserMonitor.max_budget_pln.toLocaleString("ru-RU")} zł` : "Любой бюджет";
      return {
        airports: ap,
        dates: dates,
        party: party,
        hotelClass: hotelClass,
        budget: budget,
      };
    }
    return currentPreset.chips;
  }, [activeUserMonitor, currentPreset]);

  const dashboardDestination = useMemo(() => {
    if (activeUserMonitor) {
      return activeUserMonitor.filter_params?.destination || "egypt";
    }
    return currentPreset.destination;
  }, [activeUserMonitor, currentPreset]);

  const dashboardFilterIdForAnalytics = useMemo(() => {
    if (activeUserMonitor) {
      return `monitor_${activeUserMonitor.id}`;
    }
    return activeFilterId;
  }, [activeUserMonitor, activeFilterId]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* V1 Collapsible Left Sidebar */}
      <SidebarNavigation
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        activeFilterId={activeFilterId}
        onSelectFilter={handleSelectFilter}
        onOpenSearch={() => {
          navigateToTab("search");
          setIsSidebarOpen(false);
        }}
        onOpenArbitrage={() => {
          navigateToTab("arbitrage");
          setIsSidebarOpen(false);
        }}
        onOpenMonitors={() => {
          navigateToTab("my_monitors");
          setIsSidebarOpen(false);
        }}
        userMonitors={userMonitors}
        activeUserMonitorId={activeUserMonitor?.id}
        onSelectUserMonitor={handleOpenMonitorDashboard}
        activeTab={activeTab}
        currentUser={currentUser}
        isAdmin={isAdmin}
        onOpenAuth={() => {
          setAuthModalReason(null);
          setIsAuthModalOpen(true);
        }}
      />

      {/* Top Navbar */}
      <header className="bg-slate-900 text-white py-3 px-4 sm:px-6 border-b border-slate-800 sticky top-0 z-30 shadow-md">
        <div className="max-w-[1880px] mx-auto flex items-center justify-between">
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

            {activeTab === "search" ? (
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-sky-500 flex items-center justify-center font-extrabold text-white shadow-md shadow-blue-500/20 text-base">
                  🔍
                </div>
                <div>
                  <div className="text-sm font-black tracking-tight flex items-center gap-2">
                    <span className="bg-gradient-to-r from-blue-400 via-indigo-300 to-sky-300 bg-clip-text text-transparent">
                      TRAVEL SEARCH
                    </span>
                    <span className="text-[9px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1.5 py-0.5 rounded-full flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                      LIVE META ENGINE
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 flex items-center gap-2">
                    <span>Поиск туров по всем странам и датам</span>
                    <span className="text-slate-600">•</span>
                    <span className="text-slate-300">Neon DB (2.12M цен) + Fly.pl Live</span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigateToTab("filter")}
                  className="hidden xl:inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-semibold bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/80 transition-all ml-2"
                  title="Вернуться к мониторингу 30 фильтров"
                >
                  <span>← К радару мониторинга</span>
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-extrabold text-white shadow-md shadow-blue-500/20">
                  {activeUserMonitor ? "📡" : "✈️"}
                </div>
                <div>
                  <div className="text-sm font-black tracking-tight flex items-center gap-2">
                    <span>TRAVEL MONITOR</span>
                    <span className="text-[9px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 px-1.5 py-0.5 rounded-full">
                      {activeUserMonitor ? "📡 МОЙ РАДАР" : "v2.0 DUAL-ENGINE"}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-400 truncate max-w-sm sm:max-w-md">
                    {dashboardTitle}
                  </p>
                </div>
                {activeUserMonitor && (
                  <button
                    type="button"
                    onClick={() => {
                      if (activeUserMonitor?.filter_params) {
                        handleSearch({
                          ...(activeUserMonitor.filter_params as unknown as SearchRequest),
                          filter_id: `monitor_${activeUserMonitor.id}`,
                          force_live_refresh: true,
                        });
                      }
                    }}
                    className="ml-2 px-2.5 py-1 rounded-xl bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 font-bold text-xs border border-sky-500/30 transition-colors flex items-center gap-1 cursor-pointer"
                    title="Обновить замер цен с Fly.pl"
                  >
                    <RefreshCw className={`w-3 h-3 ${isLoading ? "animate-spin" : ""}`} />
                    <span>Обновить ⚡</span>
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-1 bg-slate-800/90 p-1 rounded-2xl border border-slate-700">
              {isAdmin && (
                <button
                  type="button"
                  data-testid="admin-radar-nav-btn"
                  onClick={() => {
                    navigateToTab("filter");
                    setViewMode("table");
                  }}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                    activeTab === "filter" && viewMode !== "arbitrage"
                      ? "bg-amber-500 text-slate-950 shadow-sm"
                      : "text-amber-400 hover:text-white hover:bg-slate-700/50"
                  }`}
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span>👑 Радары админа</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => navigateToTab("search")}
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
                onClick={() => navigateToTab("my_monitors")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "my_monitors"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <span>📡 Мои мониторинги</span>
                {userMonitors.length > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full bg-sky-500/30 text-sky-300 text-[10px] font-black">
                    {userMonitors.length}
                  </span>
                )}
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

            {/* Admin Onboarding CTA only for system owner if not yet admin or if no admin exists */}
            {currentUser && !isAdmin && (!adminStatus.has_admin || currentUser.email.toLowerCase() === "jancker2a@gmail.com") && (
              <button
                type="button"
                data-testid="claim-admin-btn"
                onClick={handleClaimAdmin}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-xs shadow-sm transition-all cursor-pointer animate-pulse"
                title="Назначить свой аккаунт Администратором системы"
              >
                <Crown className="w-3.5 h-3.5 text-slate-950" />
                <span className="hidden sm:inline">👑 Назначить меня админом</span>
              </button>
            )}

            {/* User Profile / Auth Button */}
            {currentUser ? (
              <div className="flex items-center gap-1.5 pl-2 border-l border-slate-700">
                <button
                  type="button"
                  data-testid="user-profile-btn"
                  onClick={() => navigateToTab("my_monitors")}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-bold transition-colors cursor-pointer"
                  title="Мой профиль и мониторинги"
                >
                  <UserIcon className="w-3.5 h-3.5 text-blue-400" />
                  <span className="max-w-[110px] truncate hidden sm:inline">
                    {currentUser.full_name || currentUser.email.split("@")[0]}
                  </span>
                  {isAdmin && (
                    <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1 py-0.2 rounded border border-amber-500/30 font-black">
                      👑
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  data-testid="logout-btn"
                  onClick={async () => {
                    await logoutUser();
                    setCurrentUser(null);
                    setUserMonitors([]);
                  }}
                  className="p-2 rounded-xl bg-slate-800 hover:bg-rose-950/60 text-slate-400 hover:text-rose-400 border border-slate-700 transition-colors cursor-pointer"
                  title="Выйти из аккаунта"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <button
                type="button"
                data-testid="login-nav-btn"
                onClick={() => {
                  setAuthModalReason(null);
                  setIsAuthModalOpen(true);
                }}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-sm transition-all cursor-pointer"
              >
                <UserIcon className="w-3.5 h-3.5" />
                <span>Войти</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-[1880px] mx-auto px-4 sm:px-6 lg:px-8 py-5 flex-1 w-full space-y-6">
        {/* If in My Monitors Tab */}
        {activeTab === "my_monitors" ? (
          <UserMonitorsView
            currentUser={currentUser}
            monitors={userMonitors}
            isLoading={isLoadingMonitors}
            onRefresh={loadUserMonitors}
            onOpenCreateModal={() => {
              if (!currentUser) {
                setAuthModalReason("🔒 Для создания персонального мониторинга цен и получения уведомлений необходимо войти или зарегистрироваться.");
                setIsAuthModalOpen(true);
                return;
              }
              setIsCreateMonitorOpen(true);
            }}
            onRequestAuth={() => {
              setAuthModalReason("🔒 Войдите или зарегистрируйтесь, чтобы создать свой мониторинг поиска или тура.");
              setIsAuthModalOpen(true);
            }}
            onOpenDashboard={handleOpenMonitorDashboard}
          />
        ) : (
          <>
            {/* If in Search Tab */}
            {activeTab === "search" && (
              <div className="mb-4">
                <SearchHeader
                  onSearch={handleSearch}
                  isLoading={isLoading}
                  onSaveMonitor={() => {
                    if (!currentUser) {
                      setAuthModalReason("🔒 Для сохранения текущего поиска в персональный мониторинг цен необходимо войти или зарегистрироваться.");
                      setIsAuthModalOpen(true);
                      return;
                    }
                    setIsCreateMonitorOpen(true);
                  }}
                />
              </div>
            )}

        {/* Filter dashboard headers & folds: in BOTH canonical radars and user monitors */}
        {activeTab === "filter" && (
          <>
            {/* 1. Hero Terminal Banner with Metadata Chips & 4 White KPI Cards */}
            <HeroTerminal
              title={dashboardTitle}
              countryBadge={dashboardCountryBadge}
              targetUrl={dashboardTargetUrl}
              chips={dashboardChips}
              kpi={heroKpi}
              activeQuickFilter={activeQuickFilter}
              onQuickFilter={handleQuickFilter}
            />

            {/* 2. Top Fold: 🧠 AI-анализ рынка и прогноз цен */}
            <AiMarketBriefing
              filterId={dashboardFilterIdForAnalytics}
              filterTitle={dashboardTitle}
              buyNowCount={heroKpi.buyNowCount}
              onOpenPassport={(hotelId) => setActiveHotelPassport(hotelId)}
            />

            {/* 3. Time Series Chart: 📉 Средняя цена ТОП-10 дешёвых предложений */}
            <Top10TimelineChart
              filterId={dashboardFilterIdForAnalytics}
              destination={dashboardDestination}
            />

            {/* 4. Second Fold: 📊 Расширенная аналитика и тренды рынка */}
            <AnalyticsFold
              hotels={results}
              topDrops={topDrops}
              airportStats={airportStats}
              filterId={dashboardFilterIdForAnalytics}
              onSelectHotel={(hotelId) => setActiveHotelPassport(hotelId)}
              onFilterByDeparture={(depDate) => {
                if (depDate) {
                  setTableFilters((prev) => ({ ...prev, search: depDate }));
                }
              }}
            />
          </>
        )}

        {/* 5. Universal Toolbar: Вид (Карточки / Таблица / Арбитраж) + Фильтры */}
        <UniversalTableFilters
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          filters={tableFilters}
          onFilterChange={setTableFilters}
          onClear={() => setTableFilters(INITIAL_FILTERS)}
          regions={availableRegions}
          arbitrageCount={activeTab === "filter" ? arbitrageCount : 0}
          showArbitrageTab={activeTab === "filter"}
        />

        {/* 6. Mode Switch Views */}
        {viewMode === "arbitrage" ? (
          <GermanArbitrageView
            filterId={activeTab === "filter" ? dashboardArbitrageScope.filterId : undefined}
            country={activeTab === "filter" ? dashboardArbitrageScope.country : undefined}
            filterTitle={activeTab === "filter" ? dashboardArbitrageScope.title : undefined}
          />
        ) : viewMode === "table" ? (
          <HotelTableView
            hotels={filteredHotels}
            isLoading={isLoading}
            onOpenPassport={(id) => setActiveHotelPassport(id)}
            onToggleWatchlist={handleToggleWatchlist}
            watchedCohortHashes={watchedCohortHashes}
            sortField={sortField}
            sortAsc={sortAsc}
            onSort={handleSort}
            totalFound={activeTab === "search" ? totalFound : undefined}
          />
        ) : (
          <div className="space-y-4 relative" id="cardsSection">
            {/* Cards Section Header */}
            <div className="flex items-center justify-between">
              <h3 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
                <span>🏨</span>
                <span>Все отели • клик по карточке откроет паспорт справа</span>
              </h3>
              <span className="text-sm text-slate-500 font-semibold">
                Показано <b className="text-slate-900 font-black">{filteredHotels.length}</b>
                {activeTab === "search" && totalFound > filteredHotels.length ? ` из ${totalFound}` : ""} отелей
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

            {isLoading && filteredHotels.length === 0 ? (
              <LoadingSpinner
                variant="skeleton-cards"
                label="Загрузка карточек отелей..."
                description="Синхронизация котировок и фотографий"
              />
            ) : (
              <>
                {isLoading && (
                  <LoadingSpinner
                    variant="overlay"
                    size="lg"
                    label="Обновление карточек отелей..."
                    description="Синхронизация актуальных котировок"
                  />
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
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
              </>
            )}
          </div>
        )}

        {/* Load More Button for Interactive Search */}
        {activeTab === "search" && (hasMore || (totalFound > 0 && results.length < totalFound)) && (
          <div className="flex flex-col items-center justify-center py-6 gap-2">
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={isLoadingMore}
              className="inline-flex items-center gap-2.5 px-6 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold text-sm shadow-md hover:shadow-lg transition-all cursor-pointer"
            >
              {isLoadingMore ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Подгружаем следующие предложения с Fly.pl...</span>
                </>
              ) : (
                <>
                  <span>🔄 Загрузить ещё предложения</span>
                  <span className="bg-blue-700 px-2.5 py-0.5 rounded-full text-xs font-black">
                    +{Math.min(100, Math.max(1, totalFound - results.length))}
                  </span>
                </>
              )}
            </button>
            <span className="text-xs text-slate-500 font-medium">
              Показано {results.length} из {totalFound} найденных отелей
            </span>
          </div>
        )}
          </>
        )}
      </main>

      {/* 7. Hotel AI Passport Drawer (Slides out from RIGHT) */}
      {(() => {
        const activePassportHotel = results.find(
          (h) =>
            h.hotel_id === activeHotelPassport ||
            (activeHotelPassport &&
              h.hotel_name.trim().toLowerCase() === activeHotelPassport.trim().toLowerCase())
        ) || null;
        const isPassportWatched = activePassportHotel
          ? watchedCohortHashes.has(activePassportHotel.current_offer.cohort_hash)
          : false;

        return (
          <HotelPassportDrawer
            hotelId={activeHotelPassport}
            filterId={
              activeTab === "filter"
                ? (activeUserMonitor ? `monitor_${activeUserMonitor.id}` : activeFilterId)
                : undefined
            }
            hotelItem={activePassportHotel}
            searchTravelers={
              activeUserMonitor?.filter_params?.travelers
                ? activeUserMonitor.filter_params.travelers
                : activeUserMonitor?.filter_params
                ? {
                    adults: activeUserMonitor.filter_params.adults || 2,
                    children: activeUserMonitor.filter_params.children || 0,
                    children_ages: [],
                  }
                : activeTab === "search"
                ? (lastSearchReq?.travelers || { adults: 1, children: 0, children_ages: [] })
                : undefined
            }
            isWatched={isPassportWatched}
            onToggleWatchlist={activePassportHotel ? () => handleToggleWatchlist(activePassportHotel) : undefined}
            onSwitchFilter={(newFilterId) => handleSelectFilter(newFilterId)}
            onClose={() => setActiveHotelPassport(null)}
          />
        );
      })()}

      {/* Watchlist Drawer */}
      <WatchlistDrawer
        isOpen={isWatchlistOpen}
        onClose={() => setIsWatchlistOpen(false)}
        items={watchlistItems}
        onDeleteItem={handleDeleteWatchlist}
      />

      {/* Auth Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => {
          setIsAuthModalOpen(false);
          setAuthModalReason(null);
        }}
        reasonMessage={authModalReason}
        hasAdmin={adminStatus.has_admin}
        onAuthSuccess={(u) => {
          setCurrentUser(u);
          if (u.role === "ADMIN") {
            setAdminStatus({ has_admin: true, admin_email: u.email });
          }
          loadUserMonitors();
          setAuthModalReason(null);
        }}
      />

      {/* Create User Monitor Modal */}
      <CreateMonitorModal
        isOpen={isCreateMonitorOpen}
        onClose={() => setIsCreateMonitorOpen(false)}
        onCreated={(m) => {
          setUserMonitors((prev) => [m, ...prev]);
          handleOpenMonitorDashboard(m);
        }}
        currentSearchReq={lastSearchReq || undefined}
        currentUser={currentUser}
        onRequestAuth={() => {
          setIsCreateMonitorOpen(false);
          setIsAuthModalOpen(true);
        }}
      />
    </div>
  );
};
