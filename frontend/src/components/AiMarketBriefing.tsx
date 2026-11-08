import React from "react";
import { Sparkles, Plane, Target, ChevronDown } from "lucide-react";

interface AiMarketBriefingProps {
  filterTitle?: string;
  buyNowCount?: number;
}

export const AiMarketBriefing: React.FC<AiMarketBriefingProps> = ({
  filterTitle = "7–10 дней (2 взр + 1 реб)",
  buyNowCount = 14,
}) => {
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
              <span className="ai-phase-badge">Ближайшие вылеты через 6 дн.</span>
            </div>
            <div className="ai-oracle-subtitle">
              <strong className="ai-oracle-headline">Вылеты 14.11–01.12: на ближайшие даты цены падают, на дальние — стабильны</strong> • {filterTitle} • Rule-Based Deterministic Engine (Offline)
            </div>
          </div>
        </div>
        <span className="fold-chevron">⌄</span>
      </summary>

      <div className="fold-content p-4 sm:p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card 1: Flights & Price Dynamics */}
          <div className="ai-card-pulse">
            <div className="ai-card-header-purple flex items-center gap-2">
              <Plane className="w-4 h-4 text-purple-600" />
              <span>Что происходит с рейсами и ценами</span>
            </div>
            <div className="ai-card-body text-xs text-slate-700 leading-relaxed mt-2">
              Чартерная загрузка по направлению стабильна. На вылеты в ближайшие 7–10 дней туроператоры точечно сбрасывают непроданные места в отелях 4–5★ (падение до −8% к пику). На праздничные даты и раннее бронирование 2027 тарифы зафиксированы на медианном уровне.
            </div>
            <div className="ai-floor-badge mt-3">
              <span>Ценовой пол: от 3 240 zł за качественный отель 4★ All Inclusive</span>
            </div>
          </div>

          {/* Card 2: Directive */}
          <div className="ai-card-directive">
            <div className="ai-card-header-green flex items-center gap-2">
              <Target className="w-4 h-4 text-emerald-600" />
              <span>Совет: брать сейчас или подождать</span>
            </div>
            <div className="ai-card-body-green text-xs text-emerald-950 leading-relaxed mt-2">
              {buyNowCount > 0 ? (
                <>
                  На рынке есть <b>{buyNowCount} отелей</b> с индексом Deal Score 80+ и аномально низкой ценой. Рекомендуется бронировать проверенные отели 1-й линии прямо сейчас — дешёвые номера выкупаются в первую очередь.
                </>
              ) : (
                <>
                  Сейчас на рынке нет выраженных аномалий: отели продаются по базовым тарифам. Спешить нет смысла — поставьте отели в «Watchlist» и дождитесь приближения даты вылета.
                </>
              )}
            </div>
          </div>
        </div>

        {/* Buy Now Status Card */}
        <div className="ai-buy-now-card">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-600" />
              <span className="text-xs font-bold text-slate-800">
                {buyNowCount > 0 ? `Найдено ${buyNowCount} горячих предложений к покупке` : "Анализ рекомендаций к покупке"}
              </span>
            </div>
            <span className={`ai-buy-now-pill ${buyNowCount > 0 ? "pill--buy" : "pill--wait"}`}>
              {buyNowCount > 0 ? "🟢 ЕСТЬ ПРЕДЛОЖЕНИЯ К ПОКУПКЕ" : "⏳ ВЫГОДНЫХ СДЕЛОК НЕТ"}
            </span>
          </div>
        </div>
      </div>
    </details>
  );
};
