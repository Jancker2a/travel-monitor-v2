import React, { useEffect, useRef, useState } from "react";
import { getFilterTop10Timeline } from "../services/api";
import { TimelinePoint, TimelineStats } from "../types";
import { TrendingDown, TrendingUp, Minus, Calendar, Filter } from "lucide-react";
import { LoadingSpinner } from "./common/LoadingSpinner";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface Top10TimelineChartProps {
  filterId?: string;
  destination?: string;
}

export const Top10TimelineChart: React.FC<Top10TimelineChartProps> = ({
  filterId,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [dataPoints, setDataPoints] = useState<TimelinePoint[]>([]);
  const [stats, setStats] = useState<TimelineStats | null>(null);
  const [range, setRange] = useState<string>("all");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!filterId) return;

    setIsLoading(true);
    getFilterTop10Timeline(filterId, range)
      .then((resp) => {
        setDataPoints(resp.timeline || []);
        if (resp.stats) {
          setStats(resp.stats);
        }
      })
      .catch((err) => {
        console.warn("Failed to load Top-10 timeline:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [filterId, range]);

  useEffect(() => {
    if (!chartRef.current || !dataPoints.length) return;
    if (!window.Plotly) {
      const timer = setTimeout(() => {
        // force re-trigger effect once Plotly script has parsed
        setDataPoints((prev) => [...prev]);
      }, 200);
      return () => clearTimeout(timer);
    }

    const xVals = dataPoints.map((d) => d.time);
    const avgVals = dataPoints.map((d) => d.avg_price);
    const minVals = dataPoints.map((d) => d.min_price);
    const maxVals = dataPoints.map((d) => d.max_price);

    const hoverTexts = dataPoints.map((d) => {
      let topOffersStr = "";
      if (d.top10_hotels && d.top10_hotels.length > 0) {
        const top3 = d.top10_hotels.slice(0, 3);
        topOffersStr =
          "<br><br><b>Лидеры по цене:</b><br>" +
          top3
            .map(
              (h) =>
                ` ${h.position}. ${h.name}: <b>${Math.round(
                  h.price
                ).toLocaleString("ru-RU")} zł</b>`
            )
            .join("<br>");
      }

      return (
        `<b>Дата замера:</b> ${d.time}<br>` +
        `<b>Средняя цена ТОП-10:</b> ${Math.round(
          d.avg_price
        ).toLocaleString("ru-RU")} PLN<br>` +
        `<b>Диапазон (№1 — №10):</b> ${Math.round(
          d.min_price
        ).toLocaleString("ru-RU")} — ${Math.round(
          d.max_price
        ).toLocaleString("ru-RU")} PLN` +
        topOffersStr
      );
    });

    // 1. Min trace (invisible base)
    const traceMin = {
      x: xVals,
      y: minVals,
      type: "scatter",
      mode: "lines",
      line: { width: 0 },
      showlegend: false,
      hoverinfo: "skip",
    };

    // 2. Max trace (fills down to min with plum tint)
    const traceMax = {
      x: xVals,
      y: maxVals,
      type: "scatter",
      mode: "lines",
      fill: "tonexty",
      fillcolor: "rgba(162, 59, 114, 0.14)",
      line: { width: 0 },
      name: "Диапазон ТОП-10 (мин - макс)",
      hoverinfo: "skip",
      showlegend: false,
    };

    // 3. Average line with markers
    const traceAvg = {
      x: xVals,
      y: avgVals,
      type: "scatter",
      mode: "lines+markers",
      line: { color: "#A23B72", width: 2.8 },
      marker: { size: 5, color: "#A23B72" },
      name: "Средняя цена ТОП-10",
      showlegend: false,
      text: hoverTexts,
      hovertemplate: "%{text}<extra></extra>",
      hoverlabel: {
        bgcolor: "rgba(255, 255, 255, 0.98)",
        bordercolor: "#A23B72",
        font: { family: "Inter, sans-serif", size: 12, color: "#0f172a" },
        align: "left",
      },
    };

    const layout = {
      showlegend: false,
      margin: { t: 20, r: 25, b: 45, l: 65 },
      height: 360,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: {
        title: { text: "Время", font: { size: 12, color: "#64748b" } },
        gridcolor: "#f1f5f9",
        tickfont: { size: 11, color: "#64748b" },
      },
      yaxis: {
        title: { text: "Цена (PLN)", font: { size: 12, color: "#64748b" } },
        gridcolor: "#f1f5f9",
        tickfont: { size: 11, color: "#64748b" },
      },
    };

    const config = {
      responsive: true,
      displayModeBar: false,
    };

    window.Plotly.react(
      chartRef.current,
      [traceMin, traceMax, traceAvg],
      layout,
      config
    );

    const handleResize = () => {
      if (chartRef.current && window.Plotly) {
        window.Plotly.Plots.resize(chartRef.current);
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [dataPoints]);

  return (
    <section className="bg-white rounded-2xl border border-slate-200/90 p-5 sm:p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <h3 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
            <span>📉</span>
            <span>Средняя цена ТОП-10 дешёвых предложений</span>
          </h3>
          {dataPoints.length > 0 && (
            <span className="text-xs font-bold text-slate-500 bg-slate-100 px-2.5 py-0.5 rounded-full">
              {dataPoints.length} snapshots
            </span>
          )}
        </div>

        {/* Range Buttons (7d / 30d / All) */}
        <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setRange("7d")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              range === "7d"
                ? "bg-white text-slate-900 shadow-2xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            7 дней
          </button>
          <button
            type="button"
            onClick={() => setRange("30d")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              range === "30d"
                ? "bg-white text-slate-900 shadow-2xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            30 дней
          </button>
          <button
            type="button"
            onClick={() => setRange("all")}
            className={`px-3 py-1.5 rounded-lg transition-all ${
              range === "all"
                ? "bg-white text-slate-900 shadow-2xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Всё время
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      {stats && (
        <div className="flex items-center gap-6 text-sm text-slate-600 bg-slate-50 border border-slate-200/80 rounded-xl px-4 py-2.5 flex-wrap">
          <div>
            Текущая ср. цена:{" "}
            <b className="text-slate-900 font-extrabold">
              {Math.round(stats.current_avg_top10).toLocaleString("ru-RU")} zł
            </b>
          </div>
          <div>
            Ист. минимум:{" "}
            <b className="text-emerald-700 font-extrabold">
              {Math.round(stats.historical_min_avg).toLocaleString("ru-RU")} zł
            </b>
          </div>
          <div>
            Ист. максимум:{" "}
            <b className="text-slate-700 font-extrabold">
              {Math.round(stats.historical_max_avg).toLocaleString("ru-RU")} zł
            </b>
          </div>
          {stats.change_24h_pct !== undefined && (
            <div className="flex items-center gap-1.5">
              <span>Динамика 24ч:</span>
              <span
                className={`font-bold inline-flex items-center gap-0.5 ${
                  stats.change_24h_pct < 0
                    ? "text-emerald-600"
                    : stats.change_24h_pct > 0
                    ? "text-rose-600"
                    : "text-slate-500"
                }`}
              >
                {stats.change_24h_pct < 0 ? (
                  <TrendingDown className="w-4 h-4" />
                ) : stats.change_24h_pct > 0 ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <Minus className="w-4 h-4" />
                )}
                {stats.change_24h_pct > 0 ? "+" : ""}
                {stats.change_24h_pct}%
              </span>
            </div>
          )}
        </div>
      )}

      {/* Chart Canvas or Skeleton */}
      {isLoading && dataPoints.length === 0 ? (
        <LoadingSpinner
          variant="skeleton-chart"
          label="Построение графика ТОП-10 дешёвых предложений..."
          description="Сбор и агрегация исторических котировок из базы данных"
        />
      ) : (
        <div className="relative w-full">
          {isLoading && (
            <LoadingSpinner
              variant="overlay"
              size="lg"
              label="Обновление диапазона..."
              description="Пересчитываем ценовой коридор ТОП-10"
            />
          )}
          <div
            ref={chartRef}
            id="avgTop10TimelineChart"
            className="w-full"
            style={{ height: "360px" }}
          />
        </div>
      )}
    </section>
  );
};
