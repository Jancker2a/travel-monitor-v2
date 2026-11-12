export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  telegram_chat_id?: string;
  is_active: boolean;
  created_at?: string;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  user: UserProfile;
}

export interface FlyUrlParseResponse {
  is_valid: boolean;
  parsed_title: string;
  destination?: string;
  region?: string;
  departure_airports: string[];
  date_from?: string;
  date_to?: string;
  duration_min?: number;
  duration_max?: number;
  adults: number;
  children: number;
  catering?: string;
  stars?: number;
  structured_search_request: Record<string, any>;
  error_message?: string;
}

export interface UserMonitor {
  id: string;
  user_id: string;
  title: string;
  source_type: string;
  fly_source_url?: string;
  filter_params: Record<string, any>;
  check_interval_hours: number;
  min_drop_pct: number;
  max_budget_pln?: number;
  notify_telegram: boolean;
  notify_email: boolean;
  is_active: boolean;
  status: "IDLE" | "RUNNING" | "SUCCESS" | "ERROR";
  last_checked_at?: string;
  last_offers_count: number;
  last_min_price_pln?: number;
  last_error_message?: string;
  created_at?: string;
}

export interface SearchDates {
  start_date_min: string;
  start_date_max: string;
}

export interface SearchDuration {
  min_nights: number;
  max_nights: number;
}

export interface SearchTravelers {
  adults: number;
  children: number;
  children_ages: number[];
}

export interface SearchRequest {
  destination: string;
  region?: string;
  filter_id?: string;
  dates: SearchDates;
  duration: SearchDuration;
  travelers: SearchTravelers;
  airports: string[];
  catering?: string;
  stars_min?: number;
  price_min_pln?: number;
  price_max_pln?: number;
  order_by?: string;
  page?: number;
  page_size?: number;
  force_live_refresh?: boolean;
}

export interface OfferSummary {
  cohort_hash: string;
  total_price_pln: number;
  price_per_night_pax: number;
  departure_date: string;
  duration_nights: number;
  airport: string;
  adults?: number;
  children?: number;
  operator?: string;
  booking_url?: string;
}

export interface HotelIntelligence {
  deal_score: number;
  deal_badge: string;
  hopper_verdict: "BUY NOW" | "WAIT" | "OVERPRICED" | string;
  hopper_confidence: number;
  recommendation: string;
  drop_48h_pct?: number | null;
  delta_vs_typical_pct?: number | null;
  historic_min_pln: number;
  typical_median_pln: number;
  german_arbitrage_diff_pln?: number | null;
  is_budget_tier?: boolean;
}

export interface SearchHotelItem {
  hotel_id: string;
  hotel_name: string;
  stars: number;
  region?: string;
  country: string;
  main_image_url?: string;
  ta_rating?: number;
  ta_reviews?: number;
  beach_line?: number;
  beach_type?: string;
  has_aquapark?: boolean;
  has_heated_pools?: boolean;
  specs?: Record<string, any>;
  current_offer: OfferSummary;
  intelligence: HotelIntelligence;
  history_sparkline: number[];
  normalized_benchmark_1p_8n?: number;
  pure_hotel_night_pln?: number;
}

export interface SearchResponse {
  search_id: string;
  cached: boolean;
  total_found: number;
  page?: number;
  has_more?: boolean;
  results: SearchHotelItem[];
}

export interface WatchlistItem {
  watch_id: string;
  user_chat_id: string;
  cohort_hash: string;
  hotel_id: string;
  hotel_name: string;
  country: string;
  departure_date: string;
  duration_nights: number;
  airport: string;
  target_price_pln?: number;
  latest_price_pln: number;
  deal_score: number;
  deal_badge: string;
  hopper_verdict: string;

  data_maturity_tier?: number;
  maturity_explanation?: string;
  user_query_scope?: {
    adults: number;
    children: number;
    duration_nights: number;
  };
  target_reached: boolean;
  booking_url?: string;
  created_at: string;
}

export interface HotelHistoryPoint {
  recorded_at: string;
  total_price_pln: number;
  price_per_night_per_pax: number;
  departure_date: string;
  duration_nights: number;
  airport: string;
  normalized_price_1p_8n?: number;
  pure_hotel_night_rate?: number;
  scaled_tour_price?: number;
  adults?: number;
  children?: number;
}

export interface AvailablePackage {
  cohort_hash: string;
  airport: string;
  departure_date: string;
  duration_nights: number;
  total_price_pln: number;
  price_per_night_pax: number;
  operator?: string;
  booking_url?: string;
}

export interface GermanArbitrageData {
  berlin_price_pln: number;
  polish_price_pln: number;
  savings_pln: number;
  savings_pct: number;
  berlin_operator: string;
  departure_airport: string;
  booking_url?: string;
  train_transfer_from_pl: string;
}

export interface HotelOtherFilter {
  filter_id: string;
  title: string;
  min_price_pln: number;
  max_price_pln: number;
  snaps_count: number;
  adults?: number;
  children?: number;
  party_str?: string;
  duration_nights?: number;
  last_seen?: string;
}

