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
import { LoadingSpinner } from "./components/common/LoadingSpinner";
import {
  SearchRequest,
  SearchHotelItem,
  WatchlistItem,
  PriceDropItem,
  AirportStat,
  HotelCatalogCard,
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
    displayPriceCeiling?: number;
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
  turkey_7_10: {
    title: "🇹🇷 Турция — 7–10 ночей (2 взр + 1 реб)",
    countryBadge: "🇹🇷 ТУРЦИЯ",
    destination: "turkey",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom&startDateMin=31-05-2026&startDateMax=23-06-2026&returnDate=30-06-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "Июнь 2027",
      party: "2 взр + 1 реб (до 12 лет)",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "turkey_7_10",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-30" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  turkey_9_11: {
    title: "🇹🇷 Турция — 9–11 ночей (Все Включено)",
    countryBadge: "🇹🇷 ТУРЦИЯ",
    destination: "turkey",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=01-01-2026&startDateMax=22-01-2026&returnDate=31-01-2026&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=9&durationTo=11&priceFrom=4610&priceTo=20000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "Июнь 2027",
      party: "2 взр + 1 реб (6 лет)",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "turkey_9_11",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-30" },
      duration: { min_nights: 9, max_nights: 11 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  turkey_13_16: {
    title: "🇹🇷 Турция — 13–16 ночей (Длительный)",
    countryBadge: "🇹🇷 ТУРЦИЯ ДЛИТЕЛЬНЫЙ",
    destination: "turkey",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom&startDateMin=31-05-2026&startDateMax=17-06-2026&returnDate=30-06-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "Июнь 2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "turkey_13_16",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-30" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  egypt_7_10: {
    title: "🇪🇬 Египет — 7–10 ночей (2 взр + 1 реб)",
    countryBadge: "🇪🇬 ЕГИПЕТ 7–10 ДНЕЙ",
    destination: "egypt",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Modlin,Warszawa+-+Radom,Warszawa&startDateMin=28-05-2026&startDateMax=23-06-2026&returnDate=30-06-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "Красное море",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_7_10",
      dates: { start_date_min: "2026-11-10", start_date_max: "2026-12-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  egypt_13_16: {
    title: "🇪🇬 Египет — 13–16 ночей (2 взр + 1 реб)",
    countryBadge: "🇪🇬 ЕГИПЕТ ДЛИТЕЛЬНЫЙ",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Modlin,Warszawa+-+Radom,Warszawa&startDateMin=28-05-2026&startDateMax=17-06-2026&returnDate=30-06-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "Длительный отдых",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 15 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_13_16",
      dates: { start_date_min: "2026-11-10", start_date_max: "2026-12-31" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  egypt_autumn_7_10: {
    title: "🇪🇬 Египет — Осень 7–10 ночей (2 взр + 1 реб)",
    countryBadge: "🇪🇬 ЕГИПЕТ",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Radom,Warszawa,Warszawa+-+Modlin&startDateMin=10-10-2026&startDateMax=29-10-2026&returnDate=05-11-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=0&priceTo=11000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "Осень 2026",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_autumn_7_10",
      dates: { start_date_min: "2026-10-10", start_date_max: "2026-11-15" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  egypt_autumn_13_16: {
    title: "🇪🇬 Египет — Осень 13–16 ночей (2 взр + 1 реб)",
    countryBadge: "🇪🇬 ЕГИПЕТ ДЛИТЕЛЬНЫЙ",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Radom,Warszawa,Warszawa+-+Modlin&startDateMin=10-10-2026&startDateMax=23-10-2026&returnDate=05-11-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=0&priceTo=11000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "Осень 2026",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 15 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_autumn_13_16",
      dates: { start_date_min: "2026-10-10", start_date_max: "2026-11-20" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  egypt_sharm_dec20_29_1p: {
    title: "🇪🇬 Египет — Шарм-эль-Шейх 20–29 дек (1 взрослый)",
    countryBadge: "🇪🇬 ШАРМ-ЭЛЬ-ШЕЙХ",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11_154&departureLocation=Bydgoszcz,Gdańsk,Katowice,Kraków,Lublin,Łódź,Poznań,Rzeszów,Szczecin,Warszawa,Wrocław,ZielonaGóra&startDateMin=20-12-2026&startDateMax=22-12-2026&returnDate=29-12-2026&adults=1&offerTypes=accommodation_flight&durationFrom=7&durationTo=15&priceFrom=0&priceTo=30000&order=price",
    chips: {
      airports: "Любой аэропорт Польши",
      dates: "20.12–29.12.2026",
      party: "1 взрослый",
      hotelClass: "Все Включено • Бухты без ветра",
      budget: "до 7 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_sharm_dec20_29_1p",
      dates: { start_date_min: "2026-12-20", start_date_max: "2026-12-29" },
      duration: { min_nights: 7, max_nights: 15 },
      travelers: { adults: 1, children: 0, children_ages: [] },
      airports: ["WAW", "KTW", "WRO", "POZ", "GDN"],
    },
  },
  egypt_ny_dec24_2026_7_10: {
    title: "🎄 Египет — Новый Год 24.12–06.01 (7–10 дн)",
    countryBadge: "🎄 НОВЫЙ ГОД",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Radom,Warszawa,Warszawa+-+Modlin&startDateMin=24-12-2026&startDateMax=30-12-2026&returnDate=06-01-2027&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=0&priceTo=11000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "24.12.2026–06.01.2027",
      party: "2 взр + 1 реб",
      hotelClass: "Новогодний банкет включен",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_ny_dec24_2026_7_10",
      dates: { start_date_min: "2026-12-24", start_date_max: "2027-01-06" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  egypt_ny_dec28_2026_7_10: {
    title: "🎄 Египет — Новый Год 28.12–06.01 (7–10 дн)",
    countryBadge: "🎄 НОВЫЙ ГОД",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Radom,Warszawa,Warszawa+-+Modlin&startDateMin=28-12-2026&startDateMax=30-12-2026&returnDate=06-01-2027&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=0&priceTo=11000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "28.12.2026–06.01.2027",
      party: "2 взр + 1 реб",
      hotelClass: "Новогодний банкет",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_ny_dec28_2026_7_10",
      dates: { start_date_min: "2026-12-28", start_date_max: "2027-01-06" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  greece_7_10: {
    title: "🇬🇷 Греция — 7–10 ночей (5★ All Inclusive)",
    countryBadge: "🇬🇷 ГРЕЦИЯ",
    destination: "greece",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&startDateMin=10-11-2026&startDateMax=03-12-2026&returnDate=10-12-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "Все аэропорты Польши",
      dates: "Ноябрь – Декабрь 2026",
      party: "2 взр + 1 реб",
      hotelClass: "5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "greece",
      filter_id: "greece_7_10_days",
      dates: { start_date_min: "2026-11-10", start_date_max: "2026-12-10" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW", "WRO"],
    },
  },
  greece_13_16: {
    title: "🇬🇷 Греция — 13–16 ночей (5★ All Inclusive)",
    countryBadge: "🇬🇷 ГРЕЦИЯ ДЛИТЕЛЬНЫЙ",
    destination: "greece",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&startDateMin=10-11-2026&startDateMax=24-11-2026&returnDate=10-12-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "Все аэропорты Польши",
      dates: "Ноябрь – Декабрь 2026",
      party: "2 взр + 1 реб",
      hotelClass: "5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "greece",
      filter_id: "greece_13_16_days",
      dates: { start_date_min: "2026-11-10", start_date_max: "2026-12-10" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW", "WRO"],
    },
  },
  filter_cyprus_7_10: {
    title: "🇨🇾 Кипр — 7–10 ночей (1 взрослый)",
    countryBadge: "🇨🇾 КИПР",
    destination: "cyprus",
    displayPriceCeiling: 6000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=10:&departureLocation=Bydgoszcz,Gdańsk,Katowice,Kraków,Lublin,Łódź,Poznań,Rzeszów,Szczecin,Warszawa,Wrocław,ZielonaGóra&adults=1&offerTypes=accommodation_flight&durationFrom=7&durationTo=10&priceFrom=0&priceTo=30000&order=price",
    chips: {
      airports: "9 аэропортов Польши",
      dates: "Сезон 2026/2027",
      party: "1 взрослый",
      hotelClass: "3★ – 5★",
      budget: "до 6 000 zł",
    },
    searchReq: {
      destination: "cyprus",
      filter_id: "filter_cyprus_7_10",
      dates: { start_date_min: "2026-11-01", start_date_max: "2027-05-30" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 1, children: 0, children_ages: [] },
      airports: ["WAW", "KTW", "WRO", "POZ", "GDN"],
    },
  },
  benchmark_turkey_1p_7_8: {
    title: "📏 Турция • Эталон (1 взр • 7–8 дн)",
    countryBadge: "🇹🇷 ЭТАЛОН 1 ВЗР",
    destination: "turkey",
    displayPriceCeiling: 15000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Katowice,Kraków,Gdańsk,Wrocław,Poznań&adults=1&catering=all_inclusive&offerTypes=accommodation_flight&durationFrom=7&durationTo=8&priceFrom=500&priceTo=15000&order=price",
    chips: {
      airports: "WAW, KTW, KRK, GDN, WRO, POZ",
      dates: "Сегодня + 3 недели (скользящее)",
      party: "1 взрослый",
      hotelClass: "Все категории (3★ – 5★)",
      budget: "до 15 000 zł / чел",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "benchmark_turkey_1p_7_8",
      dates: { start_date_min: "2026-12-01", start_date_max: "2026-12-08" },
      duration: { min_nights: 7, max_nights: 8 },
      travelers: { adults: 1, children: 0, children_ages: [] },
      airports: ["WAW", "KTW", "KRK", "GDN", "WRO", "POZ"],
    },
  },
  benchmark_egypt_1p_7_8: {
    title: "📏 Египет • Эталон (1 взр • 7–8 дн)",
    countryBadge: "🇪🇬 ЭТАЛОН 1 ВЗР",
    destination: "egypt",
    displayPriceCeiling: 15000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa,Katowice,Kraków,Gdańsk,Wrocław,Poznań&adults=1&catering=all_inclusive&offerTypes=accommodation_flight&durationFrom=7&durationTo=8&priceFrom=500&priceTo=15000&order=price",
    chips: {
      airports: "WAW, KTW, KRK, GDN, WRO, POZ",
      dates: "Сегодня + 3 недели (скользящее)",
      party: "1 взрослый",
      hotelClass: "Все категории (3★ – 5★)",
      budget: "до 15 000 zł / чел",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "benchmark_egypt_1p_7_8",
      dates: { start_date_min: "2026-12-01", start_date_max: "2026-12-08" },
      duration: { min_nights: 7, max_nights: 8 },
      travelers: { adults: 1, children: 0, children_ages: [] },
      airports: ["WAW", "KTW", "KRK", "GDN", "WRO", "POZ"],
    },
  },
  benchmark_greece_1p_7_8: {
    title: "📏 Греция • Эталон (1 взр • 7–8 дн)",
    countryBadge: "🇬🇷 ЭТАЛОН 1 ВЗР",
    destination: "greece",
    displayPriceCeiling: 15000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&departureLocation=Warszawa,Katowice,Kraków,Gdańsk,Wrocław,Poznań&adults=1&catering=all_inclusive&offerTypes=accommodation_flight&durationFrom=7&durationTo=8&priceFrom=500&priceTo=15000&order=price",
    chips: {
      airports: "WAW, KTW, KRK, GDN, WRO, POZ",
      dates: "Сегодня + 3 недели (скользящее)",
      party: "1 взрослый",
      hotelClass: "Все категории (3★ – 5★)",
      budget: "до 15 000 zł / чел",
    },
    searchReq: {
      destination: "greece",
      filter_id: "benchmark_greece_1p_7_8",
      dates: { start_date_min: "2026-12-01", start_date_max: "2026-12-08" },
      duration: { min_nights: 7, max_nights: 8 },
      travelers: { adults: 1, children: 0, children_ages: [] },
      airports: ["WAW", "KTW", "KRK", "GDN", "WRO", "POZ"],
    },
  },
  benchmark_cyprus_1p_7_8: {
    title: "📏 Кипр • Эталон (1 взр • 7–8 дн)",
    countryBadge: "🇨🇾 ЭТАЛОН 1 ВЗР",
    destination: "cyprus",
    displayPriceCeiling: 15000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=6:&departureLocation=Warszawa,Katowice,Kraków,Gdańsk,Wrocław,Poznań&adults=1&catering=all_inclusive&offerTypes=accommodation_flight&durationFrom=7&durationTo=8&priceFrom=500&priceTo=15000&order=price",
    chips: {
      airports: "WAW, KTW, KRK, GDN, WRO, POZ",
      dates: "Сегодня + 3 недели (скользящее)",
      party: "1 взрослый",
      hotelClass: "Все категории (3★ – 5★)",
      budget: "до 15 000 zł / чел",
    },
    searchReq: {
      destination: "cyprus",
      filter_id: "benchmark_cyprus_1p_7_8",
      dates: { start_date_min: "2026-12-01", start_date_max: "2026-12-08" },
      duration: { min_nights: 7, max_nights: 8 },
      travelers: { adults: 1, children: 0, children_ages: [] },
      airports: ["WAW", "KTW", "KRK", "GDN", "WRO", "POZ"],
    },
  },
  eb_turkey_jul27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Турция Июль (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "turkey",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom&startDateMin=01-07-2027&startDateMax=31-07-2027&returnDate=14-08-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "01.07–31.07.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 12 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "eb_turkey_jul27_7_10",
      dates: { start_date_min: "2027-07-01", start_date_max: "2027-07-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  eb_turkey_jul27_13_16: {
    title: "🏷️ Раннее бронирование 2027 — Турция Июль (13–16 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "turkey",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom&startDateMin=01-07-2027&startDateMax=31-07-2027&returnDate=20-08-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=6000&priceTo=35000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "01.07–31.07.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 16 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "eb_turkey_jul27_13_16",
      dates: { start_date_min: "2027-07-01", start_date_max: "2027-07-31" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  eb_turkey_aug27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Турция Август (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "turkey",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom&startDateMin=01-08-2027&startDateMax=31-08-2027&returnDate=14-09-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "01.08–31.08.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 12 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "eb_turkey_aug27_7_10",
      dates: { start_date_min: "2027-08-01", start_date_max: "2027-08-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  eb_egypt_jul27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Египет Июль (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=01-07-2027&startDateMax=31-07-2027&returnDate=14-08-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "01.07–31.07.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "eb_egypt_jul27_7_10",
      dates: { start_date_min: "2027-07-01", start_date_max: "2027-07-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  eb_egypt_aug27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Египет Август (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=01-08-2027&startDateMax=31-08-2027&returnDate=14-09-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "01.08–31.08.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "eb_egypt_aug27_7_10",
      dates: { start_date_min: "2027-08-01", start_date_max: "2027-08-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  eb_egypt_oct27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Египет Октябрь (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=01-10-2027&startDateMax=31-10-2027&returnDate=14-11-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "01.10–31.10.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "eb_egypt_oct27_7_10",
      dates: { start_date_min: "2027-10-01", start_date_max: "2027-10-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  eb_greece_jul27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Греция Июль (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "greece",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=01-07-2027&startDateMax=31-07-2027&returnDate=14-08-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "01.07–31.07.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "greece",
      filter_id: "eb_greece_jul27_7_10",
      dates: { start_date_min: "2027-07-01", start_date_max: "2027-07-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  eb_greece_aug27_7_10: {
    title: "🏷️ Раннее бронирование 2027 — Греция Август (7–10 дн)",
    countryBadge: "🏷️ EARLY BIRD 2027",
    destination: "greece",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=01-08-2027&startDateMax=31-08-2027&returnDate=14-09-2027&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=25000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "01.08–31.08.2027",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 11 000 zł",
    },
    searchReq: {
      destination: "greece",
      filter_id: "eb_greece_aug27_7_10",
      dates: { start_date_min: "2027-08-01", start_date_max: "2027-08-31" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  turkey_vacation_jul18_2026: {
    title: "📦 Турция — Отпуск 18 июля (Архив)",
    countryBadge: "📦 АРХИВ ТУРОВ",
    destination: "turkey",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom,Warszawa+-+Modlin&startDateMin=18-07-2026&startDateMax=06-08-2026&returnDate=13-08-2026&adults=2&children=12-08-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=11&priceFrom=4610&priceTo=20000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "18.07–29.07.2026",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "Архив",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "turkey_vacation_jul18_2026",
      dates: { start_date_min: "2026-07-18", start_date_max: "2026-07-29" },
      duration: { min_nights: 7, max_nights: 11 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  egypt_autumn_2026_7_10_days: {
    title: "📦 Египет — Осень 7–10 ночей (Архив)",
    countryBadge: "📦 АРХИВ ТУРОВ",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Radom,Warszawa,Warszawa+-+Modlin&startDateMin=10-10-2026&startDateMax=29-10-2026&returnDate=05-11-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=0&priceTo=11000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "10.10–19.10.2026",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "Архив",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_autumn_2026_7_10_days",
      dates: { start_date_min: "2026-10-10", start_date_max: "2026-10-19" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  egypt_autumn_2026_13_16_days: {
    title: "📦 Египет — Осень 13–16 ночей (Архив)",
    countryBadge: "📦 АРХИВ ТУРОВ",
    destination: "egypt",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=11:&departureLocation=Warszawa+-+Radom,Warszawa,Warszawa+-+Modlin&startDateMin=10-10-2026&startDateMax=23-10-2026&returnDate=05-11-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=0&priceTo=11000&order=price",
    chips: {
      airports: "WAW, WMI, RDO",
      dates: "10.10–18.10.2026",
      party: "2 взр + 1 реб",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "Архив",
    },
    searchReq: {
      destination: "egypt",
      filter_id: "egypt_autumn_2026_13_16_days",
      dates: { start_date_min: "2026-10-10", start_date_max: "2026-10-18" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "WMI", "RDO"],
    },
  },
  turkey_7_10_days: {
    title: "🇹🇷 Турция — 7–10 ночей (2 взр + 1 реб)",
    countryBadge: "🇹🇷 ТУРЦИЯ",
    destination: "turkey",
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=39:&departureLocation=Warszawa,Warszawa+-+Radom&startDateMin=31-05-2026&startDateMax=23-06-2026&returnDate=30-06-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "WAW, RDO",
      dates: "Июнь 2027",
      party: "2 взр + 1 реб (до 12 лет)",
      hotelClass: "4★ – 5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "turkey",
      filter_id: "turkey_7_10",
      dates: { start_date_min: "2027-05-25", start_date_max: "2027-06-30" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "RDO"],
    },
  },
  greece_7_10_days: {
    title: "🇬🇷 Греция — 7–10 ночей (5★ All Inclusive)",
    countryBadge: "🇬🇷 ГРЕЦИЯ",
    destination: "greece",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&startDateMin=10-11-2026&startDateMax=03-12-2026&returnDate=10-12-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=7&durationTo=10&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "Все аэропорты Польши",
      dates: "Ноябрь – Декабрь 2026",
      party: "2 взр + 1 реб",
      hotelClass: "5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "greece",
      filter_id: "greece_7_10_days",
      dates: { start_date_min: "2026-11-10", start_date_max: "2026-12-10" },
      duration: { min_nights: 7, max_nights: 10 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW", "WRO"],
    },
  },
  greece_13_16_days: {
    title: "🇬🇷 Греция — 13–16 ночей (5★ All Inclusive)",
    countryBadge: "🇬🇷 ГРЕЦИЯ ДЛИТЕЛЬНЫЙ",
    destination: "greece",
    displayPriceCeiling: 10000,
    targetUrl: "https://fly.pl/szukaj-wycieczek/?destinationLocation=14:&startDateMin=10-11-2026&startDateMax=24-11-2026&returnDate=10-12-2026&adults=2&children=10-12-2020&catering=all_inclusive&offerTypes=accommodation_flight&categoryRating=50&durationFrom=13&durationTo=16&priceFrom=4000&priceTo=20000&order=price",
    chips: {
      airports: "Все аэропорты Польши",
      dates: "Ноябрь – Декабрь 2026",
      party: "2 взр + 1 реб",
      hotelClass: "5★ All Inclusive",
      budget: "до 10 000 zł",
    },
    searchReq: {
      destination: "greece",
      filter_id: "greece_13_16_days",
      dates: { start_date_min: "2026-11-10", start_date_max: "2026-12-10" },
      duration: { min_nights: 13, max_nights: 16 },
      travelers: { adults: 2, children: 1, children_ages: [6] },
      airports: ["WAW", "KTW", "WRO"],
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

function catalogCardToSearchItem(c: HotelCatalogCard): SearchHotelItem {
  const duration = c.cheapest_duration_nights || 7;
  const nights = duration > 0 ? duration : 7;
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
      price_per_night_pax: Math.round(c.current_min_price / nights / 2),
      departure_date: c.cheapest_checkin_date || "",
      duration_nights: nights,
      airport: c.cheapest_airport_code || "WAW",
      booking_url: c.cheapest_offer_url,
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
  const [activeTab, setActiveTab] = useState<"filter" | "search" | "arbitrage">("filter");
  const [activeFilterId, setActiveFilterId] = useState<string>("turkey_7_10");
  const [viewMode, setViewMode] = useState<"cards" | "table" | "arbitrage">("table");

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

  // Navigation tab switcher synced with URL hash (#/search, #/radar/:id, #/arbitrage)
  const navigateToTab = (tab: "filter" | "search" | "arbitrage", filterId?: string) => {
    setActiveTab(tab);
    if (tab === "search") {
      window.location.hash = "#/search";
      if (viewMode === "arbitrage") {
        setViewMode("table");
      }
    } else if (tab === "arbitrage") {
      window.location.hash = "#/arbitrage";
      setViewMode("arbitrage");
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
        setActiveTab("search");
        if (viewMode === "arbitrage") {
          setViewMode("table");
        }
      } else if (hash.includes("arbitrage")) {
        setActiveTab("filter");
        setViewMode("arbitrage");
      } else if (hash.startsWith("#/radar/") || hash.startsWith("#/filter/")) {
        const rawId = hash.replace("#/radar/", "").replace("#/filter/", "").split("?")[0];
        if (rawId && FILTER_PRESETS[rawId]) {
          setActiveFilterId(rawId);
          loadFilterResults(rawId);
        }
        setActiveTab("filter");
      }
    };

    syncFromHash();
    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, []);

  useEffect(() => {
    // 1. Critical path: Load active filter catalog immediately
    loadFilterResults("turkey_7_10");

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

  useEffect(() => {
    if (activeTab !== "filter") {
      setArbitrageCount(0);
      return;
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

    getArbitrageDeals(300, activeFilterId, country)
      .then((deals) => setArbitrageCount(deals.length))
      .catch((err) => {
        console.warn("Arbitrage count fetch failed:", err);
        setArbitrageCount(0);
      });
  }, [activeTab, activeFilterId]);

  const loadFilterResults = async (filterId: string) => {
    setIsLoading(true);
    try {
      const preset = FILTER_PRESETS[filterId] || FILTER_PRESETS["turkey_7_10_days"];
      const catResp = await getFilterHotelsCatalog(filterId, {
        maxPrice: preset?.displayPriceCeiling,
      });
      if (catResp.hotels && catResp.hotels.length > 0) {
        setResults(catResp.hotels.map(catalogCardToSearchItem));
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
    setActiveFilterId(filterId);
    setActiveTab("filter");
    setTableFilters(INITIAL_FILTERS);
    loadFilterResults(filterId);
    window.location.hash = `#/radar/${filterId}`;
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
        activeTab={activeTab}
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
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-1 bg-slate-800/90 p-1 rounded-2xl border border-slate-700">
              <button
                type="button"
                onClick={() => {
                  navigateToTab("filter");
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
                onClick={() => navigateToTab("search")}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                  activeTab === "search"
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-300 hover:text-white hover:bg-slate-700/50"
                }`}
              >
                <span>🔍 Интерактивный поиск</span>
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
      <main className="max-w-[1880px] mx-auto px-4 sm:px-6 lg:px-8 py-5 flex-1 w-full space-y-6">
        {/* If in Search Tab */}
        {activeTab === "search" && (
          <div className="mb-4">
            <SearchHeader
              onSearch={handleSearch}
              isLoading={isLoading}
              initialPreset={FILTER_PRESETS[activeFilterId]}
            />
          </div>
        )}

        {/* Filter dashboard headers & folds: ONLY in filter monitoring mode */}
        {activeTab === "filter" && (
          <>
            {/* 1. Hero Terminal Banner with Metadata Chips & 4 White KPI Cards */}
            <HeroTerminal
              title={currentPreset.title}
              countryBadge={currentPreset.countryBadge}
              targetUrl={currentPreset.targetUrl}
              chips={currentPreset.chips}
              kpi={heroKpi}
              activeQuickFilter={activeQuickFilter}
              onQuickFilter={handleQuickFilter}
            />

            {/* 2. Top Fold: 🧠 AI-анализ рынка и прогноз цен */}
            <AiMarketBriefing
              filterId={activeFilterId}
              filterTitle={currentPreset.title}
              buyNowCount={heroKpi.buyNowCount}
              onOpenPassport={(hotelId) => setActiveHotelPassport(hotelId)}
            />

            {/* 3. Time Series Chart: 📉 Средняя цена ТОП-10 дешёвых предложений */}
            <Top10TimelineChart
              filterId={activeFilterId}
              destination={currentPreset.destination}
            />

            {/* 4. Second Fold: 📊 Расширенная аналитика и тренды рынка */}
            <AnalyticsFold
              hotels={results}
              topDrops={topDrops}
              airportStats={airportStats}
              filterId={activeFilterId}
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
            filterId={activeTab === "filter" ? activeFilterId : undefined}
            country={
              FILTER_PRESETS[activeFilterId]?.destination === "turkey"
                ? "Турция"
                : FILTER_PRESETS[activeFilterId]?.destination === "egypt"
                ? "Египет"
                : FILTER_PRESETS[activeFilterId]?.destination === "greece"
                ? "Греция"
                : FILTER_PRESETS[activeFilterId]?.destination === "cyprus"
                ? "Кипр"
                : undefined
            }
            filterTitle={FILTER_PRESETS[activeFilterId]?.title}
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
      </main>

      {/* 7. Hotel AI Passport Drawer (Slides out from RIGHT) */}
      <HotelPassportDrawer
        hotelId={activeHotelPassport}
        filterId={activeTab === "filter" ? activeFilterId : undefined}
        hotelItem={
          results.find(
            (h) =>
              h.hotel_id === activeHotelPassport ||
              (activeHotelPassport &&
                h.hotel_name.trim().toLowerCase() === activeHotelPassport.trim().toLowerCase())
          ) || null
        }
        onSwitchFilter={(newFilterId) => handleSelectFilter(newFilterId)}
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
