import React, { useState, useEffect } from "react";
import { Plane, TrendingDown, ArrowRight, ExternalLink, RefreshCw, Star } from "lucide-react";
import { getArbitrageDeals } from "../services/api";
import { LoadingSpinner } from "./common/LoadingSpinner";

export const GermanArbitrageView: React.FC = () => {
  const [deals, setDeals] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [minSavings, setMinSavings] = useState(300);

  const loadDeals = async () => {
    setIsLoading(true);
    try {
      const data = await getArbitrageDeals(minSavings);
      setDeals(data);
    } catch (err) {
      console.error("Failed to load arbitrage deals:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDeals();
  }, [minSavings]);

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-6 rounded-3xl shadow-lg border border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl">🇩🇪</span>
            <h2 className="text-lg font-black tracking-tight text-white">
              НЕМЕЦКИЙ АРБИТРАЖ (БЕРЛИН BER vs ПОЛЬША)
            </h2>
            <span className="text-[10px] font-bold bg-amber-400 text-slate-950 px-2 py-0.5 rounded-full">
              CROSS-BORDER RADAR
            </span>
          </div>
          <p className="text-xs text-slate-300">
            Сравнение идентичных отелей и дат при вылете из Берлина (немецкие туроператоры TUI/FTI/Alltours) против аэропортов Польши
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs bg-slate-800/80 px-3 py-1.5 rounded-xl border border-slate-700">
            <span className="text-slate-400 font-medium">Мин. выгода:</span>
            <select
              value={minSavings}
              onChange={(e) => setMinSavings(Number(e.target.value))}
              className="bg-transparent text-amber-400 font-bold focus:outline-none"
            >
              <option value="100" className="bg-slate-900">от 100 zł</option>
              <option value="300" className="bg-slate-900">от 300 zł</option>
              <option value="500" className="bg-slate-900">от 500 zł</option>
              <option value="1000" className="bg-slate-900">от 1000 zł</option>
            </select>
          </div>

          <button
            onClick={loadDeals}
            className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white transition-colors border border-slate-700"
            title="Обновить"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-400" : ""}`} />
          </button>
        </div>
      </div>

      {/* Deals Grid */}
      {isLoading ? (
        <LoadingSpinner
          variant="card"
          size="lg"
          label="Сканируем спреды цен Берлин vs Варшава..."
          description="Поиск арбитражных предложений немецких туроператоров (FTI Touristik, TUI Deutschland)"
        />
      ) : deals.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {deals.map((d, idx) => (
            <div
              key={`${d.hotel_id}_${idx}`}
              className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
            >
              {/* Hotel Header Image */}
              <div className="relative h-40 bg-slate-100 overflow-hidden">
                <img
                  src={d.main_image_url || "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=600&q=80"}
                  alt={d.hotel_name}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
                <div className="absolute top-3 right-3 bg-rose-600 text-white text-xs font-black px-2.5 py-1 rounded-xl shadow-md flex items-center gap-1">
                  <TrendingDown className="w-3.5 h-3.5" />
                  <span>-{d.savings_pln.toLocaleString("ru-RU")} zł</span>
                </div>
              </div>

              {/* Hotel Info */}
              <div className="p-4 flex-1">
                <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-1">
                  <span className="font-semibold text-slate-700">{d.country}</span>
                  <div className="flex items-center text-amber-500">
                    {Array.from({ length: d.stars || 4 }).map((_, i) => (
                      <Star key={i} className="w-3 h-3 fill-current" />
                    ))}
                  </div>
                </div>

                <h3 className="font-bold text-slate-900 text-sm line-clamp-1 mb-2">
                  {d.hotel_name}
                </h3>

                <div className="text-[11px] text-slate-500 mb-3">
                  📅 Вылет: <b>{d.checkin_date}</b> ({d.duration_nights} ночей)
                </div>

                {/* Price Comparison Block */}
                <div className="bg-slate-50 rounded-xl p-3 border border-slate-100 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-500 flex items-center gap-1">
                      <span>🇵🇱 {d.polish_airport}</span>
                      <span className="text-[10px] text-slate-400">({d.polish_operator})</span>
                    </span>
                    <span className="font-bold text-slate-700 line-through">
                      {d.polish_price_pln.toLocaleString("ru-RU")} zł
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-blue-700 flex items-center gap-1">
                      <span>🇩🇪 {d.berlin_airport}</span>
                      <span className="text-[10px] text-blue-500">({d.berlin_operator})</span>
                    </span>
                    <span className="text-emerald-700 text-sm font-extrabold">
                      {d.berlin_price_pln.toLocaleString("ru-RU")} zł
                    </span>
                  </div>
                </div>
              </div>

              {/* Bottom CTA */}
              <div className="px-4 pb-4 pt-1 space-y-2">
                <div className="w-full py-1.5 px-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold text-center">
                  {d.verdict}
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={
                      d.berlin_booking_url && !d.berlin_booking_url.includes("fly.pl")
                        ? d.berlin_booking_url
                        : `https://www.check24.de/suche/?q=${encodeURIComponent(d.hotel_name)}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 py-2 px-3 rounded-xl bg-[#034ea2] hover:bg-[#023b7a] text-white text-xs font-bold text-center flex items-center justify-center gap-1 transition-colors shadow-sm"
                  >
                    <span>🇩🇪 Check24 BER</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                  <a
                    href={d.polish_booking_url || `https://fly.pl/szukaj-wycieczek/?hotelName=${encodeURIComponent(d.hotel_name)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="py-2 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold text-center flex items-center justify-center gap-1 transition-colors border border-slate-200"
                    title="Сравнить с вылетом из Польши"
                  >
                    <span>🇵🇱 Fly.pl</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-3xl border border-slate-200 p-12 text-center text-slate-500 max-w-lg mx-auto">
          <div className="text-4xl mb-3">🇩🇪</div>
          <h3 className="text-lg font-bold text-slate-800">Арбитражные связки рассчитываются</h3>
          <p className="text-xs text-slate-500 mt-1">
            Запустите фоновый скрапер для фильтров Берлина или снизьте порог минимальной выгоды в правом верхнем углу.
          </p>
        </div>
      )}
    </div>
  );
};