export interface HotelPassport {
  hotel_id: string;
  display_name: string;
  country: string;
  region: string;
  stars: number;
  ta_rating?: number;
  ta_reviews: number;
  main_image_url?: string;
  all_time_min_pln: number;
  all_time_max_pln: number;
  typical_median_pln: number;
  current_price_pln: number;
  active_cohorts_count: number;
  deal_score: number;
  deal_badge: string;
  hopper_verdict: string;

  data_maturity_tier?: number;
  maturity_explanation?: string;
  user_query_scope?: {
    adults: number;
    children: number;
    duration_nights: number;
  };

  gallery_photos: string[];
  tripadvisor_url?: string;
  google_reviews_url?: string;
  youtube_search_url?: string;

  beach_line: number;
  beach_type: string;
  sea_entry: string;
  has_aquapark: boolean;
  has_heated_pools: boolean;
  food_concept: string;

  pros: string[];
  cons: string[];
  verdict: string;
  suitable_for: string;

  ai_action_signal: string;
  ai_price_summary: string;
  ai_hotel_summary: string;

  infra_rich?: Record<string, any>;
  german_arbitrage?: GermanArbitrageData;
  available_packages?: AvailablePackage[];
  other_filters?: HotelOtherFilter[];
  history_points: HotelHistoryPoint[];
}

export interface PriceDropItem {
  cohort_hash: string;
  hotel_id: string;
  hotel_name: string;
  country: string;
  region: string;
  stars: number;
  main_image_url?: string;
  duration_nights: number;
  departure_date: string;
  airport: string;
  previous_price_pln: number;
  current_price_pln: number;
  drop_amount_pln: number;
  drop_pct: number;
  booking_url?: string;
}

export interface AirportStat {
  airport_code: string;
  hotel_count: number;
  min_price_pln: number;
  avg_price_pln: number;
  avg_night_pax: number;
}

export interface MarketOverview {
  total_hotels: number;
  total_cohorts: number;
  total_snapshots: number;
  avg_current_price: number;
  min_current_price: number;
}

// -------------------------------------------------------------
// V2 REST API Dashboard Types (Mathematical & Visual Parity)
// -------------------------------------------------------------

export interface Top10HotelItem {
  name: string;
  price: number;
  position: number;
}

export interface TimelinePoint {
  time: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  top10_hotels?: Top10HotelItem[];
}

export interface TimelineStats {
  current_avg_top10: number;
  historical_min_avg: number;
  historical_max_avg: number;
  overall_trend: "UP" | "DOWN" | "FLAT" | string;
  last_updated: string;
  change_24h_pct?: number;
  change_7d_pct?: number;
}

export interface TimelineResponse {
  filter_id: string;
  points_count: number;
  timeline: TimelinePoint[];
  stats?: TimelineStats;
}

export interface HotelCatalogCard {
  hotel_id: string;
  display_name: string;
  country: string;
  region?: string;
  stars: number;
  ta_rating?: number;
  ta_reviews: number;
  main_image_url?: string;
  current_min_price: number;
  typical_median_price: number;
  historical_min_price: number;
  historical_max_price: number;
  delta_vs_typical_pct: number;
  change_24h_pct: number;
  change_48h_pct?: number;
  change_7d_pct: number;
  deal_score: number;
  deal_confidence: string;
  badges: string[];
  beach_line?: number;
  beach_type?: string;
  has_aquapark?: boolean;
  has_heated_pools?: boolean;
  cheapest_checkin_date?: string;
  cheapest_duration_nights: number;
  cheapest_airport_code: string;
  cheapest_offer_url?: string;
  last_updated: string;
}

export interface HotelCatalogResponse {
  filter_id: string;
  total_hotels: number;
  hotels: HotelCatalogCard[];
  last_updated_at?: string;
}

export interface MarketOraclePick {
  hotel_id: string;
  hotel_name: string;
  price: number;
  badge: string;
  reason: string;
  booking_url?: string;
}

export interface MarketOracleAnomaly {
  type: string;
  title: string;
  text: string;
}

export interface MarketOracleData {
  filter_id: string;
  title: string;
  headline: string;
  market_phase: string;
  charter_dynamics: string;
  floor_status: string;
  strategic_directive: string;
  synthesized_by?: string;
  buy_now_recommendation?: {
    status?: string;
    label?: string;
    explanation?: string;
    top_picks?: MarketOraclePick[];
  };
  key_anomalies?: (string | MarketOracleAnomaly)[];
}

export interface ActiveDepartureItem {
  departure_key: string;
  region: string;
  country: string;
  departure_date: string;
  return_date: string;
  nights: number;
  days_to_departure: number | null;
  days_label: string;
  hotel_count: number;
  min_price: number;
  median_price: number;
  p10_price: number;
  hot_score: number;
  status_label: string;
  status_cls: "hot" | "warm" | "calm";
  delta_text: string;
  avg_deal_score: number;
  hot_deal_count: number;
}

export interface HotDepartureHistoryItem {
  departure_key: string;
  departure: string;
  dates: string;
  daysBefore: string;
  drop: string;
  seenAt: string;
  score: number;
  p10: number;
  min: number;
  median: number;
  hotelsCount: number;
}

export interface FilterDeparturesData {
  filter_id: string;
  active_departures: ActiveDepartureItem[];
  hot_history: HotDepartureHistoryItem[];
  stats: {
    history_count: number;
    active_count: number;
    hot_count: number;
    best_p10: number;
  };
}



