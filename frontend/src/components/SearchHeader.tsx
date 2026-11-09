import React, { useState } from "react";
import { Search, Calendar, Users, Plane, RefreshCw, Sparkles } from "lucide-react";
import { SearchRequest } from "../types";

interface Props {
  onSearch: (req: SearchRequest) => void;
  isLoading: boolean;
}

const DESTINATIONS = [
  { id: "turkey", name: "Турция", flag: "🇹🇷" },
  { id: "egypt", name: "Египет", flag: "🇪🇬" },
  { id: "greece", name: "Греция", flag: "🇬🇷" },
  { id: "cyprus", name: "Кипр", flag: "🇨🇾" },
  { id: "spain", name: "Испания", flag: "🇪🇸" },
];

const AIRPORTS = [
  { code: "WAW", label: "Варшава" },
  { code: "KTW", label: "Катовице" },
  { code: "KRK", label: "Краков" },
  { code: "GDN", label: "Гданьск" },
  { code: "WRO", label: "Вроцлав" },
  { code: "POZ", label: "Познань" },
  { code: "BER", label: "Берлин" },
];

export const SearchHeader: React.FC<Props> = ({ onSearch, isLoading }) => {
  const [destination, setDestination] = useState("turkey");
  const [startDateMin, setStartDateMin] = useState("2026-11-15");
  const [startDateMax, setStartDateMax] = useState("2026-11-25");
  const [minNights, setMinNights] = useState(7);
  const [maxNights, setMaxNights] = useState(10);
  const [adults, setAdults] = useState(2);
  const [selectedAirports, setSelectedAirports] = useState<string[]>(["WAW"]);
  const [forceLive, setForceLive] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch({
      destination,
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
        children: 0,
        children_ages: [],
      },
      airports: selectedAirports,
      force_live_refresh: forceLive,
    });
  };

  const toggleAirport = (code: string) => {
    setSelectedAirports((prev) =>
      prev.includes(code)
        ? prev.length > 1
          ? prev.filter((a) => a !== code)
          : prev
        : [...prev, code]
    );
  };

  return (
    <div className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-30">
      <div className="max-w-[1880px] mx-auto px-4 py-4 sm:px-6 lg:px-8">
        {/* Top Destination Pills */}
        <div className="flex items-center gap-2 overflow-x-auto pb-3 scrollbar-none">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-2 shrink-0">
            Направление:
          </span>
          {DESTINATIONS.map((d) => (
            <button
              key={d.id}
              type="button"
              onClick={() => setDestination(d.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all shrink-0 ${
                destination === d.id
                  ? "bg-blue-600 text-white shadow-sm ring-2 ring-blue-600/30"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              <span>{d.flag}</span>
              <span>{d.name}</span>
            </button>
          ))}
        </div>

        {/* Main Search Controls Form */}
        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-12 gap-3 pt-2">
          {/* Dates Range */}
          <div className="md:col-span-4 bg-slate-50 p-2.5 rounded-xl border border-slate-200 flex items-center gap-3">
            <Calendar className="w-5 h-5 text-blue-600 shrink-0" />
            <div className="flex-1 flex items-center gap-2 text-xs">
              <div>
                <label className="text-[10px] text-slate-500 font-semibold uppercase block">Вылет с</label>
                <input
                  type="date"
                  value={startDateMin}
                  onChange={(e) => setStartDateMin(e.target.value)}
                  className="bg-transparent font-medium text-slate-800 focus:outline-none cursor-pointer"
                />
              </div>
              <span className="text-slate-400 font-light">—</span>
              <div>
                <label className="text-[10px] text-slate-500 font-semibold uppercase block">Вылет по</label>
                <input
                  type="date"
                  value={startDateMax}
                  onChange={(e) => setStartDateMax(e.target.value)}
                  className="bg-transparent font-medium text-slate-800 focus:outline-none cursor-pointer"
                />
              </div>
            </div>
          </div>

          {/* Duration & Travelers */}
          <div className="md:col-span-3 bg-slate-50 p-2.5 rounded-xl border border-slate-200 flex items-center justify-between">
            <div>
              <label className="text-[10px] text-slate-500 font-semibold uppercase block">Ночей</label>
              <select
                value={`${minNights}-${maxNights}`}
                onChange={(e) => {
                  const [min, max] = e.target.value.split("-").map(Number);
                  setMinNights(min);
                  setMaxNights(max);
                }}
                className="bg-transparent text-xs font-medium text-slate-800 focus:outline-none cursor-pointer"
              >
                <option value="7-8">7 - 8 ночей</option>
                <option value="7-10">7 - 10 ночей</option>
                <option value="9-12">9 - 12 ночей</option>
                <option value="13-16">13 - 16 ночей (2 недели)</option>
              </select>
            </div>
            <div className="h-6 w-px bg-slate-200" />
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-slate-400" />
              <div>
                <label className="text-[10px] text-slate-500 font-semibold uppercase block">Туристы</label>
                <select
                  value={adults}
                  onChange={(e) => setAdults(Number(e.target.value))}
                  className="bg-transparent text-xs font-medium text-slate-800 focus:outline-none cursor-pointer"
                >
                  <option value={1}>1 взрослый</option>
                  <option value={2}>2 взрослых</option>
                  <option value={3}>3 взрослых</option>
                  <option value={4}>4 взрослых</option>
                </select>
              </div>
            </div>
          </div>

          {/* Departure Airport Selector */}
          <div className="md:col-span-3 bg-slate-50 p-2.5 rounded-xl border border-slate-200 flex items-center gap-2 overflow-x-auto">
            <Plane className="w-4 h-4 text-slate-400 shrink-0" />
            <div className="flex items-center gap-1">
              {AIRPORTS.map((a) => (
                <button
                  key={a.code}
                  type="button"
                  onClick={() => toggleAirport(a.code)}
                  className={`text-[11px] font-semibold px-2 py-1 rounded-md transition-colors ${
                    selectedAirports.includes(a.code)
                      ? "bg-blue-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-200"
                  }`}
                  title={a.label}
                >
                  {a.code}
                </button>
              ))}
            </div>
          </div>

          {/* Submit Search Button */}
          <div className="md:col-span-2 flex items-center gap-2">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full h-full min-h-[44px] bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm rounded-xl flex items-center justify-center gap-2 transition-all shadow-md shadow-blue-500/20 active:scale-[0.98] disabled:opacity-60"
            >
              {isLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Search className="w-4 h-4" />
              )}
              <span>{isLoading ? "Поиск..." : "Найти туры"}</span>
            </button>
          </div>
        </form>

        {/* Live Refresh Checkbox */}
        <div className="mt-2.5 flex items-center justify-between text-xs text-slate-500">
          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={forceLive}
              onChange={(e) => setForceLive(e.target.checked)}
              className="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
            />
            <span className="flex items-center gap-1 font-medium text-slate-600">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              Принудительный live-добор с Fly.pl (если нужны только свежайшие офферы)
            </span>
          </label>
        </div>
      </div>
    </div>
  );
};

