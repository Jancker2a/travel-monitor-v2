export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  telegram_chat_id?: string;
  telegram_notifications_enabled?: boolean;
  is_active: boolean;
  created_at?: string;

  // Daily Digest Preferences
  digest_enabled?: boolean;
  digest_time?: string;
  digest_days?: string;
  digest_include_watchlist?: boolean;
  digest_include_top_drops?: boolean;
  digest_include_hot_deals?: boolean;
  digest_include_historic_lows?: boolean;
  digest_min_deal_score?: number;
  digest_max_offers?: number;
  digest_only_if_changes?: boolean;

  // Quiet Hours
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: number;
  quiet_hours_end?: number;
}

export interface DashboardAlertSubscription {
  id: string;
  user_id: string;
  monitor_id: string;
  monitor_title: string;
  is_active: boolean;
  notify_mode: "INSTANT" | "DIGEST_ONLY";
  min_drop_pct: number;
  min_drop_pln?: number | null;
  min_deal_score: number;
  max_budget_pln?: number | null;
  only_historic_low: boolean;
  min_days_to_dep?: number;
  only_cheaper_than_std?: boolean;
  whitelist_only?: boolean;
  min_ta_rating?: number | null;
  preferred_airports?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface SeasonalityMonthItem {
  month: string;
  label: string;
  min_price: number;
  p10_price: number;
  median_price: number;
  hotels_count: number;
  cohorts_count: number;
  hot_share_pct?: number | null;
  season_tier: string;
  season_label: string;
  is_cheaper_month: boolean;
}

export interface SeasonalityOutlookData {
  has_data: boolean;
  destination: string;
  party_label: string;
  anchors: {
    seasonal_median_pln?: number;
    good_deal_target_pln?: number;
    snipe_record_pln?: number;
  };
  hunt_odds: {
    dump_probability_pct?: number;
    sold_out_scarcity_pct?: number;
    strategy_verdict?: string;
    headline?: string;
    advice?: string;
    cheapest_month?: string | null;
    cheapest_month_label?: string | null;
  };
  months: SeasonalityMonthItem[];
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
  board_basis?: string | null;
  booking_url?: string;
}

export type FilterType = "lastminute" | "early_booking" | "fixed_dates" | "rolling";

export interface HotelIntelligence {
  deal_score: number;
  deal_badge: string;
  hopper_verdict: "BUY NOW" | "WAIT" | "OVERPRICED" | string;
  hopper_confidence: number;
  recommendation: string;
  action_label?: string;
  drop_48h_pct?: number | null;
  change_30d_pct?: number | null;
  delta_vs_typical_pct?: number | null;
  historic_min_pln?: number | null;
  typical_median_pln?: number | null;
  german_arbitrage_diff_pln?: number | null;
  is_budget_tier?: boolean;
  upcoming_std_price?: number | null;
  upcoming_std_date?: string | null;
  upcoming_std_airport?: string | null;
  spread_vs_std_pln?: number | null;
  spread_vs_std_pct?: number | null;
  filter_type?: FilterType;
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
  alert_threshold_pct?: number;
  min_deal_score?: number;
  min_days_to_dep?: number;
  typical_median_pln?: number | null;
  historical_min_pln?: number | null;
  is_active?: boolean;
  notify_any_drop?: boolean;
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

export interface HorizonStat {
  count: number;
  min_price_pln: number;
  median_price_pln: number;
  avg_price_pln: number;
  display_price_pln?: number;
  current_price_pln?: number;
  departure_dates_label?: string;
  season_label?: string;
  is_same_season?: boolean;
  best_offer?: {
    price_pln: number;
    days_to_dep: number;
    checkin_date: string;
    duration_nights: number;
    airport: string;
  };
}

export interface HorizonArbitrageData {
  available: boolean;
  hotel_id?: string;
  target_nights?: number;
  target_adults?: number;
  target_children?: number;
  current_price_pln?: number;
  horizons?: {
    early_booking?: HorizonStat | null;
    standard?: HorizonStat | null;
    short_notice?: HorizonStat | null;
    last_minute?: HorizonStat | null;
  };
  all_time_min_pln?: number;
  direct_comparison?: {
    has_comparison: boolean;
    is_hot_cheaper: boolean;
    is_std_cheaper: boolean;
    is_same_flight_date?: boolean;
    price_diff_pln: number;
    diff_pct: number;
    days_gap?: number | null;
    hot_offer: {
      price_pln: number;
      checkin_date?: string | null;
      checkin_date_formatted?: string | null;
      airport?: string | null;
      offer_url?: string | null;
    };
    standard_offer: {
      price_pln: number;
      checkin_date?: string | null;
      checkin_date_formatted?: string | null;
      airport?: string | null;
      offer_url?: string | null;
    };
    early_booking_offer?: {
      price_pln: number;
      departure_dates_label?: string | null;
      season_label?: string | null;
      is_same_season?: boolean;
    } | null;
    summary: string;
  } | null;
  departure_price_story?: {
    has_story: boolean;
    target_checkin_date: string;
    date_window_label: string;
    trajectory: "DEEP_DROP" | "STABLE" | "SURCHARGE_RISE";
    trajectory_badge: string;
    stages: {
      early_booking?: {
        price_pln: number;
        checkin_date: string;
        days_before: number;
        is_exact_date_match: boolean;
      } | null;
      month_before?: {
        price_pln: number;
        checkin_date: string;
        days_before: number;
        is_exact_date_match: boolean;
      } | null;
      two_weeks_before?: {
        price_pln: number;
        checkin_date: string;
        days_before: number;
        is_exact_date_match: boolean;
      } | null;
      last_minute: {
        price_pln: number;
        checkin_date: string;
        days_before: number;
        is_exact_date_match: boolean;
      };
    };
    verdict_text: string;
    conclusion?: string;
    timeline_steps?: Array<{
      key: string;
      title: string;
      days_label: string;
      checkin_date: string;
      price_pln: number;
      delta_prev_pln?: number | null;
      delta_prev_pct?: number | null;
      is_current: boolean;
    }>;
  } | null;
  historical_best_dump?: {
    has_dump: boolean;
    price_pln: number;
    checkin_date: string;
    checkin_date_formatted: string;
    recorded_at: string;
    recorded_at_formatted: string;
    days_before: number;
    airport?: string;
    benchmark_norm_pln: number;
    savings_pln: number;
    discount_pct: number;
    is_record_now: boolean;
    narrative: string;
  } | null;
  verdict?: {
    perspective: "LAST_MINUTE" | "REGULAR_OR_EARLY";
    type: string;
    badge: string;
    headline: string;
    description: string;
    recommendation: string;
    savings_vs_standard_pln?: number | null;
    savings_vs_standard_pct?: number | null;
    savings_vs_eb_pln?: number | null;
    savings_vs_eb_pct?: number | null;
    is_cross_season_comparison?: boolean;
    season_note?: string;
  };
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
  is_exact_match?: boolean;
  history_points?: HotelHistoryPoint[];
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
  all_time_min_pln?: number | null;
  all_time_max_pln?: number | null;
  typical_median_pln?: number | null;
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
  seasonal_norm_pln?: number;
  ai_insight?: {
    headline: string;
    season_label: string;
    season_context: string;
    diff_to_norm_pct: number;
    seasonal_norm_pln: number;
    current_price_pln: number;
    summary: string;
  };

