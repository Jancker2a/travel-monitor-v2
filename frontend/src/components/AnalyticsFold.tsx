import React, { useEffect, useRef } from "react";
import { TrendingDown, TrendingUp, Plane, Sparkles, ChevronDown } from "lucide-react";
import { SearchHotelItem, PriceDropItem, AirportStat } from "../types";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface AnalyticsFoldProps {
  hotels: SearchHotelItem[];
  topDrops: PriceDropItem[];
  airportStats: AirportStat[];
  onSelectHotel: (hotelId: string) => void;
}

export const AnalyticsFold: React.FC<AnalyticsFoldProps> = ({
  hotels,
  topDrops,
  airportStats,
  onSelectHotel,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const detailsRef = useRef<HTMLDetailsElement>(null);

  // Render Top-10 cheap offers horizontal bar chart
  useEffect(() => {
    if (!hotels.length || !chartRef.current || !window.Plotly) return;

    // Take top 10 cheapest hotels
    const top10 = [...hotels]
      .sort((a, b) => a.current_offer.total_price_pln - b.current_offer.total_price_pln)
      .slice(0, 10)
      .reverse();

    const hotelNames = top10.map((h) => {
      const name = h.hotel_name;
      return name.length > 22 ? name.substring(0, 20) + "…" : name;
    });
    const prices = top10.map((h) => h.current_offer.total_price_pln);
    const hoverTexts = top10.map(
      (h) =>
        `<b>${h.hotel_name}</b><br>` +
        `Цена: <b>${h.current_offer.total_price_pln.toLocaleString("ru-RU")} zł</b><br>` +
        `Вылет: ${h.current_offer.airport} (${h.current_offer.departure_date})<br>` +
        `Deal Score: ${h.intelligence.deal_score}/100`
    );

    const data = [
      {
        type: "bar",
        orientation: "h",
        y: hotelNames,
        x: prices,
        text: prices.map((p) => `${p.toLocaleString("ru-RU")} zł`),
        textposition: "auto",
        hoverinfo: "text",
        hovertext: hoverTexts,
        marker: {
          color: prices.map((_, i) =>
            i === prices.length - 1 ? "#0284c7" : "#38bdf8"
          ),
          opacity: 0.9,
          line: { color: "#0284c7", width: 1 },
        },
      },
    ];

    const layout = {
      margin: { l: 140, r: 40, t: 30, b: 40 },
      height: 290,
      title: {
        text: "Топ-10 доступных предложений направления",
        font: { size: 13, family: "Inter, sans-serif", color: "#0f172a" },
        x: 0.05,
      },
      xaxis: {
        title: "Цена за тур (PLN)",
        gridcolor: "#f1f5f9",
        zeroline: false,
        tickfont: { size: 10, color: "#64748b" },
      },
      yaxis: {
        automargin: true,
        tickfont: { size: 11, color: "#334155", family: "Inter, sans-serif" },
      },
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
    };

    const config = {
      responsive: true,
      displayModeBar: false,
    };

    window.Plotly.react(chartRef.current, data, layout, config);
  }, [hotels]);

  // Handle accordion toggle resize
  const handleToggle = () => {
    if (!window.Plotly || !chartRef.current) return;
    const resizePlot = () => {
      if (chartRef.current) window.Plotly.Plots.resize(chartRef.current);
    };
    setTimeout(resizePlot, 40);
    setTimeout(resizePlot, 150);
    setTimeout(resizePlot, 350);
  };

  return (
    <details
      ref={detailsRef}
      className="dashboard-fold"
      id="analyticsFold"
      open
      onToggle={handleToggle}
    >
      <summary className="dashboard-fold-summary">
        <div className="flex items-center gap-2">
          <span>📊</span>
          <span>Аналитика и динамика цен (Топ-10, динамика падений, разброс аэропортов)</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-blue-600 font-semibold">
          <span>Свернуть / Развернуть</span>
          <ChevronDown className="w-4 h-4 transition-transform group-open:rotate-180" />
        </div>
      </summary>

      <div className="dashboard-fold-content space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Chart: Top 10 Offers */}
          <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200/80 p-4 shadow-sm">
            <div ref={chartRef} id="analyticsTop10Chart" className="w-full" />
          </div>

          {/* Right Column: Top Drops & Airport Summary */}
          <div className="lg:col-span-5 space-y-4">
            {/* Top Drops List */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-4 shadow-sm">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 uppercase tracking-wider">
                  <TrendingDown className="w-4 h-4 text-emerald-600" />
                  <span>Топ падений за 48ч</span>
                </div>
                <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                  Сигналы к покупке
                </span>
              </div>

              <div className="divide-y divide-slate-100 mt-2 max-h-[160px] overflow-y-auto">
                {topDrops.length > 0 ? (
                  topDrops.slice(0, 4).map((drop) => (
                    <div
                      key={drop.cohort_hash}
                      onClick={() => onSelectHotel(drop.hotel_id)}
                      className="py-2.5 flex items-center justify-between hover:bg-slate-50 cursor-pointer px-1 rounded-lg transition-colors"
                    >
                      <div className="min-w-0 pr-2">
                        <div className="text-xs font-bold text-slate-900 truncate">
                          {drop.hotel_name}
                        </div>
                        <div className="text-[10px] text-slate-500 flex items-center gap-1">
                          <span>{drop.airport}</span>
                          <span>•</span>
                          <span>{drop.departure_date}</span>
                          <span>•</span>
                          <span>{drop.duration_nights}н</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-xs font-extrabold text-emerald-600">
                          −{drop.drop_amount_pln.toLocaleString("ru-RU")} zł
                        </div>
                        <div className="text-[10px] text-slate-400 line-through">
                          {drop.previous_price_pln.toLocaleString("ru-RU")} zł
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="py-4 text-center text-xs text-slate-400">
                    Резких колебаний цен за последние 48 часов не зафиксировано
                  </div>
                )}
              </div>
            </div>

            {/* Airport Benchmark Widget */}
            <div className="bg-white rounded-2xl border border-slate-200/80 p-4 shadow-sm">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100 text-xs font-bold text-slate-800 uppercase tracking-wider">
                <div className="flex items-center gap-1.5">
                  <Plane className="w-4 h-4 text-blue-600" />
                  <span>Вылет из аэропортов</span>
                </div>
                <span className="text-[10px] text-slate-400 font-normal">Мин. цена</span>
              </div>

              <div className="grid grid-cols-3 gap-2 mt-3">
                {airportStats.length > 0 ? (
                  airportStats.slice(0, 3).map((ap) => (
                    <div
                      key={ap.airport_code}
                      className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 text-center"
                    >
                      <div className="text-xs font-extrabold text-blue-600">
                        {ap.airport_code}
                      </div>
                      <div className="text-xs font-bold text-slate-900 mt-0.5">
                        {ap.min_price_pln.toLocaleString("ru-RU")} zł
                      </div>
                      <div className="text-[9px] text-slate-400 mt-0.5">
                        ср. {ap.avg_price_pln.toLocaleString("ru-RU")} zł
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="col-span-3 text-center text-xs text-slate-400 py-2">
                    Загрузка статистики аэропортов...
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </details>
  );
};
