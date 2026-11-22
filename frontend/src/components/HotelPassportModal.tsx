import React, { useEffect, useRef, useState } from "react";
import { X, TrendingDown, Star, Calendar, RefreshCw, Layers } from "lucide-react";
import { HotelPassport } from "../types";
import { getHotelPassport, getHotelNormalizedHistory } from "../services/api";

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
  const [normalizedData, setNormalizedData] = useState<any>(null);
  const [viewMode, setViewMode] = useState<"raw" | "normalized">("raw");
  const [isLoading, setIsLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hotelId) return;
    setIsLoading(true);
    setNormalizedData(null);
    setViewMode("raw");

    Promise.all([
      getHotelPassport(hotelId).catch(() => null),
      getHotelNormalizedHistory(hotelId).catch(() => null),
    ])
      .then(([passData, normData]) => {
        setPassport(passData);
        setNormalizedData(normData);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load hotel passport:", err);
        setIsLoading(false);
      });
  }, [hotelId]);

  // Render Plotly chart based on active view mode (raw vs normalized)
  useEffect(() => {
    if (!chartRef.current || !window.Plotly) return;

    let xValues: string[] = [];
    let yValues: number[] = [];
    let hoverTexts: string[] = [];
    let lineColor = "#2563eb";

    if (viewMode === "normalized" && normalizedData && normalizedData.history.length > 0) {
      xValues = normalizedData.history.map((p: any) => p.recorded_at);
      yValues = normalizedData.history.map((p: any) => p.normalized_price_1p_8n);
      hoverTexts = normalizedData.history.map(
        (p: any) =>
          `<b>${p.normalized_price_1p_8n.toLocaleString("ru-RU")} zł</b> (1 чел. / 8 ночей)<br>` +
          `🏨 Чистая ставка отеля: ${p.pure_hotel_night_rate} zł / ночь<br>` +
          `✈️ Оценка перелёта: ${p.flight_estimate_seat} zł<br>` +
          `📌 Источник: ${p.source_type === "crawler_1p_8n" ? "🟢 Прямой замер (1p/8n)" : "🔵 Ре-нормализация v1"}`
      );
      lineColor = "#059669";
    } else if (passport && passport.history_points.length > 0) {
      xValues = passport.history_points.map((p) => p.recorded_at);
      yValues = passport.history_points.map((p) => p.total_price_pln);
      hoverTexts = passport.history_points.map(
        (p) =>
          `<b>${p.total_price_pln.toLocaleString("ru-RU")} zł</b><br>` +
          `📅 Даты поездки: ${p.departure_date} (${p.duration_nights} ночей)<br>` +
          `🛫 Аэропорт: ${p.airport}<br>` +
          `💵 За ночь/чел: ${p.price_per_night_per_pax.toFixed(0)} zł`
      );
      lineColor = "#2563eb";
    }

    if (xValues.length === 0) return;

    const trace = {
      x: xValues,
      y: yValues,
      text: hoverTexts,
      hoverinfo: "text",
      mode: "lines+markers",
      type: "scatter",
      line: { color: lineColor, width: 2.5, shape: "spline" },
      marker: {
        color: lineColor,
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
        type: "date",
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

    try {
      window.Plotly.react(chartRef.current, [trace], layout, config);
    } catch (e) {
      console.warn("Plotly modal chart error:", e);
    }

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
  }, [passport, normalizedData, viewMode]);

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
              {/* View Mode Switcher Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-3 mb-5 p-2 bg-slate-100/80 rounded-2xl border border-slate-200">
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setViewMode("raw")}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all ${
                      viewMode === "raw"
                        ? "bg-blue-600 text-white shadow-sm"
                        : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"
                    }`}
                  >
                    📊 Замеры конкретного тура (2+1 / точный состав)
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("normalized")}
                    className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 ${
                      viewMode === "normalized"
                        ? "bg-emerald-600 text-white shadow-sm"
                        : "bg-white text-slate-600 hover:bg-slate-50 border border-slate-200"
                    }`}
                  >
                    <Layers className="w-3.5 h-3.5" />
                    <span>🏷️ Нормализованный индекс (1 чел. • 8 ночей)</span>
                    <span className="text-[9px] bg-emerald-100 text-emerald-800 font-extrabold px-1.5 py-0.2 rounded-full">
                      ЭТАЛОН
                    </span>
                  </button>
                </div>

                <div className="text-[11px] text-slate-500 font-medium px-2">
                  {viewMode === "raw" ? (
                    <span>Прямые замеры цены выбранного состава и дат</span>
                  ) : (
                    <span>Исключает искажения разницы дат и состава гостей</span>
                  )}
                </div>
              </div>

              {/* Mode Explanation Banner (when Normalized) */}
              {viewMode === "normalized" && (
                <div className="mb-5 p-3 rounded-2xl bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-900 flex items-start gap-2.5">
                  <span className="text-base">💡</span>
                  <div>
                    <span className="font-bold">Эталонный индекс отеля: 1 взрослый, 8 ночей.</span>
                    <p className="text-[11px] text-emerald-800/90 mt-0.5 leading-relaxed">
                      Вычисляется из чистой посуточной ставки отеля ($H$) + фиксированного чартерного перелёта ($F$).
                      Позволяет честно сравнивать отель с другими гостиницами и оценивать реальный тренд без влияния сезонных смен дат вылета.
                    </p>
                  </div>
                </div>
              )}

              {/* Stat Cards Row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
                <div className="bg-emerald-50 border border-emerald-100 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-emerald-700 uppercase">
                    {viewMode === "normalized" ? "Мин. эталон (1p/8n)" : "Исторический минимум"}
                  </div>
                  <div className="text-xl font-extrabold text-emerald-900 mt-0.5">
                    {viewMode === "normalized" && normalizedData
                      ? `${normalizedData.stats.min_normalized_pln.toLocaleString("ru-RU")} zł`
                      : (passport.all_time_min_pln ? `${passport.all_time_min_pln.toLocaleString("ru-RU")} zł` : "—")}
                  </div>
                </div>

                <div className="bg-blue-50 border border-blue-100 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-blue-700 uppercase">
                    {viewMode === "normalized" ? "Медиана эталона" : "Медианная цена"}
                  </div>
                  <div className="text-xl font-extrabold text-blue-900 mt-0.5">
                    {viewMode === "normalized" && normalizedData
                      ? `${normalizedData.stats.median_normalized_pln.toLocaleString("ru-RU")} zł`
                      : (passport.typical_median_pln ? `${passport.typical_median_pln.toLocaleString("ru-RU")} zł` : "—")}
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-slate-600 uppercase">
                    {viewMode === "normalized" ? "Макс. эталон" : "Максимум сезона"}
                  </div>
                  <div className="text-xl font-extrabold text-slate-800 mt-0.5">
                    {viewMode === "normalized" && normalizedData
                      ? `${normalizedData.stats.max_normalized_pln.toLocaleString("ru-RU")} zł`
                      : (passport.all_time_max_pln ? `${passport.all_time_max_pln.toLocaleString("ru-RU")} zł` : "—")}
                  </div>
                </div>

                <div className="bg-slate-50 border border-slate-200 p-3.5 rounded-2xl">
                  <div className="text-[11px] font-semibold text-slate-600 uppercase">Всего замеров</div>
                  <div className="text-xl font-extrabold text-slate-800 mt-0.5">
                    {viewMode === "normalized" && normalizedData
                      ? `${normalizedData.stats.total_snapshots} точек`
                      : `${passport.history_points.length} точек`}
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

