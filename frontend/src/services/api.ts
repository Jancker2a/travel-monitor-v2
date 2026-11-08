import {
  SearchRequest,
  SearchResponse,
  WatchlistItem,
  HotelPassport,
  PriceDropItem,
  AirportStat,
  MarketOverview,
} from "../types";

const API_BASE = "";

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

export async function getHotelPassport(hotelId: string): Promise<HotelPassport> {
  const resp = await fetch(`${API_BASE}/api/v2/hotels/${hotelId}/history`);
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

