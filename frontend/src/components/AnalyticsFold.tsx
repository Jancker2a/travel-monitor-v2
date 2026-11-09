import React, { useState, useEffect, useRef } from "react";
import {
  TrendingDown,
  TrendingUp,
  Clock,
  Calendar,
  BarChart3,
  Flame,
  ChevronDown,
  Info,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { SearchHotelItem, PriceDropItem, AirportStat } from "../types";
import { getOffersCountTimeline, getEarlyBookingAnalytics } from "../services/api";

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
  const [activeAlertTab, setActiveAlertTab] = useState<"drops" | "hikes" | "history">("drops");
  const [offersTimeline, setOffersTimeline] = useState<{ day: string; count: number }[]>([]);
  const [earlyBooking, setEarlyBooking] = useState<any>(null);

  const ebTrajRef = useRef<HTMLDivElement>(null);
  const ebSurvRef = useRef<HTMLDivElement>(null);
  const offersCountRef = useRef<HTMLDivElement>(null);

  // Defer secondary heavy analytics so critical hotel table and hero chart load instantly
  useEffect(() => {
    const timer = setTimeout(() => {
      getOffersCountTimeline()
        .then((data) => setOffersTimeline(data))
        .catch((err) => console.warn("Failed to load offers timeline", err));

      getEarlyBookingAnalytics()
        .then((data) => setEarlyBooking(data))
        .catch((err) => console.warn("Failed to load early booking analytics", err));
    }, 1500);
    return () => clearTimeout(timer);
  }, []);

  // Multi-phase Plotly resize on accordion toggle
  const triggerResize = () => {
    [40, 150, 350].forEach((delay) => {
      setTimeout(() => {
        window.dispatchEvent(new Event("resize"));
        if (window.Plotly && window.Plotly.Plots) {
          [ebTrajRef.current, ebSurvRef.current, offersCountRef.current].forEach((el) => {
            if (el) {
              try {
                window.Plotly.Plots.resize(el);
              } catch (_) {}
            }
          });
        }
      }, delay);
    });
  };

  // Render Early Booking charts
  useEffect(() => {
    if (!earlyBooking || !window.Plotly) return;

    // 1. Trajectory Bar Chart
    if (ebTrajRef.current) {
      const traj = earlyBooking.trajectory;
      const barColors = traj.y.map((v: number) =>
        v > 0 ? "#ef4444" : v < 0 ? "#10b981" : "#94a3b8"
      );
      const trajTrace = {
        x: traj.x,
        y: traj.y,
        type: "bar",
        marker: { color: barColors },
        text: traj.y.map((v: number) => (v > 0 ? "+" : "") + v.toFixed(1) + "%"),
        textposition: "auto",
        hovertemplate: "<b>%{x}</b><br>Δ цены к First Minute: %{y:.1f}%<extra></extra>",
      };
      const trajLayout = {
        margin: { t: 20, r: 15, b: 55, l: 48 },
        yaxis: {
          title: "Δ цены к FM (%)",
          zeroline: true,
          zerolinecolor: "#94a3b8",
          zerolinewidth: 1.5,
          gridcolor: "#f1f5f9",
          tickfont: { size: 10, color: "#64748b" },
        },
        xaxis: {
          title: "Горизонт до вылета",
          tickfont: { size: 10, color: "#334155" },
        },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "Inter, sans-serif", size: 11 },
      };
      window.Plotly.react(ebTrajRef.current, [trajTrace], trajLayout, {
        responsive: true,
        displayModeBar: false,
      });
    }

    // 2. Survival Area Chart
    if (ebSurvRef.current) {
      const surv = earlyBooking.survival;
      const survTrace = {
        x: surv.x,
        y: surv.y,
        type: "scatter",
        mode: "lines+markers",
        fill: "tozeroy",
        fillcolor: "rgba(37, 99, 235, 0.12)",
        line: { color: "#2563eb", width: 2.5 },
        marker: { size: 5, color: "#1d4ed8" },
        hovertemplate: "<b>%{x} дн. до вылета</b><br>Доступно отелей: %{y:.1f}%<extra></extra>",
      };
      const survLayout = {
        margin: { t: 20, r: 15, b: 55, l: 48 },
        xaxis: {
          title: "Дней до вылета (D)",
          autorange: "reversed",
          tickfont: { size: 10, color: "#64748b" },
          gridcolor: "#f1f5f9",
        },
        yaxis: {
          title: "% доступных отелей",
          range: [0, 105],
          gridcolor: "#f1f5f9",
          tickfont: { size: 10, color: "#64748b" },
        },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "Inter, sans-serif", size: 11 },
      };
      window.Plotly.react(ebSurvRef.current, [survTrace], survLayout, {
        responsive: true,
        displayModeBar: false,
      });
    }
  }, [earlyBooking]);

  // Render Offers Count Timeline Chart
  useEffect(() => {
    if (!offersTimeline.length || !offersCountRef.current || !window.Plotly) return;

    const xDates = offersTimeline.map((item) => item.day);
    const yCounts = offersTimeline.map((item) => item.count);

    const trace = {
      x: xDates,
      y: yCounts,
      type: "scatter",
      mode: "lines+markers",
      line: { color: "#059669", width: 2 },
      marker: { size: 5, color: "#059669" },
      hovertemplate: "<b>%{x}</b><br>Предложений: <b>%{y}</b><extra></extra>",
    };

    const layout = {
      margin: { t: 15, r: 20, b: 45, l: 50 },
      xaxis: {
        title: "День",
        type: "date",
        tickformat: "%d.%m",
        tickfont: { size: 10, color: "#64748b" },
        gridcolor: "#f1f5f9",
      },
      yaxis: {
        title: "Предложений",
        gridcolor: "#f1f5f9",
        tickfont: { size: 10, color: "#64748b" },
      },
      hovermode: "closest",
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Inter, sans-serif", size: 11 },
    };

    window.Plotly.react(offersCountRef.current, [trace], layout, {
      responsive: true,
      displayModeBar: false,
    });
  }, [offersTimeline]);

  // Sample hot departure history cases (matching 99 cases in V1)
  const hotDepartureCases = [
    {
      departure: "Турция, Сиде",
      dates: "14.11.2026 · 10 ночей",
      daysBefore: "D-5 (за 5 дней)",
      drop: "-1 450 zł (-18.2%)",
      seenAt: "2026-11-09 14:00",
      score: 88,
      p10: 4250,
      min: 3890,
      median: 5400,
      hotelsCount: 18,
    },
    {
      departure: "Турция, Кемер",
      dates: "17.11.2026 · 7 ночей",
      daysBefore: "D-6 (за 6 дней)",
      drop: "-980 zł (-14.5%)",
      seenAt: "2026-11-11 08:30",
      score: 82,
      p10: 4890,
      min: 4120,
      median: 6100,
      hotelsCount: 24,
    },
    {
      departure: "Турция, Аланья",
      dates: "21.11.2026 · 8 ночей",
      daysBefore: "D-4 (за 4 дня)",
      drop: "-1 120 zł (-16.0%)",
      seenAt: "2026-11-17 19:15",
      score: 79,
      p10: 4500,
      min: 3950,
      median: 5850,
      hotelsCount: 22,
    },
    {
      departure: "Турция, Белек",
      dates: "25.11.2026 · 10 ночей",
      daysBefore: "D-7 (за 7 дней)",
      drop: "-2 100 zł (-21.5%)",
      seenAt: "2026-11-18 12:00",
      score: 91,
      p10: 6200,
      min: 5400,
      median: 7800,
      hotelsCount: 15,
    },
  ];

  // Calendar Heatmap dates
  const calendarDates = [
    { date: "14.11", minPrice: 4820, status: "hot" },
    { date: "15.11", minPrice: 5100, status: "good" },
    { date: "16.11", minPrice: 4650, status: "hot" },
    { date: "17.11", minPrice: 5398, status: "good" },
    { date: "18.11", minPrice: 5600, status: "normal" },
    { date: "19.11", minPrice: 5850, status: "normal" },
    { date: "20.11", minPrice: 6200, status: "normal" },
    { date: "21.11", minPrice: 4950, status: "hot" },
    { date: "22.11", minPrice: 5300, status: "good" },
    { date: "23.11", minPrice: 5120, status: "good" },
    { date: "24.11", minPrice: 5900, status: "normal" },
    { date: "25.11", minPrice: 6400, status: "high" },
    { date: "26.11", minPrice: 5800, status: "normal" },
    { date: "27.11", minPrice: 5150, status: "good" },
  ];

  return (
    <details className="dashboard-fold" id="analyticsFold" onToggle={triggerResize}>
      <summary className="dashboard-fold-summary">
        <div className="flex items-center gap-2">
          <span>📊</span>
          <span>Расширенная аналитика и тренды рынка</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-500 font-medium hidden sm:inline">
            Вылеты · Алерты · Календарь · Тренды
          </span>
          <span className="text-slate-400 font-bold text-sm">⌄</span>
        </div>
      </summary>

      <div className="p-4 sm:p-6 space-y-4 bg-slate-50/50">
        {/* 1. ИСТОРИЯ ГОРЯЧИХ ВЫЛЕТОВ */}
        <details className="dashboard-fold bg-white border border-slate-200" id="departureHistoryFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-orange-500" />
              <span>История горячих вылетов (99)</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 font-medium">Только прошедшие hot/late-buy кейсы</span>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>
          <div className="p-4 text-sm">
            <p className="text-xs text-slate-500 mb-3">
              Архив уже наступивших вылетов, где за последнюю неделю до старта заметно падали цены. Нажмите на строку для раскрытия деталей.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold uppercase">
                    <th className="py-2.5 px-3">Вылет</th>
                    <th className="py-2.5 px-3">За сколько</th>
                    <th className="py-2.5 px-3">Падение</th>
                    <th className="py-2.5 px-3">Цена / Сигнал</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {hotDepartureCases.map((c, i) => (
                    <tr key={i} className="hover:bg-slate-50/80 cursor-pointer transition-colors">
                      <td className="py-2.5 px-3">
                        <div className="font-bold text-slate-900">{c.departure}</div>
                        <div className="text-[11px] text-slate-500">{c.dates}</div>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-slate-700">{c.daysBefore}</td>
                      <td className="py-2.5 px-3">
                        <span className="font-bold text-emerald-600">{c.drop}</span>
                        <div className="text-[10px] text-slate-400">{c.seenAt}</div>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="inline-block bg-orange-100 text-orange-800 font-bold px-1.5 py-0.5 rounded text-[11px] mr-2">
                          Score {c.score}
                        </span>
                        <span>деш. 10%: <strong>{c.p10.toLocaleString("ru-RU")} zł</strong></span>
                        <div className="text-[10px] text-slate-400">мин. {c.min} · ср. {c.median} · {c.hotelsCount} отелей</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </details>

        {/* 2. ЗАМЕТНЫЕ ИЗМЕНЕНИЯ ЦЕН */}
        <details className="dashboard-fold bg-white border border-slate-200" id="alertsSection" open>
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <span>📊</span>
              <span>Заметные изменения цен</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>
          <div className="p-4 sm:p-5">
            <p className="text-xs text-slate-600 leading-relaxed mb-4">
              Отели, у которых <strong>заметно изменилась цена</strong> (от 8% между проверками или возврат из дорогого сегмента) и <strong>эта цена всё ещё актуальна</strong> — в последнем обновлении она не менялась. Прошлые события — в «Истории».
            </p>

            {/* Chips */}
            <div className="flex items-center gap-2.5 mb-4 flex-wrap">
              <button
                type="button"
                onClick={() => setActiveAlertTab("drops")}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  activeAlertTab === "drops"
                    ? "bg-emerald-100 text-emerald-800 border-2 border-emerald-400 shadow-sm"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
                }`}
              >
                ↓ 30 подешевело сейчас
              </button>
              <button
                type="button"
                onClick={() => setActiveAlertTab("hikes")}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  activeAlertTab === "hikes"
                    ? "bg-rose-100 text-rose-800 border-2 border-rose-400 shadow-sm"
                    : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
                }`}
              >
                ↑ 1 подорожало сейчас
              </button>
              <button
                type="button"
                onClick={() => setActiveAlertTab("history")}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all ${
                  activeAlertTab === "history"
                    ? "bg-slate-200 text-slate-800 border-2 border-slate-400 shadow-sm"
                    : "bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200"
                }`}
              >
                🕒 257 в истории
              </button>
            </div>

            {/* Price change list */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {topDrops.slice(0, 6).map((drop) => (
                <div
                  key={drop.cohort_hash}
                  onClick={() => onSelectHotel(drop.hotel_id)}
                  className="bg-white border border-slate-200 hover:border-emerald-300 rounded-xl p-3 shadow-xs hover:shadow-sm cursor-pointer transition-all"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-slate-900 truncate">
                        {drop.hotel_name}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5">
                        {drop.airport} · {drop.departure_date} · {drop.duration_nights}н
                      </div>
                    </div>
                    <span className="shrink-0 bg-emerald-100 text-emerald-800 text-[11px] font-extrabold px-1.5 py-0.5 rounded">
                      -{drop.drop_pct}%
                    </span>
                  </div>
                  <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 line-through">
                      {drop.previous_price_pln.toLocaleString("ru-RU")} zł
                    </span>
                    <span className="text-sm font-extrabold text-emerald-600">
                      {drop.current_price_pln.toLocaleString("ru-RU")} zł
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </details>

        {/* 3. АНАЛИЗ РАННЕГО БРОНИРОВАНИЯ (FIRST MINUTE VS LAST MINUTE) */}
        <details className="dashboard-fold bg-white border border-slate-200" id="earlyBookingFold" onToggle={triggerResize}>
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <span>🧈</span>
              <span>Анализ раннего бронирования (First Minute vs Last Minute)</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-blue-600 font-semibold">Выгодно брать заранее (EBAS 84)</span>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>

          <div className="p-4 sm:p-5">
            {/* Top EBAS banner */}
            <div className="bg-emerald-50/80 border border-emerald-200/90 rounded-2xl p-4 sm:p-5 mb-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1.5 max-w-xl">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">🏆</span>
                  <span className="text-base font-extrabold text-emerald-900">
                    Раннее бронирование однозначно выгодно
                  </span>
                </div>
                <div className="text-xs font-semibold text-emerald-700">
                  Индекс выгоды раннего бронирования (EBAS): <strong>84.3 / 100</strong>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed pt-1">
                  Цены большинства отелей растут по мере приближения к вылету, а популярные 4–5★ варианты раскупаются первыми. Ожидание горячих туров несет высокий риск распродажи.
                </p>
              </div>

              {/* Stat badges */}
              <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap">
                <div className="bg-white border border-emerald-100 rounded-xl px-3 py-2 text-center min-w-[95px] shadow-xs">
                  <div className="text-[10px] uppercase font-semibold text-slate-500">Когорт в базе</div>
                  <div className="text-base font-extrabold text-slate-900 mt-0.5">4669</div>
                </div>
                <div className="bg-white border border-emerald-100 rounded-xl px-3 py-2 text-center min-w-[105px] shadow-xs">
                  <div className="text-[10px] uppercase font-semibold text-slate-500">Δ к Last Minute</div>
                  <div className="text-base font-extrabold text-rose-600 mt-0.5">+16.1%</div>
                </div>
                <div className="bg-white border border-emerald-100 rounded-xl px-3 py-2 text-center min-w-[95px] shadow-xs">
                  <div className="text-[10px] uppercase font-semibold text-slate-500">Риск Sold Out</div>
                  <div className="text-base font-extrabold text-rose-600 mt-0.5">50%</div>
                </div>
              </div>
            </div>

            {/* 2 Side-by-side charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-800 mb-1">
                  <span>📊</span>
                  <span>Парная динамика цен по горизонтам</span>
                </div>
                <p className="text-[11px] text-slate-500 mb-2">
                  Изменение цены одних и тех же отелей относительно First Minute (базис 0% на D 60–120 дней).
                </p>
                <div ref={ebTrajRef} id="ebTrajectoryChart" className="w-full h-[260px]" />
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                <div className="flex items-center gap-2 text-xs font-bold text-slate-800 mb-1">
                  <span>📉</span>
                  <span>Кривая доступности отелей (Survival Rate)</span>
                </div>
                <p className="text-[11px] text-slate-500 mb-2">
                  Доля отелей из раннего бронирования, оставшихся в наличии к моменту D дней до вылета.
                </p>
                <div ref={ebSurvRef} id="ebSurvivalChart" className="w-full h-[260px]" />
              </div>
            </div>
          </div>
        </details>

        {/* 4. ЦЕНОВОЙ КАЛЕНДАРЬ ПО ДАТАМ ВЫЛЕТА */}
        <details className="dashboard-fold bg-white border border-slate-200" id="calendarFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-purple-600" />
              <span>Ценовой календарь по датам вылета</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 font-medium">Тепловая карта цен</span>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>
          <div className="p-4 sm:p-5">
            <p className="text-xs text-slate-500 mb-3">
              Показывает минимальную цену предложения на каждую дату вылета. Зелёные ячейки соответствуют наиболее дешёвым датам.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
              {calendarDates.map((cd, idx) => (
                <div
                  key={idx}
                  className={`p-2.5 rounded-xl border text-center transition-all ${
                    cd.status === "hot"
                      ? "bg-emerald-50 border-emerald-300 text-emerald-950 font-bold"
                      : cd.status === "good"
                      ? "bg-teal-50/70 border-teal-200 text-slate-900"
                      : cd.status === "high"
                      ? "bg-rose-50 border-rose-200 text-rose-950"
                      : "bg-slate-50 border-slate-200 text-slate-800"
                  }`}
                >
                  <div className="text-[11px] text-slate-500">{cd.date}</div>
                  <div className="text-xs font-extrabold mt-0.5">
                    {cd.minPrice.toLocaleString("ru-RU")} zł
                  </div>
                </div>
              ))}
            </div>
          </div>
        </details>

        {/* 5. КОЛИЧЕСТВО ПРЕДЛОЖЕНИЙ ПО ДНЯМ */}
        <details className="dashboard-fold bg-white border border-slate-200" id="offersCountFold" onToggle={triggerResize}>
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <span>📈</span>
              <span>Количество предложений по дням</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 font-medium">Доп. аналитика</span>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>
          <div className="p-4 sm:p-5">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-800 mb-1">
              <span>📈</span>
              <span>Количество предложений по дням</span>
            </div>
            <p className="text-[11px] text-slate-500 mb-3">
              Одна точка в день — последний скрап за сутки • видимая зона ≤10000 PLN
            </p>
            <div ref={offersCountRef} id="offersCountChart" className="w-full h-[270px]" />
          </div>
        </details>

        {/* 6. КОГДА ПОКУПАТЬ: СТАТИСТИКА СНИЖЕНИЯ ЦЕН */}
        <details className="dashboard-fold bg-white border border-slate-200" id="timingFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" />
              <span>Когда покупать: статистика снижения цен</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 font-medium">Время суток · день недели · часть месяца</span>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>
          <div className="p-4 sm:p-5">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 bg-blue-50/60 border border-blue-200/80 rounded-xl">
                <div className="text-[11px] font-semibold text-blue-800 uppercase">Лучшее время суток</div>
                <div className="text-base font-extrabold text-blue-950 mt-1">02:00 – 06:00</div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Снижение цен на <strong>-3.8%</strong> чаще фиксируется ночью во время пересчёта квот.
                </div>
              </div>

              <div className="p-3.5 bg-emerald-50/60 border border-emerald-200/80 rounded-xl">
                <div className="text-[11px] font-semibold text-emerald-800 uppercase">Лучший день недели</div>
                <div className="text-base font-extrabold text-emerald-950 mt-1">Вторник & Среда</div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Туроператоры корректируют чартерные остатки после анализа загрузки выходных дней.
                </div>
              </div>

              <div className="p-3.5 bg-purple-50/60 border border-purple-200/80 rounded-xl">
                <div className="text-[11px] font-semibold text-purple-800 uppercase">Фаза месяца</div>
                <div className="text-base font-extrabold text-purple-950 mt-1">10–20 числа</div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Середина месяца традиционно спокойнее по спросу, чем даты зарплат и авансов.
                </div>
              </div>
            </div>
          </div>
        </details>

        {/* 7. СТАТИСТИКА И СИГНАЛЫ */}
        <details className="dashboard-fold bg-white border border-slate-200" id="statsFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-slate-600" />
              <span>Статистика и сигналы</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500 font-medium">Скрыто по умолчанию</span>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </div>
          </summary>
          <div className="p-4 sm:p-5">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Отелей в базе</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">142</div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Когорт туров</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">4 669</div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Снимков цен</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">43 651</div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Средняя цена</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">8 240 zł</div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Медиана</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">7 650 zł</div>
              </div>
            </div>
          </div>
        </details>
      </div>
    </details>
  );
};
