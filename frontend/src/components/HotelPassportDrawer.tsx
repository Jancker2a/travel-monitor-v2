import React, { useState, useEffect, useRef } from "react";
import {
  X,
  ExternalLink,
  Flame,
  Star,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Scale,
  Calendar,
  Plane,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Play,
} from "lucide-react";
import { HotelPassport, HotelHistoryPoint } from "../types";
import { getHotelPassport } from "../services/api";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface HotelPassportDrawerProps {
  hotelId: string | null;
  onClose: () => void;
}

export const HotelPassportDrawer: React.FC<HotelPassportDrawerProps> = ({
  hotelId,
  onClose,
}) => {
  const [passport, setPassport] = useState<HotelPassport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"ai" | "history" | "infra" | "packages">("ai");
  const [activePhotoIdx, setActivePhotoIdx] = useState(0);

  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Fetch passport data
  useEffect(() => {
    if (!hotelId) {
      setPassport(null);
      return;
    }
    setIsLoading(true);
    setActivePhotoIdx(0);
    setActiveTab("ai");

    getHotelPassport(hotelId)
      .then((data) => {
        setPassport(data);
      })
      .catch((err) => {
        console.error("Failed to load hotel passport:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [hotelId]);

  // Render Plotly chart on history tab
  useEffect(() => {
    if (activeTab !== "history" || !passport || !passport.history_points?.length || !chartContainerRef.current || !window.Plotly) {
      return;
    }

    const pts = [...passport.history_points].sort(
      (a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime()
    );

    // Deduplicate points with identical timestamps to prevent zero-dt spline recursion in Plotly
    const ptsMap = new Map<string, HotelHistoryPoint>();
    pts.forEach((p) => {
      let key = String(p.recorded_at);
      try {
        const d = new Date(p.recorded_at);
        if (!isNaN(d.getTime())) {
          key = d.toISOString().replace("T", " ").slice(0, 19);
        }
      } catch {
        key = String(p.recorded_at).slice(0, 19);
      }
      const existing = ptsMap.get(key);
      if (!existing || p.total_price_pln < existing.total_price_pln) {
        ptsMap.set(key, p);
      }
    });

    const uniquePts = Array.from(ptsMap.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([k, p]) => ({ formattedDate: k, point: p }));

    const xDates = uniquePts.map((u) => u.formattedDate);
    const yPrices = uniquePts.map((u) => u.point.total_price_pln);
    const hoverTexts = uniquePts.map(
      (u) =>
        `<b>${u.point.total_price_pln.toLocaleString("ru-RU")} zł</b><br>` +
        `📅 Дата вылета: <b>${u.point.departure_date}</b><br>` +
        `🛫 Аэропорт: ${u.point.airport} (${u.point.duration_nights} ночей)<br>` +
        `Зафиксировано: ${u.formattedDate}`
    );

    const trace = {
      x: xDates,
      y: yPrices,
      mode: "lines+markers",
      name: "Цена тура (PLN)",
      line: { color: "#0284c7", width: 2.5, shape: "linear" },
      marker: { size: 6, color: "#0369a1" },
      text: hoverTexts,
      hoverinfo: "text",
    };

    const minPrice = passport.all_time_min_pln;
    const medianPrice = passport.typical_median_pln;

    const layout = {
      title: {
        text: "Динамика цены тура и исторический диапазон (PLN)",
        font: { size: 13, family: "Inter, sans-serif", color: "#0f172a" },
        x: 0.05,
      },
      margin: { l: 60, r: 30, t: 40, b: 40 },
      height: 320,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: {
        gridcolor: "#f1f5f9",
        tickfont: { size: 10, color: "#64748b" },
      },
      yaxis: {
        title: "Цена (PLN)",
        gridcolor: "#f1f5f9",
        tickfont: { size: 10, color: "#64748b" },
      },
      shapes: [
        {
          type: "line",
          y0: minPrice,
          y1: minPrice,
          x0: 0,
          x1: 1,
          xref: "paper",
          line: { color: "#10b981", width: 1.5, dash: "dot" },
        },
        {
          type: "line",
          y0: medianPrice,
          y1: medianPrice,
          x0: 0,
          x1: 1,
          xref: "paper",
          line: { color: "#f59e0b", width: 1.5, dash: "dot" },
        },
      ],
      annotations: [
        {
          y: minPrice,
          x: 1,
          xref: "paper",
          text: `Мин: ${minPrice.toLocaleString("ru-RU")} zł`,
          showarrow: false,
          font: { size: 10, color: "#059669" },
          bgcolor: "#ecfdf5",
          borderpad: 2,
        },
        {
          y: medianPrice,
          x: 0,
          xref: "paper",
          text: `Медиана: ${medianPrice.toLocaleString("ru-RU")} zł`,
          showarrow: false,
          font: { size: 10, color: "#b45309" },
          bgcolor: "#fef3c7",
          borderpad: 2,
        },
      ],
    };

    const config = {
      responsive: true,
      displayModeBar: false,
    };

    window.Plotly.react(chartContainerRef.current, [trace], layout, config);
  }, [activeTab, passport]);

  if (!hotelId) return null;

  const photos = passport?.gallery_photos?.length
    ? passport.gallery_photos
    : [
        passport?.main_image_url ||
          "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80",
      ];

  const handleNextPhoto = (e: React.MouseEvent) => {
    e.stopPropagation();
    setActivePhotoIdx((prev) => (prev + 1) % photos.length);
  };

  const handlePrevPhoto = (e: React.MouseEvent) => {
    e.stopPropagation();
    setActivePhotoIdx((prev) => (prev - 1 + photos.length) % photos.length);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity duration-300 animate-fadeIn"
        onClick={onClose}
      />

      {/* 780px Wide Slide-Over Drawer from Right */}
      <div className="fixed inset-y-0 right-0 max-w-full flex">
        <aside
          id="passportDrawer"
          className="w-screen max-w-[780px] bg-white shadow-2xl flex flex-col border-l border-slate-200 transform transition-transform duration-300 ease-in-out animate-slideInRight overflow-hidden"
          role="dialog"
          aria-modal="true"
        >
          {/* Top Header */}
          <div className="p-4 sm:p-5 border-b border-slate-200 bg-slate-900 text-white flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg sm:text-xl font-black tracking-tight text-white line-clamp-1">
                  {passport?.display_name || "Загрузка досье отеля..."}
                </h2>
                <div className="flex text-amber-400 text-xs shrink-0">
                  {Array.from({ length: passport?.stars || 4 }).map((_, i) => (
                    <Star key={i} className="w-3.5 h-3.5 fill-current" />
                  ))}
                </div>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                {passport?.country} • {passport?.region || "Популярный курорт"}
              </p>
            </div>

            {/* Header External Links & Close Button */}
            <div className="flex items-center gap-2 shrink-0">
              {passport?.tripadvisor_url && (
                <a
                  href={passport.tripadvisor_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 hover:bg-emerald-600/50 transition-colors"
                  title="Открыть отзывы на TripAdvisor"
                >
                  <span>🦉 TripAdvisor</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
              {passport?.youtube_search_url && (
                <a
                  href={passport.youtube_search_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-red-600/30 text-red-300 border border-red-500/40 hover:bg-red-600/50 transition-colors"
                  title="Смотреть видеообзоры туристов на YouTube"
                >
                  <Play className="w-3 h-3 fill-current" />
                  <span>YouTube</span>
                </a>
              )}
              <button
                type="button"
                id="drawerCloseBtn"
                onClick={onClose}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors border border-slate-700"
                title="Закрыть"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Sticky 4 Tabs Bar */}
          <nav className="flex items-center bg-slate-100 border-b border-slate-200 px-4 py-2 gap-1 overflow-x-auto scrollbar-none">
            <button
              type="button"
              onClick={() => setActiveTab("ai")}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                activeTab === "ai"
                  ? "bg-white text-blue-700 shadow-sm border border-slate-200/80"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/60"
              }`}
            >
              <span>🤖 AI-Обзор и Отзывы</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("history")}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                activeTab === "history"
                  ? "bg-white text-blue-700 shadow-sm border border-slate-200/80"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/60"
              }`}
            >
              <span>📈 Анализ и график цен</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("infra")}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                activeTab === "infra"
                  ? "bg-white text-blue-700 shadow-sm border border-slate-200/80"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/60"
              }`}
            >
              <span>🏖 Инфраструктура</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("packages")}
              className={`px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                activeTab === "packages"
                  ? "bg-white text-blue-700 shadow-sm border border-slate-200/80"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-200/60"
              }`}
            >
              <span>📦 Все вылеты ({passport?.available_packages?.length || 0})</span>
            </button>
          </nav>

          {/* Scrollable Drawer Body */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
            {isLoading ? (
              <div className="py-20 text-center space-y-3">
                <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-xs text-slate-500 font-semibold">
                  Формирование AI Паспорта и загрузка базы отзывов...
                </p>
              </div>
            ) : passport ? (
              <>
                {/* ═══════════════════════════════════════════════════════
                    TAB 1: AI-ОБЗОР, ОТЗЫВЫ И YOUTUBE
                    ═══════════════════════════════════════════════════════ */}
                {activeTab === "ai" && (
                  <div className="space-y-5">
                    {/* Photo Carousel Stage */}
                    <div className="relative rounded-2xl overflow-hidden bg-slate-900 aspect-video shadow-md group">
                      <img
                        src={photos[activePhotoIdx]}
                        alt={passport.display_name}
                        className="w-full h-full object-cover transition-opacity duration-300"
                      />
                      {photos.length > 1 && (
                        <>
                          <button
                            type="button"
                            onClick={handlePrevPhoto}
                            className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center transition-colors"
                          >
                            <ChevronLeft className="w-5 h-5" />
                          </button>
                          <button
                            type="button"
                            onClick={handleNextPhoto}
                            className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/60 hover:bg-black/80 text-white flex items-center justify-center transition-colors"
                          >
                            <ChevronRight className="w-5 h-5" />
                          </button>
                          <div className="absolute bottom-3 right-3 px-2 py-0.5 rounded-full bg-black/70 text-white text-[11px] font-bold">
                            {activePhotoIdx + 1} / {photos.length}
                          </div>
                        </>
                      )}
                    </div>

                    {/* Photo Thumbnails Strip */}
                    {photos.length > 1 && (
                      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                        {photos.map((url, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setActivePhotoIdx(idx)}
                            className={`w-16 h-12 rounded-lg overflow-hidden shrink-0 border-2 transition-all ${
                              activePhotoIdx === idx
                                ? "border-blue-600 scale-105 shadow-sm"
                                : "border-transparent opacity-70 hover:opacity-100"
                            }`}
                          >
                            <img
                              src={url}
                              alt=""
                              className="w-full h-full object-cover"
                            />
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Chips Row */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="spec-badge spec-beach">
                        🏖️ {passport.beach_line}-я линия ({passport.beach_type})
                      </span>
                      {passport.has_aquapark && (
                        <span className="spec-badge spec-aqua">
                          🎢 Собственный аквапарк
                        </span>
                      )}
                      {passport.has_heated_pools && (
                        <span className="spec-badge spec-heat">
                          🔥 Подогреваемый бассейн
                        </span>
                      )}
                      <span className="spec-badge spec-kids">
                        🍽️ {passport.food_concept}
                      </span>
                      <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 rounded-md text-xs font-bold">
                        <span>● TripAdvisor: {passport.ta_rating?.toFixed(1) || "4.5"}</span>
                        <span className="text-emerald-600 text-[10px]">
                          ({passport.ta_reviews} отзывов)
                        </span>
                      </span>
                    </div>

                    {/* AI Executive Dossier & Live Price Oracle Card */}
                    <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50/70 to-indigo-50/50 p-4 sm:p-5 shadow-sm space-y-3">
                      <div className="flex items-center justify-between pb-2 border-b border-blue-200/60">
                        <div className="flex items-center gap-2">
                          <Sparkles className="w-5 h-5 text-blue-600" />
                          <h3 className="text-xs font-bold uppercase tracking-wider text-blue-900">
                            AI Market Oracle: Вердикт по покупке
                          </h3>
                        </div>
                        <span className="text-xs font-extrabold text-blue-700 bg-blue-100 px-2.5 py-0.5 rounded-full">
                          {passport.ai_action_signal || "🟢 РЕКОМЕНДУЕТСЯ К ПОКУПКЕ"}
                        </span>
                      </div>

                      <p className="text-xs sm:text-sm text-slate-800 leading-relaxed font-medium">
                        {passport.ai_price_summary}
                      </p>

                      <div className="p-3 bg-white/80 rounded-xl border border-blue-100 text-xs text-slate-700 space-y-1">
                        <div className="font-bold text-slate-900 flex items-center gap-1.5">
                          <span>🎯 Кому подходит:</span>
                          <span className="text-blue-700 font-semibold">
                            {passport.suitable_for}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 leading-normal">
                          {passport.ai_hotel_summary || passport.verdict}
                        </p>
                      </div>
                    </div>

                    {/* Pros & Cons Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {/* Pros */}
                      <div className="bg-emerald-50/70 border border-emerald-200/80 rounded-2xl p-4 space-y-2">
                        <div className="text-xs font-bold uppercase tracking-wider text-emerald-800 flex items-center gap-1.5">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          <span>Сильные стороны отеля</span>
                        </div>
                        <ul className="space-y-1.5 text-xs text-slate-800">
                          {passport.pros.map((p, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <span className="text-emerald-600 font-bold">✓</span>
                              <span>{p}</span>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* Cons */}
                      <div className="bg-amber-50/70 border border-amber-200/80 rounded-2xl p-4 space-y-2">
                        <div className="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                          <AlertTriangle className="w-4 h-4 text-amber-600" />
                          <span>Нюансы и особенности</span>
                        </div>
                        <ul className="space-y-1.5 text-xs text-slate-800">
                          {passport.cons.map((c, idx) => (
                            <li key={idx} className="flex items-start gap-1.5">
                              <span className="text-amber-600 font-bold">•</span>
                              <span>{c}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* YouTube Review Card */}
                    {passport.youtube_search_url && (
                      <div className="bg-slate-900 text-white rounded-2xl p-4 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-red-600 flex items-center justify-center shrink-0 shadow-md">
                            <Play className="w-5 h-5 fill-current text-white" />
                          </div>
                          <div>
                            <div className="text-xs font-bold text-white">
                              Видеообзоры туристов на YouTube
                            </div>
                            <div className="text-[11px] text-slate-400">
                              Реальные съемки номеров, пляжа, питания и шведского стола
                            </div>
                          </div>
                        </div>

                        <a
                          href={passport.youtube_search_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-colors whitespace-nowrap shadow-sm"
                        >
                          Смотреть обзоры ↗
                        </a>
                      </div>
                    )}
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    TAB 2: АНАЛИЗ И ГРАФИК ЦЕН PLOTLY + АРБИТРАЖ
                    ═══════════════════════════════════════════════════════ */}
                {activeTab === "history" && (
                  <div className="space-y-5">
                    {/* Plotly Chart Card */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
                      <div ref={chartContainerRef} className="w-full" />
                    </div>

                    {/* Stats Metrics Row */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-center">
                        <div className="text-[10px] text-slate-500 font-semibold uppercase">
                          Исторический мин.
                        </div>
                        <div className="text-sm font-black text-emerald-600 mt-0.5">
                          {passport.all_time_min_pln.toLocaleString("ru-RU")} zł
                        </div>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-center">
                        <div className="text-[10px] text-slate-500 font-semibold uppercase">
                          Медиана сезона
                        </div>
                        <div className="text-sm font-bold text-slate-800 mt-0.5">
                          {passport.typical_median_pln.toLocaleString("ru-RU")} zł
                        </div>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-center">
                        <div className="text-[10px] text-slate-500 font-semibold uppercase">
                          Исторический макс.
                        </div>
                        <div className="text-sm font-bold text-slate-800 mt-0.5">
                          {passport.all_time_max_pln.toLocaleString("ru-RU")} zł
                        </div>
                      </div>
                      <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-center">
                        <div className="text-[10px] text-slate-500 font-semibold uppercase">
                          Текущая цена
                        </div>
                        <div className="text-sm font-black text-blue-600 mt-0.5">
                          {passport.current_price_pln.toLocaleString("ru-RU")} zł
                        </div>
                      </div>
                    </div>

                    {/* Cross-Border German Arbitrage Banner */}
                    {passport.german_arbitrage && (
                      <div className="bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border border-amber-500/30 rounded-2xl p-4 sm:p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <Scale className="w-5 h-5 text-amber-600" />
                          <h4 className="text-xs font-bold uppercase tracking-wider text-amber-900">
                            Немецкий арбитраж: Вылет из Берлина (BER)
                          </h4>
                        </div>
                        <p className="text-xs text-slate-700 leading-relaxed mb-3">
                          Этот же отель на немецком рынке через туроператора{" "}
                          <b>{passport.german_arbitrage.berlin_operator}</b> стоит{" "}
                          <b>
                            {passport.german_arbitrage.berlin_price_pln.toLocaleString(
                              "ru-RU"
                            )}{" "}
                            zł
                          </b>{" "}
                          с вылетом из <b>BER</b>. Экономия составляет{" "}
                          <span className="text-emerald-700 font-black">
                            −
                            {passport.german_arbitrage.savings_pln.toLocaleString(
                              "ru-RU"
                            )}{" "}
                            zł ({passport.german_arbitrage.savings_pct}%)
                          </span>
                          .
                        </p>
                        <div className="text-[11px] text-slate-500 bg-white/70 p-2.5 rounded-lg border border-amber-200">
                          🚆 {passport.german_arbitrage.train_transfer_from_pl}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    TAB 3: ДЕТАЛЬНАЯ ИНФРАСТРУКТУРА
                    ═══════════════════════════════════════════════════════ */}
                {activeTab === "infra" && passport.infra_rich && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                    {/* Beach */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                      <div className="font-bold text-slate-900 flex items-center gap-2 text-sm border-b pb-2">
                        <span>🏖️ Пляж и вход в воду</span>
                      </div>
                      <div className="space-y-1 text-slate-700">
                        <div><b>Линия:</b> {passport.infra_rich.beach?.line}</div>
                        <div><b>Тип берега:</b> {passport.infra_rich.beach?.type}</div>
                        <div><b>Вход в море:</b> {passport.infra_rich.beach?.entry}</div>
                        <div><b>Пирс:</b> {passport.infra_rich.beach?.pier}</div>
                        <div className="text-[11px] text-slate-500 mt-1">{passport.infra_rich.beach?.facilities}</div>
                      </div>
                    </div>

                    {/* Pools & Aquapark */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                      <div className="font-bold text-slate-900 flex items-center gap-2 text-sm border-b pb-2">
                        <span>🎢 Бассейны и Аквапарк</span>
                      </div>
                      <div className="space-y-1 text-slate-700">
                        <div><b>Горки:</b> {passport.infra_rich.pools?.aquapark}</div>
                        <div><b>Подогрев:</b> {passport.infra_rich.pools?.heated}</div>
                        <div><b>Детский бассейн:</b> {passport.infra_rich.pools?.children_pool}</div>
                      </div>
                    </div>

                    {/* Dining */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                      <div className="font-bold text-slate-900 flex items-center gap-2 text-sm border-b pb-2">
                        <span>🍽️ Питание и Рестораны</span>
                      </div>
                      <div className="space-y-1 text-slate-700">
                        <div><b>Концепция:</b> {passport.infra_rich.dining?.concept}</div>
                        <div><b>Шведский стол:</b> {passport.infra_rich.dining?.main_restaurant}</div>
                        <div><b>A la Carte:</b> {passport.infra_rich.dining?.a_la_carte}</div>
                        <div><b>Бары:</b> {passport.infra_rich.dining?.bars}</div>
                      </div>
                    </div>

                    {/* Kids */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                      <div className="font-bold text-slate-900 flex items-center gap-2 text-sm border-b pb-2">
                        <span>👶 Для детей</span>
                      </div>
                      <div className="space-y-1 text-slate-700">
                        <div><b>Мини-клуб:</b> {passport.infra_rich.kids?.miniclub}</div>
                        <div><b>Площадка:</b> {passport.infra_rich.kids?.playground}</div>
                        <div><b>Удобства:</b> {passport.infra_rich.kids?.services}</div>
                      </div>
                    </div>

                    {/* Spa & Sport */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                      <div className="font-bold text-slate-900 flex items-center gap-2 text-sm border-b pb-2">
                        <span>🧖 SPA и Спорт</span>
                      </div>
                      <div className="space-y-1 text-slate-700">
                        <div><b>SPA:</b> {passport.infra_rich.spa_sport?.spa}</div>
                        <div><b>Фитнес:</b> {passport.infra_rich.spa_sport?.fitness}</div>
                        <div><b>Спорт:</b> {passport.infra_rich.spa_sport?.sport}</div>
                      </div>
                    </div>

                    {/* Comfort & Rooms */}
                    <div className="bg-white rounded-2xl border border-slate-200 p-4 space-y-2">
                      <div className="font-bold text-slate-900 flex items-center gap-2 text-sm border-b pb-2">
                        <span>🛋️ Номера и связь</span>
                      </div>
                      <div className="space-y-1 text-slate-700">
                        <div><b>Интернет:</b> {passport.infra_rich.comfort?.wifi}</div>
                        <div><b>Оснащение:</b> {passport.infra_rich.comfort?.rooms}</div>
                        <div><b>Трансфер:</b> {passport.infra_rich.comfort?.transfer}</div>
                      </div>
                    </div>
                  </div>
                )}

                {/* ═══════════════════════════════════════════════════════
                    TAB 4: ВСЕ ВЫЛЕТЫ И ПАКЕТЫ
                    ═══════════════════════════════════════════════════════ */}
                {activeTab === "packages" && (
                  <div className="space-y-3">
                    <div className="text-xs text-slate-500 font-medium">
                      Найдено {passport.available_packages?.length || 0} доступных пакетов по разным датам и аэропортам вылета:
                    </div>

                    <div className="divide-y divide-slate-100 bg-white rounded-2xl border border-slate-200 overflow-hidden">
                      {passport.available_packages?.map((pkg) => (
                        <div
                          key={pkg.cohort_hash}
                          className="p-3.5 flex items-center justify-between hover:bg-slate-50 transition-colors"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-extrabold text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-xs border border-blue-200">
                                {pkg.airport}
                              </span>
                              <span className="text-xs font-bold text-slate-900">
                                {pkg.departure_date}
                              </span>
                              <span className="text-xs text-slate-500">
                                ({pkg.duration_nights} ночей)
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-400 mt-0.5">
                              Туроператор: {pkg.operator || "Coral / TUI / Anex"}
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            <div className="text-right">
                              <div className="text-sm font-black text-slate-900">
                                {pkg.total_price_pln.toLocaleString("ru-RU")} zł
                              </div>
                              <div className="text-[10px] text-slate-400">
                                {pkg.price_per_night_pax} zł/ночь
                              </div>
                            </div>

                            {pkg.booking_url && (
                              <a
                                href={pkg.booking_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-colors flex items-center gap-1 shadow-sm"
                              >
                                <span>Бронировать</span>
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : null}
          </div>
        </aside>
      </div>
    </div>
  );
};
