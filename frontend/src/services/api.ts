import {
  SearchRequest,
  SearchResponse,
  WatchlistItem,
  HotelPassport,
  PriceDropItem,
  AirportStat,
  MarketOverview,
  TimelineResponse,
  HotelCatalogResponse,
  MarketOracleData,
  FilterDeparturesData,
} from "../types";

const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";

export async function searchTours(req: SearchRequest): Promise<SearchResponse> {
  const resp = await fetch(`${API_BASE}/api/v2/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка поиска (${resp.status}): ${await resp.text()}`);
  }
  return resp.json();
}

export async function getHotelPassport(
  hotelId: string,
  filterId?: string,
  hints?: {
    name?: string;
    stars?: number;
    country?: string;
    region?: string;
    current_price?: number;
    ta_rating?: number;
    main_image_url?: string;
  }
): Promise<HotelPassport> {
  const params = new URLSearchParams();
  if (filterId) params.set("filter_id", filterId);
  if (hints?.name) params.set("name", hints.name);
  if (hints?.stars) params.set("stars", String(hints.stars));
  if (hints?.country) params.set("country", hints.country);
  if (hints?.region) params.set("region", hints.region);
  if (hints?.current_price) params.set("current_price", String(hints.current_price));
  if (hints?.ta_rating) params.set("ta_rating", String(hints.ta_rating));
  if (hints?.main_image_url) params.set("main_image_url", hints.main_image_url);

  const qs = params.toString() ? `?${params.toString()}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/hotels/${encodeURIComponent(hotelId)}/history${qs}`);
  if (!resp.ok) {
    throw new Error(`Ошибка получения паспорта отеля (${resp.status})`);
  }
  return resp.json();
}

export async function addToWatchlist(data: {
  cohort_hash: string;
  user_chat_id: string;
  target_price_pln?: number;
  notify_any_drop?: boolean;
}): Promise<WatchlistItem> {
  const resp = await fetch(`${API_BASE}/api/v2/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка добавления в Watchlist (${resp.status})`);
  }
  return resp.json();
}

export async function getWatchlist(userId: string): Promise<{ total: number; items: WatchlistItem[] }> {
  const resp = await fetch(`${API_BASE}/api/v2/watchlist/${userId}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки Watchlist (${resp.status})`);
  }
  return resp.json();
}

export async function deleteWatchlistItem(watchId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/v2/watchlist/${watchId}`, {
    method: "DELETE",
  });
  if (!resp.ok) {
    throw new Error(`Ошибка удаления из Watchlist (${resp.status})`);
  }
}

export async function getTopPriceDrops(limit: number = 12): Promise<PriceDropItem[]> {
  const resp = await fetch(`${API_BASE}/api/v2/analytics/top-drops?limit=${limit}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки топ падений цен (${resp.status})`);
  }
  return resp.json();
}

export async function getTop10Timeline(
  filterId?: string,
  destination?: string
): Promise<{ date: string; avg_price: number; min_price: number; max_price: number }[]> {
  const params = new URLSearchParams();
  if (filterId) params.append("filter_id", filterId);
  if (destination) params.append("destination", destination);
  const q = params.toString() ? `?${params.toString()}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/analytics/top10-timeline${q}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки таймлайна ТОП-10 (${resp.status})`);
  }
  return resp.json();
}

export async function getAirportComparison(destination?: string): Promise<AirportStat[]> {
  const q = destination ? `?destination=${encodeURIComponent(destination)}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/analytics/airports${q}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки сравнения аэропортов (${resp.status})`);
  }
  return resp.json();
}

export async function getMarketOverview(): Promise<MarketOverview> {
  const resp = await fetch(`${API_BASE}/api/v2/analytics/overview`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки сводки рынка (${resp.status})`);
  }
  return resp.json();
}

export async function getHotelNormalizedHistory(hotelId: string): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/v2/hotels/${encodeURIComponent(hotelId)}/normalized-history`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки нормализованной истории (${resp.status})`);
  }
  return resp.json();
}

export async function getFilterMonitors(): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки мониторов фильтров (${resp.status})`);
  }
  return resp.json();
}

export async function runMonitorNow(monitorId: string): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors/${encodeURIComponent(monitorId)}/run-now`, {
    method: "POST",
  });
  if (!resp.ok) {
    throw new Error(`Ошибка запуска монитора (${resp.status})`);
  }
  return resp.json();
}

export async function createCustomMonitor(data: any): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка создания монитора (${resp.status})`);
  }
  return resp.json();
}

export async function getArbitrageDeals(
  minSavings: number = 300,
  filterId?: string | null,
  country?: string | null
): Promise<any[]> {
  const params = new URLSearchParams();
  params.set("min_savings", String(minSavings));
  if (filterId) params.set("filter_id", filterId);
  if (country) params.set("country", country);

  const resp = await fetch(`${API_BASE}/api/v2/arbitrage?${params.toString()}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки немецкого арбитража (${resp.status})`);
  }
  return resp.json();
}

export async function getOffersCountTimeline(): Promise<{ day: string; count: number }[]> {
  const resp = await fetch(`${API_BASE}/api/v2/analytics/offers-count-timeline`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки таймлайна предложений (${resp.status})`);
  }
  return resp.json();
}

export async function getEarlyBookingAnalytics(): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/v2/analytics/early-booking`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки раннего бронирования (${resp.status})`);
  }
  return resp.json();
}

// -------------------------------------------------------------
// V2 Dedicated High-Performance Dashboard API Endpoints
// -------------------------------------------------------------

export async function getFilterTop10Timeline(
  filterId: string,
  range: string = "all",
  ceilingPln?: number
): Promise<TimelineResponse> {
  const params = new URLSearchParams();
  if (range && range !== "all") params.append("range", range);
  if (ceilingPln) params.append("ceiling_pln", String(ceilingPln));
  const q = params.toString() ? `?${params.toString()}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/filters/${encodeURIComponent(filterId)}/top10-timeline${q}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки таймлайна ТОП-10 (${resp.status})`);
  }
  return resp.json();
}

export async function getFilterMarketOracle(filterId: string): Promise<MarketOracleData> {
  const resp = await fetch(`${API_BASE}/api/v2/filters/${encodeURIComponent(filterId)}/oracle`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки AI Oracle брифинга (${resp.status})`);
  }
  return resp.json();
}

export async function getFilterHotelsCatalog(
  filterId: string,
  params?: {
    sortBy?: string;
    order?: string;
    stars?: number;
    search?: string;
    minPrice?: number;
    maxPrice?: number;
  }
): Promise<HotelCatalogResponse> {
  const qParams = new URLSearchParams();
  if (params?.sortBy) qParams.append("sort_by", params.sortBy);
  if (params?.order) qParams.append("order", params.order);
  if (params?.stars) qParams.append("stars", String(params.stars));
  if (params?.search) qParams.append("search", params.search);
  if (params?.minPrice) qParams.append("min_price", String(params.minPrice));
  if (params?.maxPrice) qParams.append("max_price", String(params.maxPrice));
  const q = qParams.toString() ? `?${qParams.toString()}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/filters/${encodeURIComponent(filterId)}/hotels${q}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки каталога отелей (${resp.status})`);
  }
  return resp.json();
}

export async function getFilterDepartures(filterId: string): Promise<FilterDeparturesData> {
  const resp = await fetch(`${API_BASE}/api/v2/filters/${encodeURIComponent(filterId)}/departures`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки вылетов фильтра (${resp.status})`);
  }
  return resp.json();
}



