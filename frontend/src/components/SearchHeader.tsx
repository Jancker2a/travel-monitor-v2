import React, { useState, useMemo } from "react";
import {
  Search,
  Calendar,
  Users,
  Plane,
  RefreshCw,
  Sparkles,
  ExternalLink,
  ChevronDown,
  RotateCcw,
  Utensils,
  Star,
  SlidersHorizontal,
  Compass,
} from "lucide-react";
import { SearchRequest } from "../types";

interface Props {
  onSearch: (req: SearchRequest) => void;
  isLoading: boolean;
}

interface DestinationDef {
  id: string;
  name: string;
  flag: string;
  regions?: { id: string; name: string }[];
}

const DESTINATIONS: DestinationDef[] = [
  {
    id: "turkey",
    name: "Турция",
    flag: "🇹🇷",
    regions: [
      { id: "turkey", name: "Все регионы" },
      { id: "turkey_antalya", name: "Анталийское побережье" },
      { id: "turkey_alanya", name: "Аланья" },
      { id: "turkey_side", name: "Сиде" },
      { id: "turkey_belek", name: "Белек" },
      { id: "turkey_kemer", name: "Кемер" },
      { id: "turkey_aegean", name: "Эгейское побережье" },
      { id: "turkey_bodrum", name: "Бодрум" },
      { id: "turkey_marmaris", name: "Мармарис" },
    ],
  },
  {
    id: "egypt",
    name: "Египет",
    flag: "🇪🇬",
    regions: [
      { id: "egypt", name: "Все регионы" },
      { id: "egypt_sharm", name: "Шарм-эль-Шейх" },
      { id: "egypt_hurghada", name: "Хургада" },
      { id: "egypt_marsa", name: "Марса-Алам" },
    ],
  },
  {
    id: "greece",
    name: "Греция",
    flag: "🇬🇷",
    regions: [
      { id: "greece", name: "Все острова и регионы" },
      { id: "greece_crete", name: "Крит" },
      { id: "greece_rhodes", name: "Родос" },
      { id: "greece_corfu", name: "Корфу" },
      { id: "greece_zakynthos", name: "Закинф" },
      { id: "greece_kos", name: "Кос" },
    ],
  },
  {
    id: "cyprus",
    name: "Кипр",
    flag: "🇨🇾",
    regions: [
      { id: "cyprus", name: "Весь Кипр" },
      { id: "cyprus_south", name: "Южный Кипр (Айя-Напа, Пафос, Ларнака)" },
      { id: "cyprus_north", name: "Северный Кипр (Кирения, Фамагуста)" },
    ],
  },
  {
    id: "spain",
    name: "Испания",
    flag: "🇪🇸",
    regions: [
      { id: "spain", name: "Вся Испания" },
      { id: "spain_mallorca", name: "Майорка" },
      { id: "spain_canary", name: "Канарские острова (Тенерифе)" },
      { id: "spain_costa_del_sol", name: "Коста-дель-Соль" },
    ],
  },
  { id: "bulgaria", name: "Болгария", flag: "🇧🇬" },
  { id: "tunisia", name: "Тунис", flag: "🇹🇳" },
  { id: "uae", name: "ОАЭ", flag: "🇦🇪" },
  { id: "italy", name: "Италия", flag: "🇮🇹" },
  { id: "malta", name: "Мальта", flag: "🇲🇹" },
];

const AIRPORTS = [
  { code: "WAW", label: "Варшава (Chopin)" },
  { code: "WMI", label: "Модлин" },
  { code: "RDO", label: "Радом" },
  { code: "KTW", label: "Катовице" },
  { code: "KRK", label: "Краков" },
  { code: "GDN", label: "Гданьск" },
  { code: "WRO", label: "Вроцлав" },
  { code: "POZ", label: "Познань" },
  { code: "RZE", label: "Жешув" },
  { code: "BZG", label: "Быдгощ" },
  { code: "BER", label: "Берлин (BER • Арбитраж)" },
];

