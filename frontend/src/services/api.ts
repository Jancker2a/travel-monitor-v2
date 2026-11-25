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
  FilterAnalyticsData,
  ArbitrageStatus,
  UserProfile,
  AuthTokenResponse,
  FlyUrlParseResponse,
  UserMonitor,
} from "../types";

const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";

const AUTH_TOKEN_KEY = "tm_access_token";
const AUTH_USER_KEY = "tm_user_profile";

export function getStoredToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function setStoredToken(token: string) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function getStoredUser(): UserProfile | null {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: UserProfile) {
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// ══════════════════════════════════════════════════════════════
// AUTHENTICATION APIs
// ══════════════════════════════════════════════════════════════

export async function registerUser(data: {
  email: string;
  password: string;
  full_name?: string;
  telegram_chat_id?: string;
}): Promise<AuthTokenResponse> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка регистрации" }));
    throw new Error(err.detail || `Ошибка регистрации (${resp.status})`);
  }
  const result: AuthTokenResponse = await resp.json();
  setStoredToken(result.access_token);
  setStoredUser(result.user);
  return result;
}

export async function loginUser(data: {
  email: string;
  password: string;
}): Promise<AuthTokenResponse> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Неверный логин или пароль" }));
    throw new Error(err.detail || `Ошибка входа (${resp.status})`);
  }
  const result: AuthTokenResponse = await resp.json();
  setStoredToken(result.access_token);
  setStoredUser(result.user);
  return result;
}

export async function fetchCurrentUser(): Promise<UserProfile> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/me`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    clearAuth();
    throw new Error("Сессия истекла");
  }
  const user: UserProfile = await resp.json();
  setStoredUser(user);
  return user;
}

export async function logoutUser(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/v2/auth/logout`, {
      method: "POST",
      headers: getAuthHeaders(),
    });
  } catch {}
  clearAuth();
}

export interface AdminStatusResponse {
  has_admin: boolean;
  admin_email?: string | null;
}

export async function getAdminStatus(): Promise<AdminStatusResponse> {
  try {
    const resp = await fetch(`${API_BASE}/api/v2/auth/admin-status`);
    if (!resp.ok) {
      return { has_admin: true };
    }
    return await resp.json();
  } catch {
    return { has_admin: true };
  }
}

export async function claimAdmin(adminKey?: string): Promise<UserProfile> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/claim-admin`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(adminKey ? { admin_key: adminKey } : {}),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка назначения администратора" }));
    throw new Error(err.detail || "Не удалось назначить роль администратора");
  }
  const user: UserProfile = await resp.json();
  setStoredUser(user);
  return user;
}

// ══════════════════════════════════════════════════════════════
// USER MONITORS APIs (Multi-tenant search monitoring)
// ══════════════════════════════════════════════════════════════

export async function parseFlyUrl(url: string): Promise<FlyUrlParseResponse> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors/parse-url`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ url }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка парсинга ссылки" }));
    throw new Error(err.detail || `Ошибка разбора ссылки (${resp.status})`);
  }
  return resp.json();
}

export async function listUserMonitors(): Promise<UserMonitor[]> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки мониторингов (${resp.status})`);
  }
  return resp.json();
}

export async function createUserMonitor(data: {
  title: string;
  source_type: string;
  fly_source_url?: string;
  filter_params: Record<string, any>;
  check_interval_hours?: number;
  min_drop_pct?: number;
  max_budget_pln?: number;
  notify_telegram?: boolean;
  notify_email?: boolean;
}): Promise<UserMonitor> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка создания мониторинга" }));
    throw new Error(err.detail || `Ошибка создания мониторинга (${resp.status})`);
  }
  return resp.json();
}

export async function toggleUserMonitor(monitorId: string): Promise<UserMonitor> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors/${encodeURIComponent(monitorId)}/toggle`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка переключения статуса (${resp.status})`);
  }
  return resp.json();
}

export async function deleteUserMonitor(monitorId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors/${encodeURIComponent(monitorId)}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка удаления мониторинга (${resp.status})`);
  }
}

export async function runUserMonitorNow(monitorId: string): Promise<any> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors/${encodeURIComponent(monitorId)}/run-now`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка запуска сканирования" }));
    throw new Error(err.detail || `Ошибка запуска (${resp.status})`);
  }
  return resp.json();
}

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
    adults?: number;
    children?: number;
    duration_nights?: number;
    departure_date?: string;
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
  if (hints?.adults !== undefined) params.set("adults", String(hints.adults));
  if (hints?.children !== undefined) params.set("children", String(hints.children));
  if (hints?.duration_nights !== undefined) params.set("duration_nights", String(hints.duration_nights));
  if (hints?.departure_date) params.set("departure_date", hints.departure_date);

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
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Ошибка удаления из Watchlist (${resp.status})`);
  }
}