  infra_rich?: Record<string, any>;
  german_arbitrage?: GermanArbitrageData;
  horizon_arbitrage?: HorizonArbitrageData;
  reference_history?: {
    filter_id: string;
    title: string;
    adults: number;
    children: number;
    duration_nights: number;
    is_exact_match: boolean;
    snaps_count: number;
    min_price_pln: number;
    median_price_pln: number;
    max_price_pln: number;
    history_points: HotelHistoryPoint[];
  } | null;
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
  ta_rating?: number | null;
  ta_reviews: number;
  main_image_url?: string;
  current_min_price: number;
  typical_median_price?: number | null;
  historical_min_price?: number | null;
  historical_max_price?: number | null;
  delta_vs_typical_pct?: number | null;
  change_24h_pct: number;
  change_48h_pct?: number;
  change_7d_pct: number;
  change_30d_pct?: number | null;
  deal_score: number;
  deal_confidence: string;
  hopper_verdict?: string;
  action_label?: string | null;
  recommendation?: string | null;
  upcoming_std_price?: number | null;
  upcoming_std_date?: string | null;
  upcoming_std_airport?: string | null;
  spread_vs_std_pln?: number | null;
  spread_vs_std_pct?: number | null;
  badges: string[];
  beach_line?: number;
  beach_type?: string;
  has_aquapark?: boolean;
  has_heated_pools?: boolean;
  cheapest_checkin_date?: string;
  cheapest_duration_nights: number;
  cheapest_airport_code: string;
  cheapest_offer_url?: string;
  board_basis?: string | null;
  cohort_hash?: string;
  last_updated: string;
}

export interface HotelCatalogResponse {
  filter_id: string;
  filter_type?: FilterType;
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
  filter_type?: FilterType;
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
  date?: string;
  days_to_dep?: number;
  hotels_count?: number;
  min_price: number;
  median_price: number;
  airports?: string[];
  is_hot_window?: boolean;
  // Backward compat fields
  departure_key?: string;
  region?: string;
  country?: string;
  departure_date?: string;
  return_date?: string;
  nights?: number;
  days_to_departure?: number | null;
  days_label?: string;
  hotel_count?: number;
  p10_price?: number;
  hot_score?: number;
  status_label?: string;
  status_cls?: "hot" | "warm" | "calm";
  delta_text?: string;
  avg_deal_score?: number;
  hot_deal_count?: number;
}

export interface HotDepartureHistoryItem {
  hotel_name?: string;
  checkin_date?: string;
  min_price_pln?: number;
  avg_price_pln?: number;
  drop_pct?: number;
  // Backward compat fields
  departure_key?: string;
  departure?: string;
  dates?: string;
  daysBefore?: string;
  drop?: string;
  seenAt?: string;
  score?: number;
  p10?: number;
  min?: number;
  median?: number;
  hotelsCount?: number;
}

export interface FilterDeparturesData {
  filter_id: string;
  active_departures: ActiveDepartureItem[];
  hot_history: HotDepartureHistoryItem[];
  stats: {
    upcoming_dates_count?: number;
    hot_window_dates_count?: number;
    nearest_date?: string | null;
    history_count?: number;
    active_count?: number;
    hot_count?: number;
    best_p10?: number;
  };
}

export interface FilterPriceMoveItem {
  hotel_id: string;
  hotel_name: string;
  prev_price: number;
  curr_price: number;
  delta_pln: number;
  delta_pct: number;
  airport_code?: string;
  checkin_date?: string | null;
  recorded_at: string;
}

export interface FilterAnalyticsData {
  filter_id: string;
  filter_type: FilterType;
  overview: {
    total_hotels: number;
    total_cohorts: number;
    total_snapshots: number;
    avg_price: number;
    median_price: number;
    min_price: number;
    sold_out_7d_lost_count: number;
    last_updated_at?: string | null;
  };
  calendar_dates: {
    date: string;
    days_to_dep: number;
    hotels_count: number;
    min_price: number;
    median_price: number;
  }[];
  price_changes: {
    drops: FilterPriceMoveItem[];
    hikes: FilterPriceMoveItem[];
    history: FilterPriceMoveItem[];
  };
  timing_stats: {
    best_window: string;
    best_window_share_pct: number;
    avg_drop_pct?: number;
    total_drops_analyzed: number;
    by_hour: { window: string; drops: number }[];
    by_weekday: { day: string; drops: number }[];
  };
}

export interface ArbitrageStatus {
  kb_updated_at: string | null;
  total_offers: number;
  age_hours: number | null;
  is_stale: boolean;
}



