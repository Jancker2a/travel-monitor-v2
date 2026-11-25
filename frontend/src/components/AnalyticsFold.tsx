import React, { useState, useEffect, useRef } from "react";
import {
  Clock,
  Calendar,
  BarChart3,
  Flame,
} from "lucide-react";
import {
  SearchHotelItem,
  PriceDropItem,
  AirportStat,
  FilterDeparturesData,
  FilterAnalyticsData,
  FilterPriceMoveItem,
  FilterType,
} from "../types";
import {
  getOffersCountTimeline,
  getEarlyBookingAnalytics,
  getFilterDepartures,
  getFilterAnalytics,
} from "../services/api";
import { LoadingSpinner } from "./common/LoadingSpinner";

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
  filterId?: string;
  filterType?: FilterType;
  onFilterByDeparture?: (departureDate: string) => void;
}

export const AnalyticsFold: React.FC<AnalyticsFoldProps> = ({
  hotels,
  topDrops,
  onSelectHotel,
  filterId,
  filterType = "rolling",
  onFilterByDeparture,
}) => {
  const [activeAlertTab, setActiveAlertTab] = useState<"drops" | "hikes" | "history">("drops");
  const [offersTimeline, setOffersTimeline] = useState<{ day: string; count: number }[]>([]);
  const [earlyBooking, setEarlyBooking] = useState<any>(null);
  const [departuresData, setDeparturesData] = useState<FilterDeparturesData | null>(null);
  const [filterAnalytics, setFilterAnalytics] = useState<FilterAnalyticsData | null>(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  const ebTrajRef = useRef<HTMLDivElement>(null);
  const ebSurvRef = useRef<HTMLDivElement>(null);
  const offersCountRef = useRef<HTMLDivElement>(null);

  const resolvedType: FilterType = filterAnalytics?.filter_type || filterType;

  // Fetch filter-specific DB analytics, departures, EB metrics & offers timeline
  useEffect(() => {
    let isCancelled = false;

    const timer = setTimeout(() => {
      getOffersCountTimeline()
        .then((data) => {
          if (!isCancelled) setOffersTimeline(data);
        })
        .catch((err) => console.warn("Failed to load offers timeline", err));

      getEarlyBookingAnalytics(filterId)
        .then((data) => {
          if (!isCancelled) setEarlyBooking(data);
        })
        .catch((err) => console.warn("Failed to load early booking analytics", err));
    }, 600);

    if (!filterId) {
      setDeparturesData(null);
      setFilterAnalytics(null);
      return () => {
        isCancelled = true;
        clearTimeout(timer);
      };
    }

    setLoadingAnalytics(true);
    setDeparturesData(null);
    setFilterAnalytics(null);

    Promise.allSettled([
      getFilterDepartures(filterId),
      getFilterAnalytics(filterId),
    ])
      .then(([depRes, anRes]) => {
        if (isCancelled) return;
        if (depRes.status === "fulfilled") setDeparturesData(depRes.value);
        if (anRes.status === "fulfilled") setFilterAnalytics(anRes.value);
      })
      .finally(() => {
        if (!isCancelled) setLoadingAnalytics(false);
      });

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, [filterId]);

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

  // Render Early Booking Plotly charts using real DB trajectory & survival arrays
  useEffect(() => {
    if (!earlyBooking || !earlyBooking.has_data || !window.Plotly) return;

    if (ebTrajRef.current && earlyBooking.trajectory?.x?.length) {
      const traj = earlyBooking.trajectory;
      const barColors = traj.y.map((v: number) =>
        v > 0 ? "#ef4444" : v < 0 ? "#10b981" : "#94a3b8"
      );
      window.Plotly.react(
        ebTrajRef.current,
        [
          {
            x: traj.x,
            y: traj.y,
            type: "bar",
            marker: { color: barColors },
            text: traj.y.map((v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`),
            textposition: "auto",
            hovertemplate: "<b>%{x}</b><br>Δ к стартовому горизонту: %{y:.1f}%<extra></extra>",
          },
        ],
        {
          margin: { t: 20, r: 15, b: 55, l: 48 },
          yaxis: {
            title: "Δ цены (%)",
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
        },
        { responsive: true, displayModeBar: false }
      );
    }

    if (ebSurvRef.current && earlyBooking.survival?.x?.length) {
      const surv = earlyBooking.survival;
      window.Plotly.react(
        ebSurvRef.current,
        [
          {
            x: surv.x,
            y: surv.y,
            type: "scatter",
            mode: "lines+markers",
            fill: "tozeroy",
            fillcolor: "rgba(37, 99, 235, 0.12)",
            line: { color: "#2563eb", width: 2.5 },
            marker: { size: 5, color: "#1d4ed8" },
            hovertemplate: "<b>%{x} дн. до вылета</b><br>Сохранилось когорт: %{y:.1f}%<extra></extra>",
          },
        ],
        {
          margin: { t: 20, r: 15, b: 55, l: 48 },
          xaxis: {
            title: "Дней до вылета (D)",
            autorange: "reversed",
            tickfont: { size: 10, color: "#64748b" },
            gridcolor: "#f1f5f9",
          },
          yaxis: {
            title: "% когорт в наличии",
            range: [0, 105],
            gridcolor: "#f1f5f9",
            tickfont: { size: 10, color: "#64748b" },
          },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { family: "Inter, sans-serif", size: 11 },
        },
        { responsive: true, displayModeBar: false }
      );
    }
  }, [earlyBooking]);

  // Render Offers Count Timeline Chart
  useEffect(() => {
    if (!offersTimeline.length || !offersCountRef.current || !window.Plotly) return;

    window.Plotly.react(
      offersCountRef.current,
      [
        {
          x: offersTimeline.map((item) => item.day),
          y: offersTimeline.map((item) => item.count),
          type: "scatter",
          mode: "lines+markers",
          line: { color: "#059669", width: 2 },
          marker: { size: 5, color: "#059669" },
          hovertemplate: "<b>%{x}</b><br>Когорт в замере: <b>%{y}</b><extra></extra>",
        },
      ],
      {
        margin: { t: 15, r: 20, b: 45, l: 50 },
        xaxis: {
          title: "День",
          type: "date",
          tickformat: "%d.%m",
          tickfont: { size: 10, color: "#64748b" },
          gridcolor: "#f1f5f9",
        },
        yaxis: {
          title: "Когорт",
          gridcolor: "#f1f5f9",
          tickfont: { size: 10, color: "#64748b" },
        },
        hovermode: "closest",
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "Inter, sans-serif", size: 11 },
      },
      { responsive: true, displayModeBar: false }
    );
  }, [offersTimeline]);

  // Real price moves for the current filter (fallback to global drops only in standalone search mode)
  const dropsList: FilterPriceMoveItem[] =
    filterAnalytics?.price_changes?.drops ||
    (!filterId
      ? topDrops.map((d) => ({
          hotel_id: d.hotel_id,
          hotel_name: d.hotel_name,
          prev_price: d.previous_price_pln,
          curr_price: d.current_price_pln,
          delta_pln: -Math.abs(d.drop_amount_pln),
          delta_pct: -Math.abs(d.drop_pct),
          airport_code: d.airport,
          checkin_date: d.departure_date,
          recorded_at: "",
        }))
      : []);
  const hikesList: FilterPriceMoveItem[] = filterAnalytics?.price_changes?.hikes || [];
  const historyList: FilterPriceMoveItem[] = filterAnalytics?.price_changes?.history || dropsList;

  const visibleMoves =
    activeAlertTab === "drops"
      ? dropsList
      : activeAlertTab === "hikes"
      ? hikesList
      : historyList;

  const calendarDates = filterAnalytics?.calendar_dates || [];
  const calMinAll = calendarDates.length
    ? Math.min(...calendarDates.map((d) => d.min_price))
    : 0;
  const calMedianAll = calendarDates.length
    ? [...calendarDates.map((d) => d.min_price)].sort((a, b) => a - b)[
        Math.floor(calendarDates.length / 2)
      ]
    : 0;

  const overview = filterAnalytics?.overview;
  const timingStats = filterAnalytics?.timing_stats;
  const bestWeekday = timingStats?.by_weekday?.length
    ? [...timingStats.by_weekday].sort((a, b) => b.drops - a.drops)[0]
    : null;

  const ebSummary = earlyBooking?.summary;
  const showEbSection =
    resolvedType !== "lastminute" && (Boolean(earlyBooking?.has_data) || resolvedType === "early_booking");

  const activeDepartures = departuresData?.active_departures || [];
  const hotHistory = departuresData?.hot_history || [];

  return (
    <details className="dashboard-fold" id="analyticsFold" onToggle={triggerResize}>
      <summary className="dashboard-fold-summary">
        <div className="flex items-center gap-2">
          <span>📊</span>
          <span>Расширенная аналитика и тренды рынка</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-500 font-medium hidden sm:inline">
            {resolvedType === "lastminute"
              ? "Вылеты 0–4д · История сбросов · Движения цен"
              : resolvedType === "early_booking"
              ? "Движения цен · Раннее бронирование (EBAS) · Тайминг"
              : "Вылеты · Движения цен · Календарь · Тайминг"}
          </span>
          <span className="text-slate-400 font-bold text-sm">⌄</span>
        </div>
      </summary>

      <div className="p-4 sm:p-6 space-y-4 bg-slate-50/50">
        {/* 0. ТЕКУЩИЕ И БЛИЖАЙШИЕ ВЫЛЕТЫ (Live DB Radar) */}
        {activeDepartures.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-5 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg">🛫</span>
                  <h3 className="text-base font-bold text-slate-900 tracking-tight">
                    Ближайшие вылеты фильтра (Live БД)
                  </h3>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Реальные даты вылета в текущем срезе (последние 48ч). Нажмите на карточку для фильтрации таблицы.
                </p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-semibold px-2.5 py-1 bg-slate-100 text-slate-700 rounded-lg">
                  {activeDepartures.length} дат вылета
                </span>
                {(departuresData?.stats?.hot_window_dates_count ?? 0) > 0 && (
                  <span className="text-xs font-semibold px-2.5 py-1 bg-red-100 text-red-700 rounded-lg flex items-center gap-1">
                    🔥 {departuresData?.stats?.hot_window_dates_count} в окне 0–4 дн.
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {activeDepartures.slice(0, 12).map((dep, idx) => {
                const depDate = dep.date || dep.departure_date || "";
                const daysLeft = dep.days_to_dep ?? dep.days_to_departure ?? 0;
                const hCount = dep.hotels_count ?? dep.hotel_count ?? 0;
                const isHot = Boolean(dep.is_hot_window || dep.status_cls === "hot");
                return (
                  <div
                    key={depDate || idx}
                    onClick={() => onFilterByDeparture?.(depDate)}
                    className={`p-3.5 rounded-xl border transition-all cursor-pointer hover:shadow-md ${
                      isHot
                        ? "bg-amber-50/70 border-amber-300 hover:border-amber-500"
                        : "bg-white border-slate-200 hover:border-blue-300 hover:bg-blue-50/20"
                    }`}
                    role="button"
                    tabIndex={0}
                    title="Нажмите, чтобы отфильтровать отели по этой дате"
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span className="font-bold text-slate-900 text-sm">
                        {isHot ? "⚡" : "📅"} {depDate}
                      </span>
                      <span
                        className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border ${
                          isHot
                            ? "bg-amber-100 text-amber-900 border-amber-300"
                            : "bg-slate-100 text-slate-700 border-slate-200"
                        }`}
                      >
                        {daysLeft === 0 ? "Сегодня" : `через ${daysLeft} дн.`}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-600 mb-2">
                      {hCount} отелей {dep.airports?.length ? `· ${dep.airports.join(", ")}` : ""}
                    </div>
                    <div className="flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-100 text-slate-500">
                      <span>
                        мин: <strong className="text-emerald-700">{dep.min_price.toLocaleString("ru-RU")} zł</strong>
                      </span>
                      <span>
                        мед: <strong className="text-slate-800">{dep.median_price.toLocaleString("ru-RU")} zł</strong>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* 1. ИСТОРИЯ ГОРЯЧИХ СБРОСОВ ПО ЭТОМУ НАПРАВЛЕНИЮ (Live DB) */}
        {hotHistory.length > 0 && (
          <details className="dashboard-fold bg-white border border-slate-200" id="departureHistoryFold">
            <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-orange-500" />
                <span>Реальные снижения цен в этом направлении ({hotHistory.length})</span>
              </div>
              <span className="text-slate-400 font-bold text-sm">⌄</span>
            </summary>
            <div className="p-4 text-sm">
              <p className="text-xs text-slate-500 mb-3">
                Зафиксированные в БД отели с падением от −10% относительно средней цены по аналогичному составу туристов.
              </p>
              <div className="overflow-x-auto max-h-[380px] overflow-y-auto scrollbar-thin">
                <table className="w-full text-left border-collapse text-xs">
                  <thead className="sticky top-0 z-10">
                    <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold uppercase">
                      <th className="py-2.5 px-3">Отель</th>
                      <th className="py-2.5 px-3">Дата вылета</th>
                      <th className="py-2.5 px-3">Мин. / Средняя</th>
                      <th className="py-2.5 px-3">Сброс</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {hotHistory.map((c, i) => (
                      <tr key={i} className="hover:bg-slate-50/80">
                        <td className="py-2.5 px-3 font-bold text-slate-900">
                          {c.hotel_name || c.departure}
                        </td>
                        <td className="py-2.5 px-3 text-slate-700">{c.checkin_date || c.dates}</td>
                        <td className="py-2.5 px-3">
                          <strong className="text-emerald-700">
                            {(c.min_price_pln ?? c.min ?? 0).toLocaleString("ru-RU")} zł
                          </strong>{" "}
                          <span className="text-slate-400">
                            (ср. {(c.avg_price_pln ?? c.median ?? 0).toLocaleString("ru-RU")} zł)
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-bold text-emerald-600">
                          {typeof c.drop_pct === "number" ? `${c.drop_pct.toFixed(1)}%` : c.drop}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        )}

        {/* 2. ЗАМЕТНЫЕ ИЗМЕНЕНИЯ ЦЕН (Live DB за 24–72ч) */}
        <details className="dashboard-fold bg-white border border-slate-200" id="alertsSection" open>
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <span>📊</span>
              <span>Заметные изменения цен (24–72ч)</span>
            </div>
            <span className="text-slate-400 font-bold text-sm">⌄</span>
          </summary>
          <div className="p-4 sm:p-5">
            <div className="flex items-center gap-2.5 mb-4 flex-wrap">
              <button
                type="button"
                onClick={() => setActiveAlertTab("drops")}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  activeAlertTab === "drops"
                    ? "bg-emerald-100 text-emerald-800 border-2 border-emerald-400 shadow-sm"
                    : "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
                }`}
              >
                ↓ {dropsList.length} подешевело
              </button>
              <button
                type="button"
                onClick={() => setActiveAlertTab("hikes")}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  activeAlertTab === "hikes"
                    ? "bg-rose-100 text-rose-800 border-2 border-rose-400 shadow-sm"
                    : "bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100"
                }`}
              >
                ↑ {hikesList.length} подорожало
              </button>
              <button
                type="button"
                onClick={() => setActiveAlertTab("history")}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  activeAlertTab === "history"
                    ? "bg-slate-200 text-slate-800 border-2 border-slate-400 shadow-sm"
                    : "bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200"
                }`}
              >
                🕒 {historyList.length} заметных движений
              </button>
            </div>

            {loadingAnalytics && !filterAnalytics ? (
              <LoadingSpinner variant="card" size="sm" label="Загрузка изменений цен из БД..." />
            ) : visibleMoves.length === 0 ? (
              <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-xl p-4 text-center">
                За последние 24–72 часа заметных скачков (≥ 40 zł) в этой категории не зафиксировано.
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {visibleMoves.slice(0, 9).map((m, idx) => {
                  const isDrop = m.delta_pln < 0;
                  return (
                    <div
                      key={`${m.hotel_id}-${idx}`}
                      onClick={() => onSelectHotel(m.hotel_id)}
                      className={`bg-white border rounded-xl p-3 shadow-xs hover:shadow-sm cursor-pointer transition-all ${
                        isDrop
                          ? "border-slate-200 hover:border-emerald-300"
                          : "border-slate-200 hover:border-rose-300"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-xs font-bold text-slate-900 truncate">
                            {m.hotel_name}
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            {m.airport_code || "WAW"} {m.checkin_date ? `· ${m.checkin_date}` : ""}
                          </div>
                        </div>
                        <span
                          className={`shrink-0 text-[11px] font-extrabold px-1.5 py-0.5 rounded ${
                            isDrop ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {m.delta_pct > 0 ? `+${m.delta_pct}%` : `${m.delta_pct}%`}
                        </span>
                      </div>
                      <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[11px] text-slate-400 line-through">
                          {m.prev_price.toLocaleString("ru-RU")} zł
                        </span>
                        <span className={`text-sm font-extrabold ${isDrop ? "text-emerald-600" : "text-rose-600"}`}>
                          {m.curr_price.toLocaleString("ru-RU")} zł
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </details>

        {/* 3. РАННЕЕ БРОНИРОВАНИЕ (Real EBAS & Survival, hidden if insufficient or lastminute) */}
        {showEbSection && (
          <details className="dashboard-fold bg-white border border-slate-200" id="earlyBookingFold" onToggle={triggerResize}>
            <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
              <div className="flex items-center gap-2">
                <span>🏷️</span>
                <span>Анализ раннего бронирования (First Minute vs Last Minute)</span>
              </div>
              <div className="flex items-center gap-3">
                {ebSummary && (
                  <span className="text-xs text-blue-600 font-semibold">
                    EBAS {Math.round(ebSummary.ebas_score)} / 100
                  </span>
                )}
                <span className="text-slate-400 font-bold text-sm">⌄</span>
              </div>
            </summary>

            <div className="p-4 sm:p-5">
              {!earlyBooking ? (
                <LoadingSpinner variant="card" size="md" label="Расчёт EBAS по когортам БД..." />
              ) : !earlyBooking.has_data ? (
                <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-xl p-4">
                  {ebSummary?.description || "Недостаточно длинной истории горизонтов по этому фильтру для построения кривой EBAS."}
                </div>
              ) : (
                <>
                  <div className="bg-emerald-50/80 border border-emerald-200/90 rounded-2xl p-4 sm:p-5 mb-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1.5 max-w-xl">
                      <div className="text-base font-extrabold text-emerald-900">
                        {ebSummary?.title}
                      </div>
                      <div className="text-xs font-semibold text-emerald-700">
                        Индекс EBAS (по данным БД): <strong>{ebSummary?.ebas_score} / 100</strong>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed pt-1">
                        {ebSummary?.description}
                      </p>
                    </div>

                    <div className="flex items-center gap-2.5 sm:gap-3 flex-wrap">
                      <div className="bg-white border border-emerald-100 rounded-xl px-3 py-2 text-center min-w-[95px] shadow-xs">
                        <div className="text-[10px] uppercase font-semibold text-slate-500">Когорт в выборке</div>
                        <div className="text-base font-extrabold text-slate-900 mt-0.5">
                          {(ebSummary?.total_cohorts ?? 0).toLocaleString("ru-RU")}
                        </div>
                      </div>
                      <div className="bg-white border border-emerald-100 rounded-xl px-3 py-2 text-center min-w-[105px] shadow-xs">
                        <div className="text-[10px] uppercase font-semibold text-slate-500">Δ к Last Minute</div>
                        <div className="text-base font-extrabold text-slate-900 mt-0.5">
                          {(ebSummary?.lm_delta_pct ?? 0) > 0 ? "+" : ""}
                          {ebSummary?.lm_delta_pct ?? 0}%
                        </div>
                      </div>
                      <div className="bg-white border border-emerald-100 rounded-xl px-3 py-2 text-center min-w-[95px] shadow-xs">
                        <div className="text-[10px] uppercase font-semibold text-slate-500">Исчезло до 14д</div>
                        <div className="text-base font-extrabold text-rose-600 mt-0.5">
                          {ebSummary?.sold_out_risk_pct ?? 0}%
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                      <div className="text-xs font-bold text-slate-800 mb-2">📊 Траектория цен по горизонтам</div>
                      <div ref={ebTrajRef} id="ebTrajectoryChart" className="w-full h-[260px]" />
                    </div>
                    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs">
                      <div className="text-xs font-bold text-slate-800 mb-2">📉 Выживаемость когорт до вылета</div>
                      <div ref={ebSurvRef} id="ebSurvivalChart" className="w-full h-[260px]" />
                    </div>
                  </div>
                </>
              )}
            </div>
          </details>
        )}

        {/* 4. ЦЕНОВОЙ КАЛЕНДАРЬ ПО ДАТАМ ВЫЛЕТА (Live DB) */}
        <details className="dashboard-fold bg-white border border-slate-200" id="calendarFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-purple-600" />
              <span>Ценовой календарь по датам вылета ({calendarDates.length})</span>
            </div>
            <span className="text-slate-400 font-bold text-sm">⌄</span>
          </summary>
          <div className="p-4 sm:p-5">
            {calendarDates.length === 0 ? (
              <div className="text-xs text-slate-500">Нет активных дат вылета в текущем срезе фильтра.</div>
            ) : (
              <>
                <p className="text-xs text-slate-500 mb-3">
                  Минимальная цена в текущем 24ч срезе на каждую дату вылета. Клик по ячейке фильтрует таблицу.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">
                  {calendarDates.slice(0, 28).map((cd) => {
                    const isCheapest = cd.min_price <= calMinAll * 1.05;
                    const isExpensive = calMedianAll > 0 && cd.min_price >= calMedianAll * 1.12;
                    return (
                      <button
                        key={cd.date}
                        type="button"
                        onClick={() => onFilterByDeparture?.(cd.date)}
                        className={`p-2.5 rounded-xl border text-center transition-all cursor-pointer hover:shadow-sm ${
                          isCheapest
                            ? "bg-emerald-50 border-emerald-300 text-emerald-950 font-bold"
                            : isExpensive
                            ? "bg-rose-50 border-rose-200 text-rose-950"
                            : "bg-slate-50 border-slate-200 text-slate-800 hover:border-blue-300"
                        }`}
                      >
                        <div className="text-[11px] text-slate-500">
                          {cd.date.slice(5).split("-").reverse().join(".")} · {cd.hotels_count} от.
                        </div>
                        <div className="text-xs font-extrabold mt-0.5">
                          {cd.min_price.toLocaleString("ru-RU")} zł
                        </div>
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </details>

        {/* 5. КОЛИЧЕСТВО ПРЕДЛОЖЕНИЙ ПО ДНЯМ */}
        <details className="dashboard-fold bg-white border border-slate-200" id="offersCountFold" onToggle={triggerResize}>
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <span>📈</span>
              <span>Глубина мониторинга по дням (60 дн.)</span>
            </div>
            <span className="text-slate-400 font-bold text-sm">⌄</span>
          </summary>
          <div className="p-4 sm:p-5">
            {offersTimeline.length === 0 ? (
              <LoadingSpinner variant="card" size="sm" label="Загрузка динамики когорт..." />
            ) : (
              <div ref={offersCountRef} id="offersCountChart" className="w-full h-[270px]" />
            )}
          </div>
        </details>

        {/* 6. КОГДА ПОКУПАТЬ: РЕАЛЬНАЯ СТАТИСТИКА СНИЖЕНИЙ В БД */}
        <details className="dashboard-fold bg-white border border-slate-200" id="timingFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-600" />
              <span>Когда фиксируются снижения цен (Live БД)</span>
            </div>
            <span className="text-slate-400 font-bold text-sm">⌄</span>
          </summary>
          <div className="p-4 sm:p-5">
            {!timingStats || timingStats.total_drops_analyzed === 0 ? (
              <div className="text-xs text-slate-500">
                Пока недостаточно зафиксированных снижений по этому фильтру (последние 30 дней).
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3.5 bg-blue-50/60 border border-blue-200/80 rounded-xl">
                  <div className="text-[11px] font-semibold text-blue-800 uppercase">Окно частых сбросов (UTC)</div>
                  <div className="text-base font-extrabold text-blue-950 mt-1">{timingStats.best_window}</div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {timingStats.best_window_share_pct}% от всех снижений (ср. шаг {timingStats.avg_drop_pct ?? 0}%).
                  </div>
                </div>
                <div className="p-3.5 bg-emerald-50/60 border border-emerald-200/80 rounded-xl">
                  <div className="text-[11px] font-semibold text-emerald-800 uppercase">Лидер по дню недели</div>
                  <div className="text-base font-extrabold text-emerald-950 mt-1">
                    {bestWeekday ? `${bestWeekday.day} (${bestWeekday.drops} сбросов)` : "—"}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    Реальная статистика по {timingStats.total_drops_analyzed} снижениям за 30 дней.
                  </div>
                </div>
                <div className="p-3.5 bg-purple-50/60 border border-purple-200/80 rounded-xl">
                  <div className="text-[11px] font-semibold text-purple-800 uppercase">Уход отелей (Sold-Out 7д)</div>
                  <div className="text-base font-extrabold text-purple-950 mt-1">
                    {overview?.sold_out_7d_lost_count ?? 0} отелей
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    Пропали из выдачи за последние 48ч (из замеченных за 7 дней).
                  </div>
                </div>
              </div>
            )}
          </div>
        </details>

        {/* 7. СТАТИСТИКА ФИЛЬТРА (Live БД) */}
        <details className="dashboard-fold bg-white border border-slate-200" id="statsFold">
          <summary className="dashboard-fold-summary bg-white hover:bg-slate-50">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-slate-600" />
              <span>Статистика текущего фильтра</span>
            </div>
            <span className="text-slate-400 font-bold text-sm">⌄</span>
          </summary>
          <div className="p-4 sm:p-5">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Активных отелей</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                  {(overview?.total_hotels ?? hotels.length).toLocaleString("ru-RU")}
                </div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Когорт фильтра</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                  {(overview?.total_cohorts ?? 0).toLocaleString("ru-RU")}
                </div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Снимков цен</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                  {(overview?.total_snapshots ?? 0).toLocaleString("ru-RU")}
                </div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Средняя цена</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                  {(overview?.avg_price ?? 0).toLocaleString("ru-RU")} zł
                </div>
              </div>
              <div className="bg-slate-50 border border-slate-200/80 p-3 rounded-xl text-center">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Медиана</div>
                <div className="text-lg font-extrabold text-slate-900 mt-0.5">
                  {(overview?.median_price ?? 0).toLocaleString("ru-RU")} zł
                </div>
              </div>
            </div>
          </div>
        </details>
      </div>
    </details>
  );
};
