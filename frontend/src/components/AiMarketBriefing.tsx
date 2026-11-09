import React, { useEffect, useState } from "react";
import { Sparkles, Plane, Target, ExternalLink, BarChart2, Loader2 } from "lucide-react";
import { MarketOracleData, MarketOraclePick } from "../types";
import { getFilterMarketOracle } from "../services/api";
import { LoadingSpinner } from "./common/LoadingSpinner";

interface AiMarketBriefingProps {
  filterId?: string;
  filterTitle?: string;
  buyNowCount?: number;
  onOpenPassport?: (hotelId: string) => void;
}

export const AiMarketBriefing: React.FC<AiMarketBriefingProps> = ({
  filterId,
  filterTitle = "7–10 дней (2 взр + 1 реб)",
  buyNowCount = 0,
  onOpenPassport,
}) => {
  const [oracleData, setOracleData] = useState<MarketOracleData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    if (!filterId) return;
    setIsLoading(true);
    getFilterMarketOracle(filterId)
      .then((data) => {
        setOracleData(data);
      })
      .catch((err) => {
        console.warn("Failed to load AI Oracle briefing:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [filterId]);

  const hasPicks = Boolean(
    oracleData?.buy_now_recommendation?.top_picks &&
      oracleData.buy_now_recommendation.top_picks.length > 0
  );

  const headline =
    oracleData?.headline ||
    "Цены стабильные, можно спокойно выбирать отель";

  const marketPhase =
    oracleData?.market_phase || "Ранний выбор";

  const charterDynamics =
    oracleData?.charter_dynamics ||
    "Чартерная загрузка по направлению стабильна. На вылеты в ближайшие 7–10 дней туроператоры точечно сбрасывают непроданные места в отелях 4–5★. На дальние даты тарифы зафиксированы на медианном уровне.";

  const floorStatus =
    oracleData?.floor_status ||
    (buyNowCount > 0
      ? `${buyNowCount} отелей сейчас отдают по минимальной цене за сезон.`
      : "Цены на уровне медианного диапазона.");

  const strategicDirective =
    oracleData?.strategic_directive ||
    (buyNowCount > 0
      ? `На рынке есть ${buyNowCount} отелей с высоким Deal Score. Рекомендуется бронировать проверенные отели прямо сейчас.`
      : "Спешить не нужно. Сохраняйте понравившиеся отели в Избранное (⭐) и ждите: за 10–14 дней до вылета часто начинаются первые скидки.");

  const buyNowRecommendation = oracleData?.buy_now_recommendation;
  const topPicks: MarketOraclePick[] = buyNowRecommendation?.top_picks || [];
  const anomalies = oracleData?.key_anomalies || [];

  return (
    <details className="dashboard-fold ai-oracle-fold" id="aiOracleFold" open>
      <summary className="cursor-pointer select-none">
        <div className="flex items-center gap-3">
          <div className="ai-oracle-icon-box">
            <span>🧠</span>
          </div>
          <div className="ai-oracle-title-wrap">
            <div className="ai-oracle-title-row">
              <span className="ai-oracle-main-title">AI-анализ рынка и прогноз цен</span>
              <span className="ai-phase-badge">
                {isLoading ? (
                  <span className="inline-flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin text-blue-600" />
                    <span>Анализ...</span>
                  </span>
                ) : (
                  marketPhase
                )}
              </span>
            </div>
            <div className="ai-oracle-subtitle">
              <strong className="ai-oracle-headline">{headline}</strong> • {oracleData?.title || filterTitle} • Rule-Based Deterministic Engine (Offline)
            </div>
          </div>
        </div>
        <span className="fold-chevron">⌄</span>
      </summary>

      <div className="fold-content p-4 sm:p-5 space-y-4 relative min-h-[140px]">
        {isLoading && (
          <LoadingSpinner
            variant="overlay"
            size="md"
            label="AI-анализ рынка и прогноз цен..."
            description="Сканируем чартерную загрузку и определяем стратегию покупки"
          />
        )}
        {/* Row 1: Two Column Analysis */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card 1: Flights & Price Dynamics */}
          <div className="ai-card-pulse">
            <div className="ai-card-header-purple flex items-center gap-2">
              <Plane className="w-4 h-4 text-purple-600" />
              <span>Что происходит с рейсами и ценами</span>
            </div>
            <div className="ai-card-body text-xs text-slate-700 leading-relaxed mt-2">
              {charterDynamics}
            </div>
            {floorStatus && (
              <div className="ai-floor-badge mt-3">
                <span>📊 {floorStatus}</span>
              </div>
            )}
          </div>

          {/* Card 2: Strategic Directive */}
          <div className="ai-card-directive">
            <div className="ai-card-header-green flex items-center gap-2">
              <Target className="w-4 h-4 text-emerald-600" />
              <span>Совет: брать сейчас или подождать</span>
            </div>
            <div className="ai-card-body-green text-xs text-emerald-950 leading-relaxed mt-2">
              {strategicDirective}
            </div>
          </div>
        </div>

        {/* Row 2: If Buying Now Box */}
        <div
          className={`ai-buy-now-box ${
            hasPicks ? "ai-buy-now--active" : "ai-buy-now--wait"
          }`}
        >
          <div className="ai-buy-now-header">
            <div className="ai-buy-now-title-group">
              <span className="ai-buy-now-icon">🛒</span>
              <div className="ai-buy-now-titles">
                <span className="ai-buy-now-kicker">ЕСЛИ ПОКУПАТЬ СЕЙЧАС:</span>
                <span className="ai-buy-now-heading">
                  {buyNowRecommendation?.explanation ||
                    (hasPicks
                      ? "Стоит выбрать из этих вариантов — самые удачные предложения по соотношению цена/качество прямо сейчас."
                      : "Выраженных аномалий нет. Рекомендуется поставить отели на мониторинг и подождать скидок.")}
                </span>
              </div>
            </div>
            <span
              className={`ai-buy-now-pill ${
                hasPicks ? "pill--active" : "pill--wait"
              }`}
            >
              {buyNowRecommendation?.label ||
                (hasPicks ? "🟢 ЕСТЬ ВЫГОДНЫЕ ВАРИАНТЫ" : "⏳ СПЕШИТЬ НЕ СТОИТ")}
            </span>
          </div>

          {/* Recommended Hotel Cards Grid */}
          {hasPicks && (
            <div className="ai-picks-grid mt-3">
              {topPicks.map((pick) => (
                <div key={pick.hotel_id} className="ai-pick-card">
                  <div className="ai-pick-header">
                    <span className="ai-pick-name">{pick.hotel_name}</span>
                    <span className="ai-pick-price">
                      {Math.round(pick.price).toLocaleString("ru-RU")} zł
                    </span>
                  </div>
                  <div className="ai-pick-meta">
                    <span className="ai-pick-badge">{pick.badge}</span>
                    <span className="ai-pick-why">{pick.reason}</span>
                  </div>
                  <div className="ai-pick-actions">
                    {onOpenPassport && (
                      <button
                        type="button"
                        onClick={() => onOpenPassport(pick.hotel_id)}
                        className="ai-pick-btn ai-pick-btn--chart gap-1.5"
                      >
                        <BarChart2 className="w-3.5 h-3.5" />
                        <span>Паспорт отеля</span>
                      </button>
                    )}
                    {pick.booking_url && (
                      <a
                        href={pick.booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ai-pick-btn ai-pick-btn--offer gap-1.5"
                      >
                        <span>Купить</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Row 3: Key Market Anomalies Tags */}
        {anomalies.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {anomalies.map((anomaly, idx) => {
              const title = typeof anomaly === "string" ? "" : anomaly.title;
              const text = typeof anomaly === "string" ? anomaly : anomaly.text;
              return (
                <div key={idx} className="ai-anomaly-tag">
                  {title && <strong>{title}: </strong>}
                  <span>{text}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </details>
  );
};
