import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  X,
  ExternalLink,
  Star,
  Play,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { HotelPassport } from "../types";
import { getHotelPassport, getHotelNormalizedHistory } from "../services/api";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface HotelPassportDrawerProps {
  hotelId: string | null;
  filterId?: string | null;
  onClose: () => void;
}

export const HotelPassportDrawer: React.FC<HotelPassportDrawerProps> = ({
  hotelId,
  filterId,
  onClose,
}) => {
  const [passport, setPassport] = useState<HotelPassport | null>(null);
  const [normalizedData, setNormalizedData] = useState<any>(null);
  const [historyMode, setHistoryMode] = useState<"original" | "normalized">("original");
  const [historyRange, setHistoryRange] = useState<"7d" | "30d" | "all">("all");
  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"ai" | "history" | "infra" | "packages">("ai");
  const [activePhotoIdx, setActivePhotoIdx] = useState(0);

  const chartContainerRef = useRef<HTMLDivElement>(null);

  // Fetch passport data & normalized history
  useEffect(() => {
    if (!hotelId) {
      setPassport(null);
      setNormalizedData(null);
      return;
    }
    setIsLoading(true);
    setActivePhotoIdx(0);
    setActiveTab("ai");
    setHistoryMode("original");

    getHotelPassport(hotelId, filterId || undefined)
      .then((data) => setPassport(data))
      .catch((err) => console.error("Failed to load hotel passport:", err))
      .finally(() => setIsLoading(false));

    getHotelNormalizedHistory(hotelId)
      .then((data) => setNormalizedData(data))
      .catch(() => setNormalizedData(null));
  }, [hotelId, filterId]);

  // Render Plotly Price History Chart when history tab is activated
  useEffect(() => {
    if (activeTab !== "history" || !passport || !chartContainerRef.current || !window.Plotly) {
      return;
    }

    if (historyMode === "normalized" && normalizedData?.points?.length) {
      // Normalized Benchmark Series (1 pax, 8 nights)
      let normPoints = normalizedData.points;
      if (historyRange !== "all") {
        const now = new Date().getTime();
        const cutoffDays = historyRange === "7d" ? 7 : 30;
        const cutoffMs = now - cutoffDays * 24 * 60 * 60 * 1000;
        const filtered = normPoints.filter(
          (p: any) => new Date(p.recorded_at).getTime() >= cutoffMs
        );
        if (filtered.length > 0) normPoints = filtered;
      }

      const xVals = normPoints.map((p: any) => p.recorded_at);
      const yVals = normPoints.map((p: any) => p.normalized_price_1p_8n);
      const minP = Math.min(...yVals);
      const sortedY = [...yVals].sort((a, b) => a - b);
      const medP = sortedY[Math.floor(sortedY.length / 2)] || minP;

      const trace = {
        x: xVals,
        y: yVals,
        type: "scatter",
        mode: "lines+markers",
        name: "Эталон 1p / 8n (PLN)",
        line: { color: "#0891b2", width: 2.5, shape: "linear" },
        marker: { size: 5, color: "#0e7490" },
        hovertemplate: "<b>%{y:,.0f} zł</b> (1 чел / 8н)<br>%{x|%d.%m %H:%M}<extra></extra>",
      };

      const layout = {
        title: {
          text: "Нормализованный эталон цен (1 человек • 8 ночей, PLN)",
          font: { size: 13, family: "Inter, sans-serif", color: "#0f172a" },
          x: 0.05,
        },
        margin: { l: 55, r: 25, t: 40, b: 40 },
        height: 320,
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        xaxis: { gridcolor: "#f1f5f9", tickfont: { size: 10, color: "#64748b" } },
        yaxis: { title: "Эталон (PLN)", gridcolor: "#f1f5f9", tickfont: { size: 10, color: "#64748b" } },
        shapes: [
          { type: "line", y0: minP, y1: minP, x0: 0, x1: 1, xref: "paper", line: { color: "#10b981", width: 1.5, dash: "dot" } },
          { type: "line", y0: medP, y1: medP, x0: 0, x1: 1, xref: "paper", line: { color: "#f59e0b", width: 1.5, dash: "dot" } },
        ],
        font: { family: "Inter, sans-serif", size: 11 },
      };

      window.Plotly.react(chartContainerRef.current, [trace], layout, { responsive: true, displayModeBar: false });
      return;
    }

    // Original Tour History (2+1 / Custom)
    const allHistory = passport.history_points || [];
    if (!allHistory.length) return;

    let history = allHistory;
    if (historyRange !== "all") {
      const now = new Date().getTime();
      const cutoffDays = historyRange === "7d" ? 7 : 30;
      const cutoffMs = now - cutoffDays * 24 * 60 * 60 * 1000;
      const filtered = allHistory.filter(
        (pt) => new Date(pt.recorded_at).getTime() >= cutoffMs
      );
      if (filtered.length > 0) {
        history = filtered;
      }
    }

    // Deduplicate timestamps to prevent recursion
    const uniqueMap = new Map<string, number>();
    history.forEach((pt) => {
      uniqueMap.set(pt.recorded_at, pt.total_price_pln);
    });

    const xVals: string[] = [];
    const yVals: number[] = [];
    uniqueMap.forEach((val, key) => {
      xVals.push(key);
      yVals.push(val);
    });

    const trace = {
      x: xVals,
      y: yVals,
      type: "scatter",
      mode: "lines+markers",
      name: "Цена тура (PLN)",
      line: {
        color: "#4f46e5",
        width: 2.5,
        shape: "linear",
      },
      marker: {
        size: 5,
        color: "#4338ca",
      },
      hovertemplate: "<b>%{y:,.0f} zł</b><br>%{x|%d.%m %H:%M}<extra></extra>",
    };

    const pVals = yVals.length ? yVals : [passport.current_price_pln];
    const minPrice = Math.min(...pVals);
    const sortedP = [...pVals].sort((a, b) => a - b);
    const medianPrice = sortedP[Math.floor(sortedP.length / 2)] || minPrice;

    const layout = {
      title: {
        text: "Динамика цены тура и исторический диапазон (PLN)",
        font: { size: 13, family: "Inter, sans-serif", color: "#0f172a" },
        x: 0.05,
      },
      margin: { l: 55, r: 25, t: 40, b: 40 },
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
      font: { family: "Inter, sans-serif", size: 11 },
    };

    const config = {
      responsive: true,
      displayModeBar: false,
    };

    window.Plotly.react(chartContainerRef.current, [trace], layout, config);
  }, [activeTab, passport, historyMode, historyRange, normalizedData]);

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

  const currentPrice = passport?.current_price_pln || 0;
  const minPrice = passport?.all_time_min_pln || 0;
  const maxPrice = passport?.all_time_max_pln || 0;
  const savings = maxPrice > currentPrice ? maxPrice - currentPrice : 0;

  // Dynamic values depending on active filter range (7d / 30d / all)
  const rangeStats = useMemo(() => {
    if (historyMode === "normalized") {
      let normPoints = normalizedData?.points || [];
      if (historyRange !== "all") {
        const now = Date.now();
        const cutoffDays = historyRange === "7d" ? 7 : 30;
        const cutoffMs = now - cutoffDays * 24 * 60 * 60 * 1000;
        const filtered = normPoints.filter(
          (p: any) => new Date(p.recorded_at).getTime() >= cutoffMs
        );
        if (filtered.length > 0) normPoints = filtered;
      }
      const yVals = normPoints.map((p: any) => p.normalized_price_1p_8n);
      const cur = yVals.length > 0 ? yVals[yVals.length - 1] : normalizedData?.stats?.current_normalized_pln || 0;
      const min = yVals.length > 0 ? Math.min(...yVals) : normalizedData?.stats?.min_normalized_pln || 0;
      const max = yVals.length > 0 ? Math.max(...yVals) : normalizedData?.stats?.max_normalized_pln || 0;
      return { cur, min, max, savings: max > cur ? max - cur : 0 };
    }

    let hist = passport?.history_points || [];
    if (historyRange !== "all") {
      const now = Date.now();
      const cutoffDays = historyRange === "7d" ? 7 : 30;
      const cutoffMs = now - cutoffDays * 24 * 60 * 60 * 1000;
      const filtered = hist.filter(
        (p) => new Date(p.recorded_at).getTime() >= cutoffMs
      );
      if (filtered.length > 0) hist = filtered;
    }
    const pVals = hist.map((p) => p.total_price_pln);
    const cur = pVals.length > 0 ? pVals[pVals.length - 1] : currentPrice;
    const min = pVals.length > 0 ? Math.min(...pVals) : minPrice;
    const max = pVals.length > 0 ? Math.max(...pVals) : maxPrice;
    return { cur, min, max, savings: max > cur ? max - cur : 0 };
  }, [historyMode, historyRange, normalizedData, passport?.history_points, currentPrice, minPrice, maxPrice]);

  return (
    <>
      {/* V1 Authentic Backdrop */}
      <div
        className={`drawer-overlay ${hotelId ? "open" : ""}`}
        id="passportDrawerOverlay"
        onClick={onClose}
      />

      {/* V1 Authentic 780px Slide-Over Drawer */}
      <aside
        id="passportDrawer"
        className={`passport-drawer ${hotelId ? "open" : ""}`}
        role="dialog"
        aria-labelledby="drawerHotelTitle"
        aria-modal="true"
      >
        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-title-box">
            <div className="drawer-title-row">
              <h2 id="drawerHotelTitle">{passport?.display_name || "Загрузка отеля..."}</h2>
              <span className="hotel-stars" id="drawerStarsRow">
                {"★".repeat(passport?.stars || 4)}
              </span>
            </div>
            <p id="drawerHotelSubtitle">
              {passport?.country} • {passport?.region || "Популярный курорт"}
            </p>
          </div>

          <div className="drawer-header-actions">
            {passport?.tripadvisor_url && (
              <a
                className="btn-drawer-header-ta"
                href={passport.tripadvisor_url}
                target="_blank"
                rel="noopener noreferrer"
                id="drawerHeaderTaLink"
                title="Открыть отзывы на TripAdvisor"
              >
                🦉 TripAdvisor ↗
              </a>
            )}
            {passport?.youtube_search_url && (
              <a
                className="btn-drawer-header-yt"
                href={passport.youtube_search_url}
                target="_blank"
                rel="noopener noreferrer"
                id="drawerHeaderYtLink"
                title="Смотреть обзоры на YouTube"
              >
                ▶ YouTube ↗
              </a>
            )}
            <button
              className="drawer-close-btn"
              id="drawerCloseBtn"
              onClick={onClose}
              title="Закрыть"
              type="button"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Sticky Tabs Bar */}
        <nav className="drawer-tabs-bar" id="drawerTabsBar">
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "ai" ? "active" : ""}`}
            onClick={() => setActiveTab("ai")}
          >
            🤖 AI-Обзор и Отзывы
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
          >
            📈 Анализ и график цен
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "infra" ? "active" : ""}`}
            onClick={() => setActiveTab("infra")}
          >
            🏖 Инфраструктура
          </button>
          <button
            type="button"
            className={`drawer-tab-btn ${activeTab === "packages" ? "active" : ""}`}
            onClick={() => setActiveTab("packages")}
          >
            📦 Все вылеты и фильтры
          </button>
        </nav>

        {/* Scrollable Content */}
        <div className="drawer-content" id="drawerScrollContent" style={{ overflowY: "auto", padding: "18px 22px" }}>
          {/* TAB 1: AI-Обзор & Отзывы & YouTube */}
          {activeTab === "ai" && (
            <div className="drawer-tab-panel active" id="tabPanel-ai">
              {/* Photo Gallery Carousel */}
              <div className="drawer-gallery-box" id="drawerGalleryBox">
                <div className="gallery-stage" style={{ height: "260px" }}>
                  <img
                    alt={passport?.display_name || "Фото отеля"}
                    className="gallery-main-img"
                    id="galleryMainImg"
                    src={photos[activePhotoIdx]}
                  />
                  {photos.length > 1 && (
                    <>
                      <button
                        className="gallery-nav-btn prev"
                        style={{ left: "10px" }}
                        onClick={handlePrevPhoto}
                        type="button"
                        aria-label="Предыдущее фото"
                      >
                        ‹
                      </button>
                      <button
                        className="gallery-nav-btn next"
                        style={{ right: "10px" }}
                        onClick={handleNextPhoto}
                        type="button"
                        aria-label="Следующее фото"
                      >
                        ›
                      </button>
                      <div
                        className="gallery-counter-pill"
                        id="galleryCounterPill"
                        style={{
                          display: "block",
                          position: "absolute",
                          bottom: "10px",
                          right: "10px",
                          background: "rgba(15, 23, 42, 0.75)",
                          color: "#fff",
                          padding: "3px 8px",
                          borderRadius: "12px",
                          fontSize: "11px",
                        }}
                      >
                        {activePhotoIdx + 1} / {photos.length}
                      </div>
                    </>
                  )}
                </div>

                {photos.length > 1 && (
                  <div
                    className="gallery-thumbs-row"
                    id="galleryThumbsRow"
                    style={{
                      display: "flex",
                      gap: "6px",
                      padding: "8px",
                      overflowX: "auto",
                      background: "#f8fafc",
                    }}
                  >
                    {photos.slice(0, 10).map((p, idx) => (
                      <img
                        key={idx}
                        src={p}
                        alt="Превью"
                        onClick={() => setActivePhotoIdx(idx)}
                        style={{
                          width: "56px",
                          height: "40px",
                          objectFit: "cover",
                          borderRadius: "6px",
                          cursor: "pointer",
                          border: idx === activePhotoIdx ? "2px solid #4f46e5" : "1px solid #cbd5e1",
                          opacity: idx === activePhotoIdx ? 1 : 0.65,
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Badges */}
              <div className="drawer-hero-badges" id="drawerHeroBadges" style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "12px" }}>
                <span className="badge" style={{ background: "#e0e7ff", color: "#3730a3", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                  Deal Score {passport?.deal_score || 82}/100
                </span>
                <span className="badge" style={{ background: "#ecfdf5", color: "#065f46", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                  {passport?.hopper_verdict === "BUY" ? "🟢 СИГНАЛ: ПОКУПАТЬ" : "↔ СТАБИЛЬНО"}
                </span>
                <span className="badge" style={{ background: "#fef3c7", color: "#92400e", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                  TripAdvisor {passport?.ta_rating ? `★ ${passport.ta_rating}` : "★ 4.5"}
                </span>
              </div>

              {/* AI Executive Dossier & Live Price Oracle Card */}
              <div className="drawer-ai-oracle-card">
                <div className="oracle-header">
                  <div className="oracle-title-wrap">
                    <span className="oracle-robot-icon">🤖</span>
                    <div>
                      <div className="oracle-title">AI-Саммари и Ценовой Анализ</div>
                      <div className="oracle-subtitle">Анализ отеля, инфраструктуры и текущей точки входа</div>
                    </div>
                  </div>
                  <div className="oracle-deal-pill" id="drawerOraclePriceBadge" style={{ background: "#dcfce7", color: "#15803d", fontWeight: 700, padding: "4px 10px", borderRadius: "20px", fontSize: "11px" }}>
                    🟢 Выгодно брать
                  </div>
                </div>

                <div className="oracle-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  {/* Left: Hotel Dossier */}
                  <div className="oracle-col hotel-col">
                    <div className="oracle-col-title" style={{ fontWeight: 700, fontSize: "12px", color: "#1e293b", marginBottom: "6px" }}>
                      🏨 Об отеле и отдыхе
                    </div>
                    <p className="oracle-body-text" id="drawerAiHotelSummaryText" style={{ fontSize: "12px", color: "#334155", lineHeight: "1.5" }}>
                      {passport?.ai_hotel_summary ||
                        "Качественный отель с комфортной зеленой территорией и развитой пляжной инфраструктурой. Высокая оценка за питание и сервис персонала."}
                    </p>
                    <div className="oracle-meta-line" style={{ marginTop: "8px", fontSize: "11px" }}>
                      <span className="oracle-meta-lbl" style={{ color: "#64748b" }}>🎯 Для кого: </span>
                      <span className="oracle-meta-val" id="drawerAiAudienceText" style={{ fontWeight: 600, color: "#0f172a" }}>
                        {passport?.suitable_for || "Семьи с детьми, пары, ценители сервиса"}
                      </span>
                    </div>
                  </div>

                  {/* Right: Price Intelligence */}
                  <div className="oracle-col price-col">
                    <div className="oracle-col-title" style={{ fontWeight: 700, fontSize: "12px", color: "#1e293b", marginBottom: "6px" }}>
                      💰 Текущая цена и выгода
                    </div>
                    <div className="oracle-price-row" style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
                      <span className="oracle-price-val" id="drawerOracleCurPrice" style={{ fontSize: "18px", fontWeight: 800, color: "#0f172a" }}>
                        {currentPrice.toLocaleString("ru-RU")} zł
                      </span>
                      {savings > 0 && (
                        <span className="oracle-diff-pill" id="drawerOraclePriceDiff" style={{ background: "#dcfce7", color: "#166534", fontSize: "11px", fontWeight: 700, padding: "2px 6px", borderRadius: "6px" }}>
                          -{savings.toLocaleString("ru-RU")} zł
                        </span>
                      )}
                    </div>
                    <p className="oracle-body-text" id="drawerAiPriceVerdictText" style={{ fontSize: "12px", color: "#334155", lineHeight: "1.5", marginTop: "4px" }}>
                      {passport?.ai_price_summary ||
                        "Цена находится в нижней четверти исторического коридора. Рекомендуется фиксировать тур."}
                    </p>
                    <div className="oracle-meta-line" style={{ marginTop: "8px", fontSize: "11px" }}>
                      <span className="oracle-meta-lbl" style={{ color: "#64748b" }}>🔮 Сигнал Hopper: </span>
                      <span className="oracle-meta-val" id="drawerAiActionSignal" style={{ fontWeight: 700, color: "#15803d" }}>
                        {passport?.ai_action_signal || "Покупать сейчас"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Compact YouTube Video Review Banner */}
              <div className="yt-compact-banner">
                <div className="yt-banner-left">
                  <svg className="yt-svg-lg" viewBox="0 0 24 24">
                    <path
                      d="M23.5 6.2c-.3-1-.9-1.8-1.9-2.1C19.9 3.5 12 3.5 12 3.5s-7.9 0-9.6.6c-1 .3-1.6 1.1-1.9 2.1C0 8.1 0 12 0 12s0 3.9.5 5.8c.3 1 .9 1.8 1.9 2.1 1.7.6 9.6.6 9.6.6s7.9 0 9.6-.6c1-.3 1.6-1.1 1.9-2.1.5-1.9.5-5.8.5-5.8s0-3.9-.5-5.8z"
                      fill="#FF0000"
                    />
                    <polygon fill="#FFFFFF" points="9.6,15.6 15.8,12 9.6,8.4" />
                  </svg>
                  <div>
                    <h4>Видеообзоры туристов на YouTube</h4>
                    <p>Смотрите живые рум-туры, обзоры территории и пляжа перед покупкой</p>
                  </div>
                </div>
                <a
                  className="btn-yt-main"
                  href={passport?.youtube_search_url || "https://www.youtube.com"}
                  target="_blank"
                  rel="noopener noreferrer"
                  id="drawerYtAllBtn"
                >
                  ▶ Все видео на YouTube ↗
                </a>
              </div>

              {/* External Ratings */}
              <div className="drawer-reviews-row">
                <a
                  className="ext-review-card"
                  href={passport?.tripadvisor_url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  id="drawerTripadvisorLink"
                >
                  <div className="ext-review-info">
                    <h5>🦉 TripAdvisor Рейтинг</h5>
                    <p id="drawerTaReviewsCount">
                      {passport?.ta_reviews
                        ? `на основе ${passport.ta_reviews} отзывов`
                        : "на основе свежих отзывов"}
                    </p>
                  </div>
                  <div className="ext-review-score" id="drawerTaScore">
                    ★ {passport?.ta_rating || "4.5"}
                  </div>
                </a>

                <a
                  className="ext-review-card"
                  href={`https://www.google.com/search?q=${encodeURIComponent((passport?.display_name || "") + " отзывы")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  id="drawerGoogleLink"
                >
                  <div className="ext-review-info">
                    <h5>🔍 Отзывы в Google</h5>
                    <p>Поиск свежих впечатлений</p>
                  </div>
                  <div className="ext-review-score">↗</div>
                </a>
              </div>

              {/* Pros & Cons */}
              <div className="pros-cons-grid">
                <div className="pros-card">
                  <h5>✅ Ключевые преимущества</h5>
                  <ul className="pros-list" id="drawerProsList">
                    {(passport?.pros || [
                      "Первая береговая линия и пологий вход в море",
                      "Разнообразное питание All Inclusive с морепродуктами",
                      "Большая зеленая ухоженная территория и аквапарк",
                      "Качественная анимация для детей и взрослых",
                    ]).map((pro, idx) => (
                      <li key={idx}>{pro}</li>
                    ))}
                  </ul>
                </div>

                <div className="cons-card">
                  <h5>⚠️ На что обратить внимание</h5>
                  <ul className="cons-list" id="drawerConsList">
                    {(passport?.cons || [
                      "В пик сезона возможны очереди в основном ресторане",
                      "Некоторые корпуса удалены от главного пляжа",
                    ]).map((con, idx) => (
                      <li key={idx}>{con}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: График Plotly и Аналитика */}
          {activeTab === "history" && (
            <div className="drawer-tab-panel active" id="tabPanel-history">
              <div className="chart-controls-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                <div className="mode-switch-box">
                  <button
                    type="button"
                    className={`mode-btn ${historyMode === "original" ? "active" : ""}`}
                    onClick={() => setHistoryMode("original")}
                  >
                    Пакетный тур ({passport?.active_cohorts_count || 1} напр.)
                  </button>
                  <button
                    type="button"
                    className={`mode-btn ${historyMode === "normalized" ? "active" : ""}`}
                    onClick={() => setHistoryMode("normalized")}
                  >
                    🏷️ Эталон (1 чел / 8 ночей)
                  </button>
                </div>

                <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-semibold">
                  <button
                    type="button"
                    onClick={() => setHistoryRange("7d")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${
                      historyRange === "7d"
                        ? "bg-white text-slate-900 shadow-2xs font-bold"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    7 дней
                  </button>
                  <button
                    type="button"
                    onClick={() => setHistoryRange("30d")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${
                      historyRange === "30d"
                        ? "bg-white text-slate-900 shadow-2xs font-bold"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    30 дней
                  </button>
                  <button
                    type="button"
                    onClick={() => setHistoryRange("all")}
                    className={`px-2.5 py-1 rounded-lg transition-all ${
                      historyRange === "all"
                        ? "bg-white text-slate-900 shadow-2xs font-bold"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    Вся история
                  </button>
                </div>

                <div className="stat-pill" style={{ background: "#dcfce7", color: "#166534", padding: "4px 10px", borderRadius: "20px", fontSize: "11px", fontWeight: 700 }}>
                  {historyMode === "normalized" ? "📊 Нормализованная база" : "🟢 Исторически низкая цена"}
                </div>
              </div>

              {historyMode === "normalized" && (
                <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd", borderRadius: "10px", padding: "10px 14px", marginBottom: "12px", fontSize: "11px", color: "#0369a1" }}>
                  💡 <strong>Эталон 1p / 8n:</strong> исключает искажения состава семьи и дат. Выделена чистая себестоимость ночи в отеле (~<strong>{normalizedData?.stats?.pure_hotel_night_rate || 450} zł/ночь</strong>) и стандартный перелёт.
                </div>
              )}

              <div className="chart-container-box" style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "10px", marginBottom: "16px" }}>
                <div ref={chartContainerRef} id="drawerPlotlyChart" style={{ width: "100%", height: "320px" }} />
              </div>

              <div className="benchmarks-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px", marginBottom: "16px" }}>
                <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                  <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                    {historyMode === "normalized" ? "Текущий эталон" : "Текущая цена"}
                  </div>
                  <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#0f172a", marginTop: "2px" }}>
                    {`${Math.round(rangeStats.cur).toLocaleString("ru-RU")} zł`}
                  </div>
                </div>

                <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                  <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                    {historyMode === "normalized" ? "Мин. эталон" : "Минимум периода"}
                  </div>
                  <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#16a34a", marginTop: "2px" }}>
                    {`${Math.round(rangeStats.min).toLocaleString("ru-RU")} zł`}
                  </div>
                </div>

                <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                  <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                    {historyMode === "normalized" ? "Макс. эталон" : "Максимум периода"}
                  </div>
                  <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#e11d48", marginTop: "2px" }}>
                    {`${Math.round(rangeStats.max).toLocaleString("ru-RU")} zł`}
                  </div>
                </div>

                <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                  <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                    {historyMode === "normalized" ? "Чистая ночь" : "Экономия периода"}
                  </div>
                  <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#2563eb", marginTop: "2px" }}>
                    {historyMode === "normalized" && normalizedData?.stats?.pure_hotel_night_rate != null
                      ? `~${normalizedData.stats.pure_hotel_night_rate} zł/н`
                      : rangeStats.savings > 0 ? `-${Math.round(rangeStats.savings).toLocaleString("ru-RU")} zł` : "0 zł"}
                  </div>
                </div>
              </div>

              {/* German Arbitrage highlight */}
              {passport?.german_arbitrage && passport.german_arbitrage.savings_pln > 0 && (
                <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "10px", padding: "12px 14px", marginBottom: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontSize: "12px", fontWeight: 800, color: "#1e40af" }}>
                        🌍 Арбитраж через Берлин (BER)
                      </div>
                      <div style={{ fontSize: "11px", color: "#3b82f6", marginTop: "2px" }}>
                        Вылет из BER: {passport.german_arbitrage.berlin_price_pln.toLocaleString("ru-RU")} zł ({passport.german_arbitrage.berlin_operator})
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ background: "#2563eb", color: "#ffffff", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                        Экономия {passport.german_arbitrage.savings_pln.toLocaleString("ru-RU")} zł
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Расширенная Инфраструктура */}
          {activeTab === "infra" && (
            <div className="drawer-tab-panel active" id="tabPanel-infra">
              {(() => {
                const ir = passport?.infra_rich || {};
                const b = ir.beach || {};
                const p = ir.pools || {};
                const f = ir.food || ir.dining || {};
                const k = ir.kids || {};
                const s = ir.sport_spa || ir.spa_sport || {};
                const c = ir.comfort || {};

                return (
                  <div className="infra-rich-grid">
                    {/* 1. Beach */}
                    <div className="infra-cat-card">
                      <div className="infra-cat-header">
                        <span>🏖️</span>
                        <h4>Пляж и море</h4>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Линия и берег</span>
                        <span className="infra-item-val">
                          {b.line || (passport?.beach_line ? `${passport.beach_line}-я линия` : "1-я линия")}, {b.type || passport?.beach_type || "Собственный пляж"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Заход в море</span>
                        <span className="infra-item-val">
                          {b.entry || passport?.sea_entry || "Пологий песчаный вход"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Оснащение пляжа</span>
                        <span className="infra-item-val">
                          {b.equipment || b.facilities || "Шезлонги, зонтики и бар на пляже бесплатно"}
                        </span>
                      </div>
                    </div>

                    {/* 2. Pools */}
                    <div className="infra-cat-card">
                      <div className="infra-cat-header">
                        <span>🏊</span>
                        <h4>Бассейны и водные горки</h4>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Открытые бассейны</span>
                        <span className="infra-item-val">
                          {p.pools_count || "Несколько открытых бассейнов с пресной водой"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Подогрев</span>
                        <span className="infra-item-val">
                          {p.heated || (passport?.has_heated_pools ? "Бассейн с подогревом в прохладный сезон" : "Бассейны без подогрева")}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Аквапарк</span>
                        <span className="infra-item-val">
                          {p.aquapark || (passport?.has_aquapark ? "Водные горки для взрослых и детей" : "Без водных горок")}
                        </span>
                      </div>
                    </div>

                    {/* 3. Food */}
                    <div className="infra-cat-card">
                      <div className="infra-cat-header">
                        <span>🍽️</span>
                        <h4>Питание и рестораны</h4>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Концепция</span>
                        <span className="infra-item-val">
                          <strong>{f.concept || passport?.food_concept || "All Inclusive"}</strong>
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Главный ресторан</span>
                        <span className="infra-item-val">
                          {f.main_buffet || f.main_restaurant || "Шведский стол, блюда международной кухни, гриль"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">A la Carte и бары</span>
                        <span className="infra-item-val">
                          {f.alacarte || f.bars || "Рестораны a la carte, лобби-бар и бар у бассейна"}
                        </span>
                      </div>
                    </div>

                    {/* 4. Kids */}
                    <div className="infra-cat-card">
                      <div className="infra-cat-header">
                        <span>👶</span>
                        <h4>Для детей и семей</h4>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Мини-клуб</span>
                        <span className="infra-item-val">
                          {k.club || k.miniclub || "Детский клуб от 4 до 12 лет с аниматорами"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Детский бассейн</span>
                        <span className="infra-item-val">
                          {k.pool || "Мелкий детский бассейн с навесом от солнца"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Площадка и сервис</span>
                        <span className="infra-item-val">
                          {k.playground || k.services || "Игровая площадка, стульчики и детское меню"}
                        </span>
                      </div>
                    </div>

                    {/* 5. Sport & Spa */}
                    <div className="infra-cat-card">
                      <div className="infra-cat-header">
                        <span>💆</span>
                        <h4>Спа, спорт и активности</h4>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Спа-центр</span>
                        <span className="infra-item-val">
                          {s.spa || "Сауна, турецкий хаммам, джакузи и массаж"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Фитнес и спорт</span>
                        <span className="infra-item-val">
                          {s.fitness || s.sport || "Тренажерный зал, пляжный волейбол, аэробика"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Водные виды</span>
                        <span className="infra-item-val">
                          {s.watersports || "Снорклинг, прокат инвентаря, водные развлечения"}
                        </span>
                      </div>
                    </div>

                    {/* 6. Comfort & Service */}
                    <div className="infra-cat-card">
                      <div className="infra-cat-header">
                        <span>🌐</span>
                        <h4>Удобства и сервис</h4>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Интернет Wi-Fi</span>
                        <span className="infra-item-val">
                          {c.wifi || "Бесплатный Wi-Fi на территории и в номерах"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Номера</span>
                        <span className="infra-item-val">
                          {c.room_amenities || c.rooms || "Кондиционер, сейф, балкон/терраса, мини-бар"}
                        </span>
                      </div>
                      <div className="infra-item-line">
                        <span className="infra-item-lbl">Трансфер и сервис</span>
                        <span className="infra-item-val">
                          {c.distance || c.transfer || "Круглосуточная стойка регистрации, трансфер ~30 мин"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* TAB 4: Все вылеты и фильтры */}
          {activeTab === "packages" && (
            <div className="drawer-tab-panel active" id="tabPanel-packages">
              <div id="drawerPackagesCount" style={{ marginBottom: "10px", fontSize: "0.84rem", fontWeight: 700, color: "#0f172a" }}>
                Вылеты в текущем фильтре:
              </div>

              <div style={{ overflowX: "auto", marginBottom: "20px" }}>
                <table className="packages-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                  <thead>
                    <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0", textAlign: "left" }}>
                      <th style={{ padding: "8px 12px" }}>Даты поездки</th>
                      <th style={{ padding: "8px 12px" }}>Длит.</th>
                      <th style={{ padding: "8px 12px" }}>Аэропорт</th>
                      <th style={{ padding: "8px 12px" }}>Цена</th>
                      <th style={{ padding: "8px 12px" }}>Бронь</th>
                    </tr>
                  </thead>
                  <tbody id="drawerPackagesTbody">
                    {(passport?.available_packages || [
                      {
                        checkin_date: "2026-11-14",
                        checkout_date: "2026-11-24",
                        duration_nights: 10,
                        airport_code: "WAW",
                        total_price_pln: currentPrice,
                        booking_url: "https://fly.pl",
                      },
                      {
                        checkin_date: "2026-11-17",
                        checkout_date: "2026-11-24",
                        duration_nights: 7,
                        airport_code: "WAW",
                        total_price_pln: Math.round(currentPrice * 0.82),
                        booking_url: "https://fly.pl",
                      },
                    ]).map((pkg: any, idx: number) => (
                      <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                        <td style={{ padding: "8px 12px", fontWeight: 600 }}>{pkg.checkin_date} – {pkg.checkout_date}</td>
                        <td style={{ padding: "8px 12px" }}>{pkg.duration_nights}н</td>
                        <td style={{ padding: "8px 12px" }}>{pkg.airport_code}</td>
                        <td style={{ padding: "8px 12px", fontWeight: 700, color: "#0f172a" }}>
                          {pkg.total_price_pln.toLocaleString("ru-RU")} zł
                        </td>
                        <td style={{ padding: "8px 12px" }}>
                          <a
                            href={pkg.booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: "inline-block",
                              background: "#0284c7",
                              color: "#fff",
                              padding: "4px 10px",
                              borderRadius: "6px",
                              textDecoration: "none",
                              fontWeight: 700,
                            }}
                          >
                            Бронь ↗
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
