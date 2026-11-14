import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  X,
  ExternalLink,
  Star,
  Play,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { HotelPassport, SearchHotelItem } from "../types";
import { getHotelPassport, getHotelNormalizedHistory } from "../services/api";
import { FILTER_PRESETS } from "../constants/presets";
import { LoadingSpinner } from "./common/LoadingSpinner";

declare global {
  interface Window {
    Plotly?: any;
  }
}

interface HotelPassportDrawerProps {
  hotelId: string | null;
  filterId?: string | null;
  hotelItem?: SearchHotelItem | null;
  searchTravelers?: { adults: number; children: number; children_ages?: number[] };
  isWatched?: boolean;
  onToggleWatchlist?: () => void;
  onClose: () => void;
  onSwitchFilter?: (filterId: string) => void;
}

export const HotelPassportDrawer: React.FC<HotelPassportDrawerProps> = ({
  hotelId,
  filterId,
  hotelItem,
  searchTravelers,
  isWatched,
  onToggleWatchlist,
  onClose,
  onSwitchFilter,
}) => {
  const [passport, setPassport] = useState<HotelPassport | null>(null);
  const [historyRange, setHistoryRange] = useState<"7d" | "30d" | "all">("all");
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

    const filterPreset = filterId ? FILTER_PRESETS[filterId] : undefined;
    const is1pExplicit = Boolean(
      (filterId && (filterId.includes("1p") || filterId.includes("_1_adult"))) ||
      (searchTravelers && searchTravelers.adults === 1 && (!searchTravelers.children || searchTravelers.children === 0)) ||
      (passport?.user_query_scope && passport.user_query_scope.adults === 1 && (!passport.user_query_scope.children || passport.user_query_scope.children === 0))
    );
    const fallbackAdults = is1pExplicit
      ? 1
      : (searchTravelers?.adults ??
         filterPreset?.searchReq?.travelers?.adults ??
         passport?.user_query_scope?.adults ??
         hotelItem?.current_offer?.adults ??
         2);
    const fallbackChildren = is1pExplicit
      ? 0
      : (searchTravelers?.children ??
         filterPreset?.searchReq?.travelers?.children ??
         passport?.user_query_scope?.children ??
         hotelItem?.current_offer?.children ??
         0);
    const fallbackNights =
      hotelItem?.current_offer?.duration_nights ??
      filterPreset?.searchReq?.duration?.min_nights ??
      7;

    const hints = hotelItem
      ? {
          name: hotelItem.hotel_name,
          stars: hotelItem.stars,
          country: hotelItem.country,
          region: hotelItem.region,
          current_price: hotelItem.current_offer?.total_price_pln,
          ta_rating: hotelItem.ta_rating,
          main_image_url: hotelItem.main_image_url,
          adults: fallbackAdults,
          children: fallbackChildren,
          duration_nights: fallbackNights,
        }
      : {
          adults: fallbackAdults,
          children: fallbackChildren,
          duration_nights: fallbackNights,
        };

    getHotelPassport(hotelId, filterId || undefined, hints)
      .then((data) => setPassport(data))
      .catch((err) => console.error("Failed to load hotel passport:", err))
      .finally(() => setIsLoading(false));
  }, [hotelId, filterId, hotelItem, searchTravelers]);

  const filterPreset = filterId ? FILTER_PRESETS[filterId] : undefined;
  const is1pExplicit = Boolean(
    (filterId && (filterId.includes("1p") || filterId.includes("_1_adult"))) ||
    (searchTravelers && searchTravelers.adults === 1 && (!searchTravelers.children || searchTravelers.children === 0)) ||
    (passport?.user_query_scope && passport.user_query_scope.adults === 1 && (!passport.user_query_scope.children || passport.user_query_scope.children === 0))
  );

  const resolvedAdults = is1pExplicit
    ? 1
    : (searchTravelers?.adults ??
       filterPreset?.searchReq?.travelers?.adults ??
       passport?.user_query_scope?.adults ??
       hotelItem?.current_offer?.adults ??
       2);

  const resolvedChildren = is1pExplicit
    ? 0
    : (searchTravelers?.children ??
       filterPreset?.searchReq?.travelers?.children ??
       passport?.user_query_scope?.children ??
       hotelItem?.current_offer?.children ??
       0);

  const resolvedNights =
    hotelItem?.current_offer?.duration_nights ||
    passport?.user_query_scope?.duration_nights ||
    filterPreset?.searchReq?.duration?.min_nights ||
    7;

  const partyLabel =
    resolvedAdults === 1 && resolvedChildren === 0
      ? "1 взр"
      : `${resolvedAdults} взр` + (resolvedChildren > 0 ? ` + ${resolvedChildren} реб` : "");

  // Render Plotly Price History Chart when history tab is activated
  useEffect(() => {
    if (activeTab !== "history" || !passport || !chartContainerRef.current || !window.Plotly) {
      return;
    }

    // Real Tour History
    const allHistory = passport.history_points || [];
    if (!allHistory.length || passport.data_maturity_tier === 0) {
      window.Plotly.purge(chartContainerRef.current);
      return;
    }

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

    const filterPreset = filterId ? FILTER_PRESETS[filterId] : undefined;
    const is1pFilter = Boolean(filterId && (filterId.includes("1p") || filterId.includes("_1_adult")));
    const userAdults =
      searchTravelers?.adults ??
      filterPreset?.searchReq?.travelers?.adults ??
      (is1pFilter ? 1 : undefined) ??
      passport?.user_query_scope?.adults ??
      hotelItem?.current_offer?.adults ??
      1;
    const userChildren =
      searchTravelers?.children ??
      filterPreset?.searchReq?.travelers?.children ??
      (is1pFilter ? 0 : undefined) ??
      passport?.user_query_scope?.children ??
      hotelItem?.current_offer?.children ??
      0;
    const userNights =
      hotelItem?.current_offer?.duration_nights ||
      passport?.user_query_scope?.duration_nights ||
      filterPreset?.searchReq?.duration?.min_nights ||
      7;
    const partyLabel = userAdults === 1 && !userChildren ? "1 взр" : (`${userAdults} взр` + (userChildren > 0 ? ` + ${userChildren} реб` : ""));

    // Deduplicate timestamps to prevent duplicate x-axis points
    const uniqueMap = new Map<string, { price: number; perNightPax: number }>();
    const totalPax = Math.max(1, resolvedAdults + resolvedChildren);
    history.forEach((pt) => {
      const isExactParty = pt.adults === resolvedAdults && (pt.children || 0) === resolvedChildren;
      const p = isExactParty ? pt.total_price_pln : (pt.scaled_tour_price || pt.total_price_pln);
      const perNight = Math.round(p / (resolvedNights * totalPax));
      uniqueMap.set(pt.recorded_at, {
        price: p,
        perNightPax: perNight,
      });
    });

    const xVals: string[] = [];
    const yVals: number[] = [];
    const customData: number[] = [];
    uniqueMap.forEach((val, key) => {
      xVals.push(key);
      yVals.push(val.price);
      customData.push(val.perNightPax);
    });

    const trace = {
      x: xVals,
      y: yVals,
      customdata: customData,
      type: "scatter",
      mode: "lines+markers",
      name: `Цена тура (${partyLabel} • ${userNights}н)`,
      line: {
        color: "#0284c7",
        width: 2.5,
        shape: "linear",
      },
      marker: {
        size: 5,
        color: "#0369a1",
      },
      hovertemplate:
        "<b>%{y:,.0f} zł</b> (Цена всего тура)<br>~%{customdata:,.0f} zł / чел / ночь<br>%{x|%d.%m %H:%M}<extra></extra>",
    };

    const pVals = yVals.length ? yVals : [passport.current_price_pln];
    const minPrice = Math.min(...pVals);
    const sortedP = [...pVals].sort((a, b) => a - b);
    const medianPrice = sortedP[Math.floor(sortedP.length / 2)] || minPrice;

    const layout = {
      title: {
        text: `Динамика цены тура (${partyLabel} • ${userNights} ночей, с перелётом)`,
        font: { size: 12.5, family: "Inter, sans-serif", color: "#0f172a" },
        x: 0.05,
      },
      margin: { l: 55, r: 25, t: 40, b: 40 },
      height: 320,
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      xaxis: {
        type: "date",
        gridcolor: "#f1f5f9",
        tickfont: { size: 10, color: "#64748b" },
      },
      yaxis: {
        title: "Цена тура (PLN)",
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

    try {
      window.Plotly.react(chartContainerRef.current, [trace], layout, config);
    } catch (e) {
      console.warn("Plotly tour chart error:", e);
    }
  }, [activeTab, passport, historyRange]);

  const genericPlaceholder =
    "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=800&q=80";

  // Filter out any generic unsplash placeholder URLs that might be present in cached data
  const realGalleryPhotos = (passport?.gallery_photos || []).filter(
    (url) =>
      url &&
      !url.includes("images.unsplash.com/photo-1566073771259") &&
      !url.includes("images.unsplash.com/photo-1582719478250") &&
      !url.includes("images.unsplash.com/photo-1571896349842") &&
      !url.includes("images.unsplash.com/photo-1540555700478")
  );

  const primaryPhoto =
    hotelItem?.main_image_url ||
    passport?.main_image_url ||
    (realGalleryPhotos.length ? realGalleryPhotos[0] : "");

  const photos = primaryPhoto
    ? [primaryPhoto, ...realGalleryPhotos.filter((p) => p !== primaryPhoto)]
    : realGalleryPhotos.length
    ? realGalleryPhotos
    : [genericPlaceholder];

  const handleNextPhoto = (e: React.MouseEvent) => {
    e.stopPropagation();
    setActivePhotoIdx((prev) => (prev + 1) % photos.length);
  };

  const handlePrevPhoto = (e: React.MouseEvent) => {
    e.stopPropagation();
    setActivePhotoIdx((prev) => (prev - 1 + photos.length) % photos.length);
  };

  const currentPrice = hotelItem?.current_offer?.total_price_pln || passport?.current_price_pln || 0;
  const minPrice = hotelItem?.intelligence?.historic_min_pln || passport?.all_time_min_pln || 0;
  const maxPrice = passport?.all_time_max_pln || 0;

// rangeStats uses resolvedAdults and resolvedChildren

  // Dynamic values depending on active filter range (7d / 30d / all)
  const rangeStats = useMemo(() => {
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
    const pVals = hist.map((p) => {
      const isExactParty = p.adults === resolvedAdults && (p.children || 0) === resolvedChildren;
      return isExactParty ? p.total_price_pln : (p.scaled_tour_price || p.total_price_pln);
    });
    const lastPt = hist.length > 0 ? hist[hist.length - 1] : null;
    const cur = pVals.length > 0 ? pVals[pVals.length - 1] : currentPrice;
    const min = pVals.length > 0 ? Math.min(...pVals) : cur;
    const max = pVals.length > 0 ? Math.max(...pVals) : cur;
    const sorted = [...pVals].sort((a, b) => a - b);
    const med = sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)] : cur;
    const pureNight = lastPt?.pure_hotel_night_rate || 0;
    return { cur, min, med, max, pureNight, count: hist.length };
  }, [historyRange, passport?.history_points, currentPrice, resolvedAdults, resolvedChildren]);

  const currentTaRating = hotelItem?.ta_rating ?? passport?.ta_rating;
  const isBudgetQuality =
    currentTaRating !== undefined &&
    currentTaRating !== null &&
    currentTaRating > 0 &&
    currentTaRating < 3.5;

  // Real, meaningful savings vs median (safeguarded against party/duration scale mismatch and seasonal bias)
  const typicalPrice = hotelItem?.intelligence?.typical_median_pln || passport?.typical_median_pln || rangeStats.med;
  const savingsVsMedian =
    !isBudgetQuality && typicalPrice > 0 && currentPrice < typicalPrice
      ? typicalPrice - currentPrice
      : 0;

  let savingsBadgeText: string | null = null;
  if (!isBudgetQuality && savingsVsMedian >= 50 && savingsVsMedian < typicalPrice * 0.35) {
    savingsBadgeText = `↓ на ${Math.round(savingsVsMedian).toLocaleString("ru-RU")} zł ниже типичной`;
  } else if (!isBudgetQuality && hotelItem?.intelligence?.drop_48h_pct && hotelItem.intelligence.drop_48h_pct < -2) {
    savingsBadgeText = `↓ на ${Math.abs(Math.round(hotelItem.intelligence.drop_48h_pct))}% за 48ч`;
  }

  // Ensure AI Price summary strictly matches bold currentPrice and hotel quality
  const dynamicPriceSummary = useMemo(() => {
    if (isBudgetQuality) {
      return `Текущая цена ${Math.round(currentPrice).toLocaleString("ru-RU")} zł обусловлена скромным классом отеля (TripAdvisor ${currentTaRating}★). Низкий тариф отражает уровень сервиса и удобств, а не аномальную скидку.`;
    }
    if (hotelItem?.intelligence?.recommendation) {
      return hotelItem.intelligence.recommendation;
    }
    if (passport?.ai_price_summary && currentPrice > 0) {
      return passport.ai_price_summary.replace(
        /Текущая цена\s+[\d\s\u00a0,.]+\s*(?:zł|pln)/gi,
        `Текущая цена ${Math.round(currentPrice).toLocaleString("ru-RU")} zł`
      );
    }
    return currentPrice > 0
      ? `Текущая цена ${Math.round(currentPrice).toLocaleString("ru-RU")} zł соответствует справедливой рыночной оценке.`
      : "";
  }, [passport?.ai_price_summary, currentPrice, isBudgetQuality, currentTaRating, hotelItem?.intelligence?.recommendation]);

  const currentDealScore = isBudgetQuality
    ? Math.min(62, hotelItem?.intelligence?.deal_score ?? passport?.deal_score ?? 60)
    : hotelItem?.intelligence?.deal_score ?? passport?.deal_score ?? 80;

  const isBuySignal =
    !isBudgetQuality &&
    (currentDealScore >= 80 ||
      passport?.hopper_verdict === "BUY" ||
      passport?.hopper_verdict === "BUY NOW" ||
      passport?.hopper_verdict === "ПОКУПАТЬ" ||
      hotelItem?.intelligence?.hopper_verdict === "ПОКУПАТЬ");
  const isOverpricedSignal =
    currentDealScore < 45 ||
    passport?.hopper_verdict === "OVERPRICED" ||
    hotelItem?.intelligence?.hopper_verdict === "ДОРОГО";

  let dealScoreBadgeText = "";
  if (isBudgetQuality) dealScoreBadgeText = "🏷️ Budget";
  else if (currentDealScore >= 85) dealScoreBadgeText = "🔥 Hot";
  else if (currentDealScore >= 70) dealScoreBadgeText = "✅ Good";
  else if (currentDealScore < 45) dealScoreBadgeText = "📈 Bad";

  const verdictBadgeText = isBudgetQuality
    ? "🟡 БЮДЖЕТ"
    : isBuySignal
    ? "🟢 ПОКУПАТЬ"
    : isOverpricedSignal
    ? "🔴 ДОРОГО"
    : "↔ СТАБИЛЬНО";
  const verdictBadgeBg = isBudgetQuality
    ? "#fef9c3"
    : isBuySignal
    ? "#ecfdf5"
    : isOverpricedSignal
    ? "#fef2f2"
    : "#f1f5f9";
  const verdictBadgeColor = isBudgetQuality
    ? "#854d0e"
    : isBuySignal
    ? "#065f46"
    : isOverpricedSignal
    ? "#991b1b"
    : "#334155";

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
        {isLoading && (
          <LoadingSpinner
            variant="overlay"
            size="xl"
            label="Загрузка паспорта отеля..."
            description="Синхронизация истории цен, параметров инфраструктуры и отзывов TripAdvisor"
            className="z-50 !bg-white/95"
          />
        )}
        {/* Header */}
        <div className="drawer-header">
          <div className="drawer-title-box">
            <div className="drawer-title-row">
              <h2 id="drawerHotelTitle">
                {hotelItem?.hotel_name || passport?.display_name || "Отель"}
              </h2>
              <span className="hotel-stars" id="drawerStarsRow">
                {"★".repeat(hotelItem?.stars || passport?.stars || 4)}
              </span>
            </div>
            <p id="drawerHotelSubtitle">
              {(() => {
                const c = passport?.country || hotelItem?.country || "Курорт";
                const r = passport?.region || hotelItem?.region;
                if (!r || r === c) {
                  return c;
                }
                return `${c} • ${r}`;
              })()}
            </p>
          </div>

          <div className="drawer-header-actions">
            {onToggleWatchlist && (
              <button
                type="button"
                onClick={onToggleWatchlist}
                id="drawerHeaderFavBtn"
                className={`px-3 py-1.5 rounded-lg border text-[12.5px] font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                  isWatched
                    ? "bg-amber-500 hover:bg-amber-600 text-white border-amber-600 shadow-xs"
                    : "bg-white hover:bg-amber-50 text-slate-700 hover:text-amber-600 border-slate-200"
                }`}
                title={isWatched ? "Удалить из избранного" : "Добавить в избранное"}
              >
                <Star className={`w-3.5 h-3.5 ${isWatched ? "fill-white text-white" : "text-amber-500 fill-amber-400"}`} />
                <span>{isWatched ? "В избранном" : "В избранное"}</span>
              </button>
            )}
            {(passport?.tripadvisor_url || hotelItem?.hotel_name) && (
              <a
                className="btn-drawer-header-ta"
                href={
                  passport?.tripadvisor_url ||
                  `https://www.tripadvisor.com/Search?q=${encodeURIComponent((hotelItem?.hotel_name || passport?.display_name || "") + " hotel review")}`
                }
                target="_blank"
                rel="noopener noreferrer"
                id="drawerHeaderTaLink"
                title="Открыть отзывы на TripAdvisor"
              >
                🦉 TripAdvisor ↗
              </a>
            )}
            {(passport?.youtube_search_url || hotelItem?.hotel_name) && (
              <a
                className="btn-drawer-header-yt"
                href={
                  passport?.youtube_search_url ||
                  `https://www.youtube.com/results?search_query=${encodeURIComponent((hotelItem?.hotel_name || passport?.display_name || "") + " обзор отеля")}`
                }
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
                  Deal Score {currentDealScore}/100 {dealScoreBadgeText}
                </span>
                <span className="badge" style={{ background: verdictBadgeBg, color: verdictBadgeColor, padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                  {verdictBadgeText}
                </span>
                <span className="badge" style={{ background: "#fef3c7", color: "#92400e", padding: "3px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 700 }}>
                  TripAdvisor {currentTaRating ? `★ ${currentTaRating}` : "★ 4.5"}
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
                  <div
                    className="oracle-deal-pill"
                    id="drawerOraclePriceBadge"
                    style={{
                      background: isBudgetQuality ? "#fef9c3" : isBuySignal ? "#dcfce7" : isOverpricedSignal ? "#fee2e2" : "#f1f5f9",
                      color: isBudgetQuality ? "#854d0e" : isBuySignal ? "#15803d" : isOverpricedSignal ? "#b91c1c" : "#475569",
                      fontWeight: 700,
                      padding: "4px 10px",
                      borderRadius: "20px",
                      fontSize: "11px",
                    }}
                  >
                    {isBudgetQuality ? "🟡 Бюджетный класс" : isBuySignal ? "🟢 Выгодно брать" : isOverpricedSignal ? "🔴 Дорого" : "↔ Нормальная цена"}
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
                      {savingsBadgeText && (
                        <span className="oracle-diff-pill" id="drawerOraclePriceDiff" style={{ background: "#dcfce7", color: "#166534", fontSize: "11px", fontWeight: 700, padding: "2px 6px", borderRadius: "6px" }}>
                          {savingsBadgeText}
                        </span>
                      )}
                    </div>
                    <p className="oracle-body-text" id="drawerAiPriceVerdictText" style={{ fontSize: "12px", color: "#334155", lineHeight: "1.5", marginTop: "4px" }}>
                      {dynamicPriceSummary}
                    </p>
                    <div className="oracle-meta-line" style={{ marginTop: "8px", fontSize: "11px" }}>
                      <span className="oracle-meta-lbl" style={{ color: "#64748b" }}>🔮 Сигнал Hopper: </span>
                      <span
                        className="oracle-meta-val"
                        id="drawerAiActionSignal"
                        style={{
                          fontWeight: 700,
                          color: isBudgetQuality ? "#854d0e" : isBuySignal ? "#15803d" : isOverpricedSignal ? "#b91c1c" : "#475569",
                        }}
                      >
                        {hotelItem?.intelligence?.recommendation ||
                          passport?.ai_action_signal ||
                          (isBudgetQuality
                            ? "Следить за ценой (эконом-класс)"
                            : isBuySignal
                            ? "Покупать сейчас"
                            : isOverpricedSignal
                            ? "Ждать снижения"
                            : "Следить за ценой")}
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
                  href={
                    passport?.tripadvisor_url ||
                    `https://www.tripadvisor.com/Search?q=${encodeURIComponent((hotelItem?.hotel_name || passport?.display_name || "") + " hotel review")}`
                  }
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
                    ★ {passport?.ta_rating || hotelItem?.ta_rating || "4.5"}
                  </div>
                </a>

                <a
                  className="ext-review-card"
                  href={`https://www.google.com/search?q=${encodeURIComponent((hotelItem?.hotel_name || passport?.display_name || "") + " отзывы")}`}
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

              {/* Other Filters Callout if hotel exists elsewhere */}
              {passport?.other_filters && passport.other_filters.length > 0 && (
                <div
                  style={{
                    marginTop: "16px",
                    background: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: "12px",
                    padding: "12px 16px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "8px",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "12px", fontWeight: 700, color: "#166534" }}>
                      📂 Отель также отслеживается в {passport.other_filters.length} {passport.other_filters.length === 1 ? "другом фильтре" : "других фильтрах"}
                    </div>
                    <div style={{ fontSize: "11px", color: "#15803d", marginTop: "2px" }}>
                      Лучшая цена: от {Math.min(...passport.other_filters.map((f) => f.min_price_pln)).toLocaleString("ru-RU")} zł
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab("packages")}
                    style={{
                      background: "#16a34a",
                      color: "#fff",
                      border: "none",
                      padding: "6px 12px",
                      borderRadius: "6px",
                      fontSize: "11px",
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    Посмотреть варианты ({passport.other_filters.length}) →
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: График Plotly и Аналитика */}
          {activeTab === "history" && (
            <div className="drawer-tab-panel active" id="tabPanel-history">
              {(() => {
                const filterPreset = filterId ? FILTER_PRESETS[filterId] : undefined;
                const is1pFilter = Boolean(filterId && (filterId.includes("1p") || filterId.includes("_1_adult")));
                const userAdults =
                  searchTravelers?.adults ??
                  filterPreset?.searchReq?.travelers?.adults ??
                  (is1pFilter ? 1 : undefined) ??
                  passport?.user_query_scope?.adults ??
                  hotelItem?.current_offer?.adults ??
                  1;
                const userChildren =
                  searchTravelers?.children ??
                  filterPreset?.searchReq?.travelers?.children ??
                  (is1pFilter ? 0 : undefined) ??
                  passport?.user_query_scope?.children ??
                  hotelItem?.current_offer?.children ??
                  0;
                const userNights =
                  hotelItem?.current_offer?.duration_nights ||
                  passport?.user_query_scope?.duration_nights ||
                  filterPreset?.searchReq?.duration?.min_nights ||
                  7;
                const partyLabel = userAdults === 1 && !userChildren ? "1 взр" : (`${userAdults} взр` + (userChildren > 0 ? ` + ${userChildren} реб` : ""));
                const depStr = hotelItem?.current_offer?.departure_date || (passport?.history_points?.length ? passport.history_points[passport.history_points.length - 1].departure_date : null);
                let targetMonthLabel = "сезон";
                if (depStr) {
                  try {
                    const d = new Date(depStr);
                    targetMonthLabel = d.toLocaleString("ru-RU", { month: "short" });
                  } catch {}
                }

                return (
                  <>
                    <div className="chart-controls-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", flexWrap: "wrap", gap: "8px" }}>
                      <div className="stat-pill" style={{ background: "#e0f2fe", color: "#0369a1", padding: "6px 14px", borderRadius: "20px", fontSize: "12px", fontWeight: 700, border: "1px solid #bae6fd" }}>
                        ✈️ Полная цена тура ({partyLabel} • {resolvedNights}н, с перелётом)
                      </div>

                      {/* Range Selector */}
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
                    </div>

                    {/* Explanatory banner */}
                    <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "10px", padding: "10px 14px", marginBottom: "14px", fontSize: "12px", color: "#475569", lineHeight: "1.5" }}>
                      <div>
                        💡 <strong>История стоимости пакета:</strong> график отражает реальную динамику цены всего тура (перелёт туда-обратно + проживание All Inclusive + трансфер) для вашего состава семьи ({partyLabel} • {resolvedNights}н). Учитывает все скидки туроператора и горящие места в чартерах.
                      </div>
                      {hotelItem?.current_offer?.departure_date && (
                        <div style={{ marginTop: "6px", fontSize: "11px", color: "#0369a1", background: "#f0f9ff", padding: "4px 8px", borderRadius: "6px", border: "1px solid #e0f2fe" }}>
                          ℹ️ Текущий live-поиск: вылет <strong>{hotelItem.current_offer.departure_date}</strong> ({resolvedNights}н) • {currentPrice.toLocaleString("ru-RU")} zł.
                        </div>
                      )}
                    </div>

                    {/* Chart container or friendly empty state */}
                    {(!passport?.history_points || passport.history_points.length <= 1 || passport?.data_maturity_tier === 0) ? (
                      <div style={{ background: "#f8fafc", border: "1.5px dashed #cbd5e1", borderRadius: "16px", padding: "32px 20px", textAlign: "center", marginBottom: "16px" }}>
                        <div style={{ fontSize: "36px", marginBottom: "8px" }}>📊</div>
                        <h4 style={{ fontSize: "15px", fontWeight: 800, color: "#0f172a", marginBottom: "6px" }}>
                          Мониторинг запущен: первый замер зафиксирован
                        </h4>
                        <p style={{ fontSize: "12px", color: "#64748b", maxWidth: "480px", margin: "0 auto 12px", lineHeight: "1.5" }}>
                          {passport?.maturity_explanation || "Отель обнаружен через расширенный live-поиск. Зафиксирована первая котировка тура, регулярный почасовой мониторинг цен запущен. График динамики будет построен после сбора повторных котировок."}
                        </p>
                        <div style={{ display: "inline-flex", alignItems: "center", gap: "8px", background: "#f1f5f9", padding: "6px 14px", borderRadius: "20px", fontSize: "11.5px", color: "#334155", fontWeight: 700 }}>
                          <span>⏱️ Следующий автоматический замер: в течение 60 мин.</span>
                          <span>•</span>
                          <span>Текущая цена тура: {Math.round(currentPrice).toLocaleString("ru-RU")} zł</span>
                        </div>
                      </div>
                    ) : (
                      <div className="chart-container-box" style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "10px", marginBottom: "16px" }}>
                        <div ref={chartContainerRef} id="drawerPlotlyChart" style={{ width: "100%", height: "320px" }} />
                      </div>
                    )}

                    <div className="benchmarks-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "10px", marginBottom: "16px" }}>
                      <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                        <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                          Текущая цена тура
                        </div>
                        <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#0f172a", marginTop: "2px" }}>
                          {rangeStats.cur > 0 ? `${Math.round(rangeStats.cur).toLocaleString("ru-RU")} zł` : "—"}
                        </div>
                      </div>

                      <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                        <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                          Минимум за период
                        </div>
                        <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#16a34a", marginTop: "2px" }}>
                          {rangeStats.min > 0 ? `${Math.round(rangeStats.min).toLocaleString("ru-RU")} zł` : "—"}
                        </div>
                      </div>

                      <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                        <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                          Сезонная норма ({targetMonthLabel})
                        </div>
                        <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#0284c7", marginTop: "2px" }}>
                          {(passport?.typical_median_pln || rangeStats.med) > 0 ? `${Math.round(passport?.typical_median_pln || rangeStats.med).toLocaleString("ru-RU")} zł` : "—"}
                        </div>
                      </div>

                      <div className="benchmark-card" style={{ background: "#f8fafc", border: "1px solid #e2e8f0", padding: "10px", borderRadius: "10px", textAlign: "center" }}>
                        <div className="lbl" style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase" }}>
                          Максимум за период
                        </div>
                        <div className="val" style={{ fontSize: "15px", fontWeight: 800, color: "#e11d48", marginTop: "2px" }}>
                          {rangeStats.max > 0 ? `${Math.round(rangeStats.max).toLocaleString("ru-RU")} zł` : "—"}
                        </div>
                      </div>
                    </div>
                  </>
                );
              })()}

              {/* Cross-Filter callout in Tab 2 */}
              {passport?.other_filters && passport.other_filters.length > 0 && (
                <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "14px 16px", marginBottom: "16px" }}>
                  <div style={{ fontSize: "12.5px", fontWeight: 700, color: "#1e293b", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                    <span>💡</span>
                    <span>Справочно: история отеля в других фильтрах</span>
                  </div>
                  <p style={{ fontSize: "11px", color: "#64748b", marginBottom: "10px", lineHeight: "1.4" }}>
                    В других радарах по этому отелю накоплена подробная история цен, которую можно использовать как рыночный ориентир:
                  </p>
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {passport.other_filters.map((f, idx) => (
                      <div key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", background: "#ffffff", padding: "8px 12px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                        <div>
                          <div style={{ fontSize: "12px", fontWeight: 700, color: "#0f172a" }}>
                            {f.title || f.filter_id} <span style={{ fontSize: "10.5px", fontWeight: 600, color: "#64748b" }}>({f.party_str || "Стандарт"} • {f.duration_nights || 7}н)</span>
                          </div>
                          <div style={{ fontSize: "11px", color: "#16a34a", fontWeight: 600, marginTop: "2px" }}>
                            Цены: от {Math.round(f.min_price_pln).toLocaleString("ru-RU")} zł до {Math.round(f.max_price_pln).toLocaleString("ru-RU")} zł <span style={{ color: "#64748b", fontWeight: 400 }}>({f.snaps_count} замеров)</span>
                          </div>
                        </div>
                        {onSwitchFilter && (
                          <button
                            type="button"
                            onClick={() => {
                              onSwitchFilter(f.filter_id);
                              onClose();
                            }}
                            style={{ background: "#0ea5e9", color: "#ffffff", border: "none", padding: "5px 10px", borderRadius: "6px", fontSize: "11px", fontWeight: 700, cursor: "pointer" }}
                          >
                            Посмотреть график →
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* German Arbitrage highlight: ONLY shown when a verified specific offer URL exists and has real savings */}
              {passport?.german_arbitrage &&
                passport.german_arbitrage.savings_pln > 0 &&
                passport.german_arbitrage.booking_url &&
                !passport.german_arbitrage.booking_url.includes("/suche/?q=") &&
                (!passport.german_arbitrage.booking_url.includes("check24") ||
                  !passport.german_arbitrage.booking_url.endsWith("hotelId=")) && (
                <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: "12px", padding: "14px 16px", marginBottom: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "10px" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        <span style={{ fontSize: "16px" }}>🇩🇪</span>
                        <span style={{ fontSize: "13px", fontWeight: 800, color: "#1e40af" }}>
                          Арбитраж через Берлин (BER)
                        </span>
                        <span style={{ background: "#2563eb", color: "#ffffff", padding: "2px 8px", borderRadius: "6px", fontSize: "11px", fontWeight: 800 }}>
                          Выгода {passport.german_arbitrage.savings_pln.toLocaleString("ru-RU")} zł
                        </span>
                      </div>
                      <div style={{ fontSize: "12px", color: "#3b82f6", marginTop: "4px" }}>
                        Вылет из BER: <strong>{passport.german_arbitrage.berlin_price_pln.toLocaleString("ru-RU")} zł</strong> ({passport.german_arbitrage.berlin_operator || "Check24 / TUI Deutschland"})
                      </div>
                      <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                        🚆 {passport.german_arbitrage.train_transfer_from_pl || "PKP Intercity Варшава/Познань -> Berlin Hbf"}
                      </div>
                    </div>
                    <div>
                      <a
                        href={passport.german_arbitrage.booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          background: "#034ea2",
                          color: "#ffffff",
                          padding: "8px 14px",
                          borderRadius: "8px",
                          fontSize: "12px",
                          fontWeight: 700,
                          textDecoration: "none",
                          boxShadow: "0 2px 4px rgba(3, 78, 162, 0.25)",
                        }}
                      >
                        <span>
                          {passport.german_arbitrage.booking_url.includes("check24")
                            ? "🇩🇪 Конкретный тур на Check24 (BER)"
                            : "🇩🇪 Вылет из Берлина (BER)"}
                        </span>
                        <span>↗</span>
                      </a>
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

              <div style={{ maxHeight: "420px", overflowY: "auto", overflowX: "auto", marginBottom: "20px", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                <table className="packages-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                  <thead style={{ position: "sticky", top: 0, zIndex: 10 }}>
                    <tr style={{ background: "#f8fafc", borderBottom: "2px solid #e2e8f0", textAlign: "left" }}>
                      <th style={{ padding: "10px 12px", color: "#475569", fontWeight: 700, background: "#f8fafc" }}>Даты поездки</th>
                      <th style={{ padding: "10px 12px", color: "#475569", fontWeight: 700, background: "#f8fafc" }}>Длит.</th>
                      <th style={{ padding: "10px 12px", color: "#475569", fontWeight: 700, background: "#f8fafc" }}>Аэропорт</th>
                      <th style={{ padding: "10px 12px", color: "#475569", fontWeight: 700, background: "#f8fafc" }}>Цена</th>
                      <th style={{ padding: "10px 12px", color: "#475569", fontWeight: 700, background: "#f8fafc" }}>Бронь</th>
                    </tr>
                  </thead>
                  <tbody id="drawerPackagesTbody">
                    {(passport?.available_packages && passport.available_packages.length > 0
                      ? passport.available_packages
                      : [
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
                        ]
                    ).map((pkg: any, idx: number) => {
                      const dep = pkg.checkin_date || pkg.departure_date;
                      const ret = pkg.checkout_date;
                      const dateText = dep ? (ret ? `${dep} – ${ret}` : dep) : "—";
                      const airportText = pkg.airport_code || pkg.airport || "WAW";
                      const durText = pkg.duration_nights ? `${pkg.duration_nights}н` : "—";
                      const priceVal = pkg.total_price_pln || pkg.price || currentPrice;
                      const bookUrl = pkg.booking_url || pkg.url || "https://fly.pl";
                      return (
                        <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                          <td style={{ padding: "8px 12px", fontWeight: 600, color: "#1e293b", whiteSpace: "nowrap" }}>{dateText}</td>
                          <td style={{ padding: "8px 12px", color: "#475569" }}>{durText}</td>
                          <td style={{ padding: "8px 12px", color: "#475569" }}>
                            <span style={{ background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px", fontSize: "11px", fontWeight: 600 }}>
                              {airportText}
                            </span>
                          </td>
                          <td style={{ padding: "8px 12px", fontWeight: 700, color: "#0f172a", whiteSpace: "nowrap" }}>
                            {Math.round(priceVal).toLocaleString("ru-RU")} zł
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            <a
                              href={bookUrl}
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
                                fontSize: "11px",
                              }}
                            >
                              Бронь ↗
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Other Filters Section */}
              {passport?.other_filters && passport.other_filters.length > 0 && (
                <div style={{ marginTop: "24px" }}>
                  <div style={{ marginBottom: "12px", fontSize: "0.88rem", fontWeight: 700, color: "#0f172a" }}>
                    🎯 Отель также отслеживается в других фильтрах:
                  </div>
                  <div style={{ display: "grid", gap: "10px" }}>
                    {passport.other_filters.map((f, idx) => (
                      <div
                        key={idx}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "12px 14px",
                          background: "#f8fafc",
                          border: "1px solid #e2e8f0",
                          borderRadius: "10px",
                          gap: "10px",
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: "#1e293b", fontSize: "13px" }}>
                            {f.title || f.filter_id}
                          </div>
                          <div style={{ fontSize: "11px", color: "#64748b", marginTop: "2px" }}>
                            👥 {f.adults} взр. {f.children ? `+ ${f.children} реб.` : ""}
                            {f.duration_nights ? ` • ~${f.duration_nights} ночей` : ""}
                            {f.snaps_count ? ` • ${f.snaps_count} замеров цен` : ""}
                          </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <div style={{ textAlign: "right" }}>
                            <div style={{ fontSize: "10px", color: "#64748b" }}>лучшая цена</div>
                            <div style={{ fontSize: "14px", fontWeight: 800, color: "#16a34a" }}>
                              от {Math.round(f.min_price_pln).toLocaleString("ru-RU")} zł
                            </div>
                          </div>
                          {onSwitchFilter && (
                            <button
                              type="button"
                              onClick={() => {
                                onSwitchFilter(f.filter_id);
                                onClose();
                              }}
                              style={{
                                background: "#0284c7",
                                color: "#ffffff",
                                border: "none",
                                padding: "6px 12px",
                                borderRadius: "8px",
                                fontSize: "12px",
                                fontWeight: 700,
                                cursor: "pointer",
                              }}
                            >
                              Перейти →
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