const CATERING_OPTIONS = [
  { id: "all_inclusive", label: "All Inclusive (Всё включено)", badge: "ТОП" },
  { id: "ultra_all_inclusive", label: "Ultra All Inclusive" },
  { id: "breakfast_and_dinner", label: "Завтрак + ужин (HB)" },
  { id: "breakfast", label: "Только завтрак (BB)" },
  { id: "all", label: "Любое питание" },
];

const HOTEL_STARS = [
  { val: 0, label: "Любые ★" },
  { val: 3, label: "3★+" },
  { val: 4, label: "4★+" },
  { val: 5, label: "5★" },
];

export const SearchHeader: React.FC<Props> = ({ onSearch, isLoading }) => {
  // 1. Destination & Region
  const [destination, setDestination] = useState("turkey");
  const [region, setRegion] = useState("turkey");

  // 2. Dates
  const todayStr = useMemo(() => new Date().toISOString().split("T")[0], []);
  const defaultMinDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 21);
    return d.toISOString().split("T")[0];
  }, []);
  const defaultMaxDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + 28);
    return d.toISOString().split("T")[0];
  }, []);

  const [startDateMin, setStartDateMin] = useState(defaultMinDate);
  const [startDateMax, setStartDateMax] = useState(defaultMaxDate);

  // 3. Duration
  const [minNights, setMinNights] = useState(7);
  const [maxNights, setMaxNights] = useState(8);

  // 4. Travelers & Children
  const [adults, setAdults] = useState(1);
  const [childrenCount, setChildrenCount] = useState(0);
  const [childrenAges, setChildrenAges] = useState<number[]>([]);

  // 5. Airports
  const [selectedAirports, setSelectedAirports] = useState<string[]>([
    "WAW",
    "KTW",
    "KRK",
    "GDN",
    "WRO",
    "POZ",
  ]);

  // 6. Catering, Stars, Price, Order
  const [catering, setCatering] = useState("all_inclusive");
  const [starsMin, setStarsMin] = useState(4);
  const [minPrice, setMinPrice] = useState<string>("");
  const [maxPrice, setMaxPrice] = useState<string>("8000");
  const [orderBy, setOrderBy] = useState("price");

  // Advanced toggles: Default is LIVE mode
  const [forceLive, setForceLive] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleMinPriceChange = (val: string) => {
    const digits = val.replace(/\D/g, "");
    setMinPrice(digits);
  };

  const handleMaxPriceChange = (val: string) => {
    const digits = val.replace(/\D/g, "");
    setMaxPrice(digits);
  };

  // Current active destination definition
  const currentDestDef = useMemo(
    () => DESTINATIONS.find((d) => d.id === destination) || DESTINATIONS[0],
    [destination]
  );

  // Handle destination change
  const handleDestinationChange = (destId: string) => {
    setDestination(destId);
    setRegion(destId);
  };

  // Handle children count change with dynamic ages
  const handleChildrenCountChange = (count: number) => {
    const c = Math.max(0, Math.min(4, count));
    setChildrenCount(c);
    setChildrenAges((prev) => {
      if (c === 0) return [];
      if (c > prev.length) {
        const added = Array(c - prev.length).fill(7); // default 7 y.o.
        return [...prev, ...added];
      }
      return prev.slice(0, c);
    });
  };

  const handleChildAgeChange = (idx: number, age: number) => {
    setChildrenAges((prev) => {
      const next = [...prev];
      next[idx] = age;
      return next;
    });
  };

  // Airport toggling
  const toggleAirport = (code: string) => {
    setSelectedAirports((prev) =>
      prev.includes(code)
        ? prev.length > 1
          ? prev.filter((a) => a !== code)
          : prev
        : [...prev, code]
    );
  };

  const selectAllAirports = () => {
    setSelectedAirports([
      "WAW",
      "WMI",
      "RDO",
      "KTW",
      "KRK",
      "GDN",
      "WRO",
      "POZ",
      "RZE",
      "BZG",
    ]);
  };

  const selectOnlyWarsaw = () => {
    setSelectedAirports(["WAW", "WMI", "RDO"]);
  };

  // Quick Date Horizon Presets
  const applyDatePreset = (preset: "lastminute" | "benchmark" | "ny" | "may" | "summer") => {
    const now = new Date();
    if (preset === "lastminute") {
      const minD = new Date(now);
      minD.setDate(now.getDate() + 1);
      const maxD = new Date(now);
      maxD.setDate(now.getDate() + 7);
      setStartDateMin(minD.toISOString().split("T")[0]);
      setStartDateMax(maxD.toISOString().split("T")[0]);
    } else if (preset === "benchmark") {
      const minD = new Date(now);
      minD.setDate(now.getDate() + 21);
      const maxD = new Date(now);
      maxD.setDate(now.getDate() + 28);
      setStartDateMin(minD.toISOString().split("T")[0]);
      setStartDateMax(maxD.toISOString().split("T")[0]);
      setMinNights(7);
      setMaxNights(8);
      setAdults(1);
      setChildrenCount(0);
      setChildrenAges([]);
    } else if (preset === "ny") {
      setStartDateMin("2026-12-24");
      setStartDateMax("2026-12-30");
      setMinNights(7);
      setMaxNights(10);
    } else if (preset === "may") {
      setStartDateMin("2027-04-28");
      setStartDateMax("2027-05-04");
      setMinNights(7);
      setMaxNights(9);
    } else if (preset === "summer") {
      setStartDateMin("2027-07-01");
      setStartDateMax("2027-07-15");
      setMinNights(7);
      setMaxNights(10);
    }
  };

  // Direct Fly.pl URL Builder for preview / direct booking
  const flyPlDirectUrl = useMemo(() => {
    const base = "https://fly.pl/szukaj-wycieczek/";
    const destCodeMap: Record<string, string> = {
      turkey: "39:",
      turkey_antalya: "39_3",
      turkey_aegean: "39_14",
      turkey_side: "39_3_40",
      turkey_alanya: "39_3_38",
      turkey_belek: "39_3_39",
      turkey_kemer: "39_3_41",
      turkey_bodrum: "39_14_45",
      turkey_marmaris: "39_14_44",
      egypt: "11:",
      egypt_sharm: "11_154",
      egypt_hurghada: "11_155",
      egypt_marsa: "11_156",
      greece: "14:",
      greece_crete: "14_1",
      greece_rhodes: "14_2",
      greece_corfu: "14_4",
      greece_zakynthos: "14_3",
      greece_kos: "14_5",
      cyprus: "6:",
      cyprus_south: "6_1",
      cyprus_north: "6_2",
      spain: "18:",
      spain_mallorca: "18_1",
      spain_canary: "18_13",
      spain_costa_del_sol: "18_3",
      bulgaria: "4:",
      tunisia: "37:",
      italy: "21:",
      uae: "44:",
      malta: "28:",
    };

    const airportMap: Record<string, string> = {
      WAW: "Warszawa",
      WMI: "Warszawa - Modlin",
      RDO: "Warszawa - Radom",
      KTW: "Katowice",
      KRK: "Kraków",
      GDN: "Gdańsk",
      WRO: "Wrocław",
      POZ: "Poznań",
      RZE: "Rzeszów",
      BZG: "Bydgoszcz",
      BER: "Berlin",
    };

    const targetKey = region || destination;
    const destCode = destCodeMap[targetKey] || "39:";
    const depStr = selectedAirports.map((a) => airportMap[a] || a).join(",");

    const formatDate = (iso: string) => {
      if (!iso) return "";
      const [y, m, d] = iso.split("-");
      return `${d}-${m}-${y}`;
    };

    const params = new URLSearchParams();
    params.set("destinationLocation", destCode);
    params.set("departureLocation", depStr);
    if (startDateMin) params.set("startDateMin", formatDate(startDateMin));
    if (startDateMax) params.set("startDateMax", formatDate(startDateMax));
    params.set("adults", String(adults));
    params.set("offerTypes", "accommodation_flight");
    params.set("durationFrom", String(minNights));
    params.set("durationTo", String(maxNights));
    params.set("order", orderBy);

    if (childrenCount > 0) {
      params.set("children", String(childrenCount));
      if (childrenAges.length) {
        params.set("childrenAges", childrenAges.join(","));
      }
    }
    if (catering && catering !== "all") {
      params.set("catering", catering);
    }
    if (starsMin > 0) {
      params.set("categoryRating", String(starsMin * 10));
    }
    const minP = minPrice ? Number(minPrice) : undefined;
    const maxP = maxPrice ? Number(maxPrice) : undefined;
    if (minP && minP > 0) {
      params.set("priceFrom", String(minP));
    }
    if (maxP && maxP > 0) {
      params.set("priceTo", String(maxP));
    }

    return `${base}?${params.toString()}`;
  }, [
    destination,
    region,
    selectedAirports,
    startDateMin,
    startDateMax,
    adults,
    childrenCount,
    childrenAges,
    minNights,
    maxNights,
    catering,
    starsMin,
    minPrice,
    maxPrice,
    orderBy,
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const minP = minPrice ? Number(minPrice) : undefined;
    const maxP = maxPrice ? Number(maxPrice) : undefined;
    onSearch({
      destination,
      region: region !== destination ? region : undefined,
      dates: {
        start_date_min: startDateMin,
        start_date_max: startDateMax,
      },
      duration: {
        min_nights: minNights,
        max_nights: maxNights,
      },
      travelers: {
        adults,
        children: childrenCount,
        children_ages: childrenAges,
      },
      airports: selectedAirports,
      catering: catering !== "all" ? catering : undefined,
      stars_min: starsMin > 0 ? starsMin : undefined,
      price_min_pln: minP && minP > 0 ? minP : undefined,
      price_max_pln: maxP && maxP > 0 ? maxP : undefined,
      order_by: orderBy,
      force_live_refresh: forceLive,
    });
  };

  const handleReset = () => {
    setDestination("turkey");
    setRegion("turkey");
    setStartDateMin(defaultMinDate);
    setStartDateMax(defaultMaxDate);
    setMinNights(7);
    setMaxNights(8);
    setAdults(1);
    setChildrenCount(0);
    setChildrenAges([]);
    setSelectedAirports(["WAW", "KTW", "KRK", "GDN", "WRO", "POZ"]);
    setCatering("all_inclusive");
    setStarsMin(4);
    setMinPrice("");
    setMaxPrice("8000");
    setOrderBy("price");
    setForceLive(true);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-md overflow-hidden transition-all">
      {/* Clean Sub-Header Action Bar */}
      <div className="px-5 py-3 bg-slate-50 border-b border-slate-200/90 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="text-xs font-extrabold text-slate-800 uppercase tracking-wider flex items-center gap-2">
            <span>Параметры поискового запроса</span>
            <span className="text-[10px] font-semibold bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200/80">
              Fly.pl 1:1 Live Sync
            </span>
          </span>
          <span className="hidden md:inline text-xs text-slate-300">|</span>
          <span className="hidden md:inline text-xs text-slate-500">
            Мгновенный запрос к базе цен и парсинг актуальных офферов
          </span>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={flyPlDirectUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white hover:bg-slate-100 text-slate-700 transition-all border border-slate-300 shadow-2xs"
            title="Открыть эту точную поисковую выдачу на официальном сайте Fly.pl"
          >
            <ExternalLink className="w-3.5 h-3.5 text-blue-600" />
            <span>Открыть на Fly.pl</span>
          </a>
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium text-slate-500 hover:text-slate-900 hover:bg-slate-200/60 transition-all"
            title="Сбросить все параметры к эталонным"
          >
            <RotateCcw className="w-3 h-3 text-slate-400" />
            <span className="hidden sm:inline">Сбросить</span>
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="p-5 space-y-4">
        {/* ROW 1: DESTINATIONS */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5 uppercase tracking-wide">
              <Compass className="w-4 h-4 text-blue-600" />
              <span>1. Страна назначения</span>
            </label>
            <span className="text-[11px] text-slate-400">
              Выбрано: <strong className="text-blue-600">{currentDestDef.name}</strong>
            </span>
          </div>

          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
            {DESTINATIONS.map((d) => {
              const isActive = destination === d.id;
              return (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => handleDestinationChange(d.id)}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold shrink-0 transition-all ${
                    isActive
                      ? "bg-blue-600 text-white shadow-md shadow-blue-500/25 ring-2 ring-blue-600/30 scale-[1.02]"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200/80"
                  }`}
                >
                  <span className="text-sm">{d.flag}</span>
                  <span>{d.name}</span>
                </button>
              );
            })}
          </div>

          {/* Sub-regions Pills (if available for country) */}
          {currentDestDef.regions && currentDestDef.regions.length > 1 && (
            <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center gap-1.5 overflow-x-auto scrollbar-thin text-xs">
              <span className="text-[11px] font-semibold text-slate-400 shrink-0 mr-1">
                Курорт:
              </span>
              {currentDestDef.regions.map((reg) => {
                const isRegActive = region === reg.id;
                return (
                  <button
                    key={reg.id}
                    type="button"
                    onClick={() => setRegion(reg.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium shrink-0 transition-colors ${
                      isRegActive
                        ? "bg-blue-100 text-blue-800 font-bold border border-blue-300"
                        : "bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200"
                    }`}
                  >
                    {reg.name}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* ROW 2: AIRPORTS */}
        <div className="bg-slate-50/70 p-3.5 rounded-xl border border-slate-200/80 space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-xs font-bold text-slate-700 flex items-center gap-1.5 uppercase tracking-wide">
              <Plane className="w-4 h-4 text-blue-600" />
              <span>2. Аэропорты вылета (Польша & BER)</span>
              <span className="ml-1 text-[11px] font-bold text-blue-600 bg-blue-100 px-1.5 py-0.2 rounded-full">
                {selectedAirports.length}
              </span>
            </label>

            <div className="flex items-center gap-2 text-xs">
              <button
                type="button"
                onClick={selectAllAirports}
                className="text-blue-600 hover:text-blue-700 font-semibold text-[11px]"
              >
                Все аэропорты Польши
              </button>
              <span className="text-slate-300">•</span>
              <button
                type="button"
                onClick={selectOnlyWarsaw}
                className="text-slate-500 hover:text-slate-700 text-[11px]"
              >
                Только Варшава
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {AIRPORTS.map((a) => {
              const isSelected = selectedAirports.includes(a.code);
              return (
                <button
                  key={a.code}
                  type="button"
                  onClick={() => toggleAirport(a.code)}
                  className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    isSelected
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
                  }`}
                  title={a.label}
                >
                  <span className="font-bold">{a.code}</span>
                  <span className="text-[10px] opacity-80 hidden md:inline">
                    {a.label.split(" ")[0]}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ROW 3: DATES, DURATION, TRAVELERS (CORE FILTER COCKPIT) */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
          {/* Dates Range with Presets */}
          <div className="md:col-span-5 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5 uppercase">
                <Calendar className="w-3.5 h-3.5 text-blue-600" />
                <span>3. Даты вылета (диапазон)</span>
              </label>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-500 font-medium block">
                  Вылет с
                </label>
                <input
                  type="date"
                  min={todayStr}
                  value={startDateMin}
                  onChange={(e) => setStartDateMin(e.target.value)}
                  className="w-full bg-white text-xs font-semibold text-slate-800 px-2.5 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-500 font-medium block">
                  Вылет по
                </label>
                <input
                  type="date"
                  min={startDateMin || todayStr}
                  value={startDateMax}
                  onChange={(e) => setStartDateMax(e.target.value)}
                  className="w-full bg-white text-xs font-semibold text-slate-800 px-2.5 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Quick Date Presets */}
            <div className="flex flex-wrap items-center gap-1 pt-1 text-[11px]">
              <button
                type="button"
                onClick={() => applyDatePreset("benchmark")}
                className="px-2 py-0.5 rounded-md bg-blue-100 hover:bg-blue-200 text-blue-800 font-semibold"
                title="Эталонный поиск: вылет сегодня + 3 недели (1 взрослый • 7-8 ночей)"
              >
                📏 Эталон (+3 нед)
              </button>
              <button
                type="button"
                onClick={() => applyDatePreset("lastminute")}
                className="px-2 py-0.5 rounded-md bg-amber-100 hover:bg-amber-200 text-amber-800 font-semibold"
                title="Ближайшие 7 дней"
              >
                ⚡ Горящие (7 дн)
              </button>
              <button
                type="button"
                onClick={() => applyDatePreset("ny")}
                className="px-2 py-0.5 rounded-md bg-emerald-100 hover:bg-emerald-200 text-emerald-800 font-semibold"
              >
                🎄 Новый Год
              </button>
              <button
                type="button"
                onClick={() => applyDatePreset("summer")}
                className="px-2 py-0.5 rounded-md bg-purple-100 hover:bg-purple-200 text-purple-800 font-semibold"
              >
                ☀️ Лето 2027
              </button>
            </div>
          </div>

          {/* Duration Selector */}
          <div className="md:col-span-3 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-2">
            <label className="text-[11px] font-bold text-slate-700 flex items-center justify-between uppercase">
              <span>4. Длительность</span>
              <span className="text-blue-600 font-extrabold">
                {minNights}–{maxNights} ночей
              </span>
            </label>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-500 font-medium block">
                  От (ночей)
                </label>
                <select
                  value={minNights}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setMinNights(v);
                    if (v > maxNights) setMaxNights(v);
                  }}
                  className="w-full bg-white text-xs font-semibold text-slate-800 px-2 py-1.5 rounded-lg border border-slate-200 focus:outline-none"
                >
                  {[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 21].map((n) => (
                    <option key={n} value={n}>
                      {n} ночей
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[10px] text-slate-500 font-medium block">
                  До (ночей)
                </label>
                <select
                  value={maxNights}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setMaxNights(v);
                    if (v < minNights) setMinNights(v);
                  }}
                  className="w-full bg-white text-xs font-semibold text-slate-800 px-2 py-1.5 rounded-lg border border-slate-200 focus:outline-none"
                >
                  {[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 21, 28].map((n) => (
                    <option key={n} value={n}>
                      {n} ночей
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Quick duration presets */}
            <div className="flex items-center gap-1 pt-1 text-[11px]">
              {[
                { min: 7, max: 8, label: "7–8 дн" },
                { min: 7, max: 10, label: "7–10 дн" },
                { min: 9, max: 11, label: "9–11 дн" },
                { min: 13, max: 16, label: "13–16 дн" },
              ].map((dp) => (
                <button
                  key={dp.label}
                  type="button"
                  onClick={() => {
                    setMinNights(dp.min);
                    setMaxNights(dp.max);
                  }}
                  className={`px-1.5 py-0.5 rounded text-[10px] font-semibold transition-colors ${
                    minNights === dp.min && maxNights === dp.max
                      ? "bg-blue-600 text-white"
                      : "bg-white hover:bg-slate-200 text-slate-600 border border-slate-200"
                  }`}
                >
                  {dp.label}
                </button>
              ))}
            </div>
          </div>

          {/* Travelers & Children Selector (1:1 with Fly.pl) */}
          <div className="md:col-span-4 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-2">
            <label className="text-[11px] font-bold text-slate-700 flex items-center justify-between uppercase">
              <span className="flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-blue-600" />
                <span>5. Туристы</span>
              </span>
              <span className="text-blue-600 font-bold text-xs">
                {adults} взр. {childrenCount > 0 ? `+ ${childrenCount} реб.` : ""}
              </span>
            </label>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-500 font-medium block">
                  Взрослые
                </label>
                <div className="flex items-center bg-white rounded-lg border border-slate-200 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setAdults((prev) => Math.max(1, prev - 1))}
                    className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 font-bold"
                  >
                    –
                  </button>
                  <span className="flex-1 text-center font-bold text-slate-800">
                    {adults}
                  </span>
                  <button
                    type="button"
                    onClick={() => setAdults((prev) => Math.min(6, prev + 1))}
                    className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 font-bold"
                  >
                    +
                  </button>
                </div>
              </div>

              <div>
                <label className="text-[10px] text-slate-500 font-medium block">
                  Дети (до 17 лет)
                </label>
                <div className="flex items-center bg-white rounded-lg border border-slate-200 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => handleChildrenCountChange(childrenCount - 1)}
                    className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 font-bold"
                  >
                    –
                  </button>
                  <span className="flex-1 text-center font-bold text-slate-800">
                    {childrenCount}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleChildrenCountChange(childrenCount + 1)}
                    className="px-2.5 py-1 text-slate-600 hover:bg-slate-100 font-bold"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>

            {/* Dynamic Child Ages Selectors (1:1 with Fly.pl) */}
            {childrenCount > 0 && (
              <div className="pt-2 border-t border-slate-200/80 space-y-1">
                <span className="text-[10px] font-semibold text-slate-500 block">
                  Возраст детей на момент поездки:
                </span>
                <div className="grid grid-cols-2 gap-1.5">
                  {childrenAges.map((age, idx) => (
                    <div key={idx} className="flex items-center gap-1">
                      <span className="text-[10px] text-slate-400 font-bold">
                        #{idx + 1}:
                      </span>
                      <select
                        value={age}
                        onChange={(e) => handleChildAgeChange(idx, Number(e.target.value))}
                        className="bg-white text-[11px] font-semibold text-slate-800 px-1.5 py-1 rounded border border-slate-200 flex-1"
                      >
                        {Array.from({ length: 18 }, (_, a) => (
                          <option key={a} value={a}>
                            {a} {a === 1 ? "год" : a < 5 ? "года" : "лет"}
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ROW 4: CATERING, HOTEL CATEGORY & PRICE (ADVANCED EXPANDABLE) */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 pt-1">
          {/* Catering */}
          <div className="md:col-span-4 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
            <label className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5 uppercase">
              <Utensils className="w-3.5 h-3.5 text-blue-600" />
              <span>6. Питание (Catering)</span>
            </label>
            <select
              value={catering}
              onChange={(e) => setCatering(e.target.value)}
              className="w-full bg-white text-xs font-semibold text-slate-800 px-2.5 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {CATERING_OPTIONS.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {/* Hotel Category / Stars */}
          <div className="md:col-span-3 bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
            <label className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5 uppercase">
              <Star className="w-3.5 h-3.5 text-amber-500" />
              <span>7. Категория отеля</span>
            </label>
            <div className="grid grid-cols-4 gap-1">
              {HOTEL_STARS.map((s) => (
                <button
                  key={s.val}
                  type="button"
                  onClick={() => setStarsMin(s.val)}
                  className={`py-1.5 rounded-lg text-xs font-semibold text-center transition-colors ${
                    starsMin === s.val
                      ? "bg-amber-500 text-white shadow-sm font-bold"
                      : "bg-white hover:bg-slate-100 text-slate-700 border border-slate-200"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* 8. Budget Range: От - До (PLN) with digits-only validation */}
          <div className="md:col-span-3 bg-slate-50 p-2.5 rounded-xl border border-slate-200 space-y-1.5">
            <label className="text-[11px] font-bold text-slate-700 flex items-center justify-between uppercase">
              <span>8. Бюджет тура (PLN)</span>
              <span className="text-emerald-600 font-extrabold text-[11px]">
                {minPrice || maxPrice
                  ? `${minPrice ? `от ${Number(minPrice).toLocaleString("ru-RU")}` : "от 0"} ${
                      maxPrice ? `до ${Number(maxPrice).toLocaleString("ru-RU")}` : ""
                    } zł`
                  : "Любой"}
              </span>
            </label>

            {/* Inputs: От - До */}
            <div className="grid grid-cols-2 gap-1.5">
              <div className="relative">
                <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-400 uppercase">
                  От
                </span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={minPrice}
                  onChange={(e) => handleMinPriceChange(e.target.value)}
                  placeholder="0"
                  className="w-full bg-white text-xs font-bold text-slate-800 pl-7 pr-6 py-1 rounded-lg border border-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-slate-400">
                  zł
                </span>
              </div>
              <div className="relative">
                <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-400 uppercase">
                  До
                </span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={maxPrice}
                  onChange={(e) => handleMaxPriceChange(e.target.value)}
                  placeholder="20 000"
                  className="w-full bg-white text-xs font-bold text-slate-800 pl-7 pr-6 py-1 rounded-lg border border-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                />
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-semibold text-slate-400">
                  zł
                </span>
              </div>
            </div>

            {/* Quick Presets */}
            <div className="flex items-center gap-1">
              {[5000, 8000, 10000, 15000].map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setMaxPrice(String(p))}
                  className={`flex-1 py-0.5 text-[10px] font-semibold rounded transition-colors ${
                    maxPrice === String(p)
                      ? "bg-emerald-600 text-white font-bold"
                      : "bg-white hover:bg-slate-100 text-slate-700 border border-slate-200"
                  }`}
                >
                  {p / 1000}k
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  setMinPrice("");
                  setMaxPrice("");
                }}
                className={`px-1.5 py-0.5 text-[10px] font-semibold rounded transition-colors ${
                  !minPrice && !maxPrice
                    ? "bg-slate-800 text-white font-bold"
                    : "bg-white hover:bg-slate-100 text-slate-500 border border-slate-200"
                }`}
              >
                Все
              </button>
            </div>
          </div>

          {/* Search Trigger Button */}
          <div className="md:col-span-2 flex flex-col justify-end">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs uppercase tracking-wider rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-blue-500/25 active:scale-[0.98] disabled:opacity-60"
            >
              {isLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              <span>{isLoading ? "Поиск..." : "Найти туры"}</span>
            </button>
          </div>
        </div>

        {/* BOTTOM CONTROLS: LIVE REFRESH & SORTING */}
        <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs">
          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={forceLive}
              onChange={(e) => setForceLive(e.target.checked)}
              className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4"
            />
            <span className="flex items-center gap-1.5 font-semibold text-slate-700">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              Принудительный LIVE-запрос к Fly.pl
              <span className="text-[10px] text-slate-400 font-normal hidden sm:inline">
                (обратиться к живому API скрапинга прямо сейчас)
              </span>
            </span>
          </label>

          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Сортировка:</span>
            <select
              value={orderBy}
              onChange={(e) => setOrderBy(e.target.value)}
              className="bg-slate-50 text-xs font-semibold text-slate-700 px-2 py-1 rounded-lg border border-slate-200 focus:outline-none"
            >
              <option value="price">Сначала дешёвые (цена ↑)</option>
              <option value="rating">По рейтингу TripAdvisor</option>
              <option value="deal_score">По выгодности (Deal Score)</option>
              <option value="discount">По величине скидки</option>
            </select>
          </div>
        </div>
      </form>
    </div>
  );
};
