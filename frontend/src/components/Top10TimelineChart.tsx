import React, { useEffect, useRef, useState } from "react";
import { getTop10Timeline } from "../services/api";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface Top10TimelineChartProps {
  destination?: string;
}

export const Top10TimelineChart: React.FC<Top10TimelineChartProps> = ({ destination }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const [dataPoints, setDataPoints] = useState<
    { date: string; avg_price: number; min_price: number; max_price: number }[]
  >([]);

  useEffect(() => {
    getTop10Timeline(destination)
      .then((pts) => {
        setDataPoints(pts);
      })
      .catch((err) => console.warn("Failed to load timeline:", err));
  }, [destination]);

  useEffect(() => {
    if (!chartRef.current || !window.Plotly || !dataPoints.length) return;

    const xVals = dataPoints.map((d) => d.date);
    const avgVals = dataPoints.map((d) => d.avg_price);
    const minVals = dataPoints.map((d) => d.min_price);
    const maxVals = dataPoints.map((d) => d.max_price);

    const hoverTexts = dataPoints.map(
      (d) =>
        `<b>Дата замера:</b> ${d.date}<br>` +
        `<b>Средняя цена ТОП-10:</b> ${Math.round(d.avg_price).toLocaleString("ru-RU")} PLN<br>` +
        `<b>Диапазон (№1 — №10):</b> ${Math.round(d.min_price).toLocaleString("ru-RU")} — ${Math.round(d.max_price).toLocaleString("ru-RU")} PLN`
    );

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
      margin: { t: 20, r: 25, b: 45, l: 65 },
      height: 290,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: {
        title: { text: "Время", font: { size: 11, color: "#64748b" } },
        gridcolor: "#f1f5f9",
        tickfont: { size: 10, color: "#64748b" },
      },
      yaxis: {
        title: { text: "Цена (PLN)", font: { size: 11, color: "#64748b" } },
        gridcolor: "#f1f5f9",
        tickfont: { size: 10, color: "#64748b" },
      },
    };

    const config = {
      responsive: true,
      displayModeBar: false,
    };

    window.Plotly.react(chartRef.current, [traceMin, traceMax, traceAvg], layout, config);
  }, [dataPoints]);

  return (
    <section className="bg-white rounded-2xl border border-slate-200/90 p-4 sm:p-5 shadow-sm space-y-2">
      <h3 className="text-base font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
        <span>📉</span>
        <span>Средняя цена ТОП-10 дешёвых предложений</span>
      </h3>
      <div ref={chartRef} id="avgTop10TimelineChart" className="w-full" style={{ height: "290px" }} />
    </section>
  );
};
