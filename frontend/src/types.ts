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
  dates: SearchDates;
  duration: SearchDuration;
  travelers: SearchTravelers;
  airports: string[];
  price_max_pln?: number;
  force_live_refresh?: boolean;
}

export interface OfferSummary {
  cohort_hash: string;
  total_price_pln: number;
  price_per_night_pax: number;
  departure_date: string;
  duration_nights: number;
  airport: string;
  operator?: string;
  booking_url?: string;
}

export interface HotelIntelligence {
  deal_score: number;
  deal_badge: string;
  hopper_verdict: "BUY NOW" | "WAIT" | "OVERPRICED" | string;
  hopper_confidence: number;
  recommendation: string;
  drop_48h_pct: number;
  historic_min_pln: number;
  typical_median_pln: number;
  german_arbitrage_diff_pln?: number | null;
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
  train_transfer_from_pl: string;
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