export async function updateWatchlistItem(
  watchId: string,
  updates: {
    target_price_pln?: number | null;
    alert_threshold_pct?: number | null;
    min_deal_score?: number | null;
    notify_any_drop?: boolean;
    is_active?: boolean;
  }
): Promise<WatchlistItem> {
  const resp = await fetch(`${API_BASE}/api/v2/watchlist/${encodeURIComponent(watchId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка обновления вотчлиста" }));
    throw new Error(err.detail || `Ошибка обновления (${resp.status})`);
  }
  return resp.json();
}

export async function updateUserProfile(updates: Partial<UserProfile>): Promise<UserProfile> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/me`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка сохранения профиля" }));
    throw new Error(err.detail || `Ошибка сохранения (${resp.status})`);
  }
  return resp.json();
}

export async function sendTestDailyDigest(): Promise<{
  success: boolean;
  message: string;
  chat_id?: string;
  simulated?: boolean;
}> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/test-digest`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: "Ошибка отправки тестового дайджеста" }));
    throw new Error(err.message || err.detail || `Ошибка (${resp.status})`);
  }
  return resp.json();
}

export async function getDashboardAlertSubscription(
  monitorId: string,
  title?: string
): Promise<any> {
  const q = title ? `?title=${encodeURIComponent(title)}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/monitors/alerts/${encodeURIComponent(monitorId)}${q}`, {
    headers: { ...getAuthHeaders() },
  });
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки настроек алертов (${resp.status})`);
  }
  return resp.json();
}

export async function updateDashboardAlertSubscription(
  monitorId: string,
  data: any,
  title?: string
): Promise<any> {
  const q = title ? `?title=${encodeURIComponent(title)}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/monitors/alerts/${encodeURIComponent(monitorId)}${q}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "Ошибка сохранения алертов мониторинга" }));
    throw new Error(err.detail || `Ошибка сохранения (${resp.status})`);
  }
  return resp.json();
}

export async function sendTestDashboardAlert(
  monitorId: string,
  title?: string
): Promise<{
  success: boolean;
  message: string;
  offer_found?: boolean;
  hotel_name?: string;
  price_pln?: number;
  simulated?: boolean;
}> {
  const q = title ? `?title=${encodeURIComponent(title)}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/monitors/alerts/${encodeURIComponent(monitorId)}/test${q}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: "Ошибка отправки тестового алерта мониторинга" }));
    throw new Error(err.message || err.detail || `Ошибка (${resp.status})`);
  }
  return resp.json();
}

export async function listDashboardAlertSubscriptions(): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/api/v2/monitors/alerts`, {
    headers: { ...getAuthHeaders() },
  });
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки подписок (${resp.status})`);
  }
  return resp.json();
}


export async function sendTestTelegram(chatId?: string): Promise<{
  success: boolean;
  message: string;
  chat_id?: string;
  simulated?: boolean;
}> {
  const resp = await fetch(`${API_BASE}/api/v2/auth/test-telegram`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ chat_id: chatId || null }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: "Ошибка отправки теста" }));
    throw new Error(err.message || err.detail || `Ошибка (${resp.status})`);
  }
  return resp.json();
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

export async function getEarlyBookingAnalytics(filterId?: string): Promise<any> {
  const q = filterId ? `?filter_id=${encodeURIComponent(filterId)}` : "";
  const resp = await fetch(`${API_BASE}/api/v2/analytics/early-booking${q}`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки раннего бронирования (${resp.status})`);
  }
  return resp.json();
}

export async function getArbitrageStatus(): Promise<ArbitrageStatus> {
  const resp = await fetch(`${API_BASE}/api/v2/arbitrage/status`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки статуса Check24 (${resp.status})`);
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

export async function getFilterAnalytics(filterId: string): Promise<FilterAnalyticsData> {
  const resp = await fetch(`${API_BASE}/api/v2/filters/${encodeURIComponent(filterId)}/analytics`);
  if (!resp.ok) {
    throw new Error(`Ошибка загрузки аналитики фильтра (${resp.status})`);
  }
  return resp.json();
}



