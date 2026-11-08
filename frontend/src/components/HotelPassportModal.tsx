import React, { useEffect, useRef, useState } from "react";
import { X, TrendingDown, Star, Calendar, RefreshCw } from "lucide-react";
import { HotelPassport } from "../types";
import { getHotelPassport } from "../services/api";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface Props {
  hotelId: string | null;
  onClose: () => void;
}

export const HotelPassportModal: React.FC<Props> = ({ hotelId, onClose }) => {
  const [passport, setPassport] = useState<HotelPassport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hotelId) return;
    setIsLoading(true);
    getHotelPassport(hotelId)
      .then((data) => {
        setPassport(data);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load hotel passport:", err);
        setIsLoading(false);
      });
  }, [hotelId]);

  // Render Plotly chart whenever passport data is ready
  useEffect(() => {
    if (!passport || !chartRef.current || !window.Plotly) return;

    const xValues = passport.history_points.map((p) => p.recorded_at);
    const yValues = passport.history_points.map((p) => p.total_price_pln);
    const hoverTexts = passport.history_points.map(
      (p) =>
        `<b>${p.total_price_pln.toLocaleString("ru-RU")} zł</b><br>` +
        `📅 Даты поездки: ${p.departure_date} (${p.duration_nights} ночей)<br>` +
        `🛫 Аэропорт: ${p.airport}<br>` +
        `💵 За ночь/чел: ${p.price_per_night_per_pax.toFixed(0)} zł`
    );

    const trace = {
      x: xValues,
      y: yValues,
      text: hoverTexts,
      hoverinfo: "text",
      mode: "lines+markers",
      type: "scatter",
      line: { color: "#2563eb", width: 2.5, shape: "spline" },
      marker: {
        color: "#1d4ed8",
        size: 7,
        line: { color: "#ffffff", width: 1.5 },
      },
    };

    const layout = {
      margin: { t: 20, r: 20, b: 40, l: 60 },
      autosize: true,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: {
        gridcolor: "#f1f5f9",
        tickfont: { color: "#64748b", size: 10 },
        showline: true,
        linecolor: "#e2e8f0",
      },
      yaxis: {
        gridcolor: "#f1f5f9",
        tickfont: { color: "#64748b", size: 10 },
        ticksuffix: " zł",
        showline: true,
        linecolor: "#e2e8f0",
      },
      hoverlabel: {
        bgcolor: "#1e293b",
        font: { color: "#ffffff", size: 11, family: "Inter" },
      },
    };

    const config = {
      responsive: true,
      displayModeBar: false,
    };

    window.Plotly.newPlot(chartRef.current, [trace], layout, config);

    // Multi-phase resize per project web standards
    const timers = [40, 150, 350].map((delay) =>
      setTimeout(() => {
        if (chartRef.current && window.Plotly) {
          window.Plotly.Plots.resize(chartRef.current);
        }
      }, delay)
    );

    return () => {
      timers.forEach(clearTimeout);
    };
  }, [passport]);

  if (!hotelId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-3xl max-w-4xl w-full max-h-[90vh] overflow-y-auto shadow-2xl border border-slate-200">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-100 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
              <span>{passport?.country || "Отель"}</span>
              {passport?.region && <span>• {passport.region}</span>}
              <span className="text-amber-500 flex items-center">
                {Array.from({ length: passport?.stars || 4 }).map((_, i) => (
                  <Star key={i} className="w-3 h-3 fill-current" />
                ))}
              </span>
            </div>
            <h2 className="text-2xl font-extrabold text-slate-900">
              {passport?.display_name || "Загрузка паспорта отеля..."}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {isLoading ? (
            <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
              <p className="text-sm font-medium">Анализируем исторические срезы цен...</p>
            </div>
          ) : passport ? (
            <div>
              {/* Stat Cards Row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                <div className="bg-emerald-50 border border-emerald-100 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-emerald-700 uppercase">Исторический минимум</div>
                  <div className="text-xl font-extrabold text-emerald-900 mt-0.5">
                    {passport.all_time_min_pln.toLocaleString("ru-RU")} zł
                  </div>
                </div>

                <div className="bg-blue-50 border border-blue-100 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-blue-700 uppercase">Медианная цена</div>
                  <div className="text-xl font-extrabold text-blue-900 mt-0.5">
                    {passport.typical_median_pln.toLocaleString("ru-RU")} zł
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-slate-600 uppercase">Максимум сезона</div>
                  <div className="text-xl font-extrabold text-slate-800 mt-0.5">
                    {passport.all_time_max_pln.toLocaleString("ru-RU")} zł
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-slate-600 uppercase">Всего замеров</div>
                  <div className="text-xl font-extrabold text-slate-800 mt-0.5">
                    {passport.history_points.length} точек
                  </div>
                </div>
              </div>

              {/* Plotly Chart Container */}
              <div className="bg-slate-50 p-4 rounded-2xl border border-slate-200">
                <div className="text-xs font-bold text-slate-700 mb-2 flex items-center justify-between">
                  <span>График колебания цен во времени:</span>
                  <span className="text-[11px] font-normal text-slate-500">
                    💡 Наведите курсор на точку, чтобы увидеть даты поездки
                  </span>
                </div>
                <div ref={chartRef} className="w-full h-72" />
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-slate-500">
              Данные отеля не найдены.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

