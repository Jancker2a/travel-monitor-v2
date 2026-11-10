import React from "react";
import { ExternalLink, Tag, Flame, TrendingDown, Clock, ShieldCheck } from "lucide-react";

interface HeroTerminalProps {
  title: string;
  countryBadge: string;
  targetUrl?: string;
  chips?: {
    airports?: string;
    dates?: string;
    party?: string;
    hotelClass?: string;
    budget?: string;
  };
  kpi: {
    minPricePln?: number;
    minPriceHotel?: string;
    minPriceDate?: string;
    buyNowCount?: number;
    dropped48hCount?: number;
    dropped48hMaxPln?: number;
    dropped48hMaxPct?: number;
    dropped48hTopHotel?: string;
    dropped48hPln?: number;
    lastUpdatedText?: string;
  };
  activeQuickFilter?: "buy_now" | "drops" | null;
  onQuickFilter?: (filterType: "buy_now" | "drops") => void;
}

function pluralizeHotels(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 19) return `${n} отелей`;
  if (mod10 === 1) return `${n} отель`;
  if (mod10 >= 2 && mod10 <= 4) return `${n} отеля`;
  return `${n} отелей`;
}

export const HeroTerminal: React.FC<HeroTerminalProps> = ({
  title,
  countryBadge,
  targetUrl,
  chips = {
    airports: "WAW, WRO, KTW, POZ, GDN",
    dates: "25.05.2027 — 25.06.2027",
    party: "2 взр + 1 реб (6 лет)",
    hotelClass: "4★ – 5★ All Inclusive",
    budget: "до 12 000 zł",
  },
  kpi,
  activeQuickFilter,
  onQuickFilter,
}) => {
  return (
    <section className="hero-terminal" id="heroTerminal">
      {/* Top Banner Row */}
      <div className="hero-terminal-top">
        <div className="hero-terminal-title-area">
          <div className="hero-terminal-badge">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>{countryBadge}</span>
          </div>
          <h1 className="hero-terminal-title">{title}</h1>
        </div>

        {targetUrl && (
          <a
            href={targetUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-open-fly"
            id="btnOpenFly"
            title="Открыть этот фильтр с текущими параметрами на Fly.pl"
          >
            <span>Открыть фильтр на Fly.pl</span>
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>

      {/* Dynamic Metadata Chips */}
      <div className="hero-terminal-chips">
        {chips.airports && (
          <div className="terminal-chip">
            <span>🛫</span>
            <span className="chip-label">Вылет:</span>
            <span className="chip-val">{chips.airports}</span>
          </div>
        )}
        {chips.dates && (
          <div className="terminal-chip">
            <span>📅</span>
            <span className="chip-label">Даты:</span>
            <span className="chip-val">{chips.dates}</span>
          </div>
        )}
        {chips.party && (
          <div className="terminal-chip">
            <span>👥</span>
            <span className="chip-label">Состав:</span>
            <span className="chip-val">{chips.party}</span>
          </div>
        )}
        {chips.hotelClass && (
          <div className="terminal-chip">
            <span>🏨</span>
            <span className="chip-label">Отель:</span>
            <span className="chip-val">{chips.hotelClass}</span>
          </div>
        )}
        {chips.budget && (
          <div className="terminal-chip">
            <span>💰</span>
            <span className="chip-label">Бюджет:</span>
            <span className="chip-val">{chips.budget}</span>
          </div>
        )}
      </div>

      {/* 4 White KPI Cards */}
      <div className="kpi-cards-grid">
        {/* KPI 1: Min Price */}
        <div className="kpi-card-white" id="heroKpiMinPrice">
          <div className="kpi-card-icon-box kpi-icon--price">
            <Tag className="w-5 h-5" />
          </div>
          <div className="kpi-card-info">
            <div className="kpi-card-number">
              {kpi.minPricePln ? `${kpi.minPricePln.toLocaleString("ru-RU")} zł` : "—"}
            </div>
            <div className="kpi-card-title truncate max-w-[280px]" title={kpi.minPriceHotel || "Минимальная цена"}>
              {kpi.minPriceHotel ? `${kpi.minPriceHotel} (${kpi.minPriceDate || ""})` : "Мин. цена в туре"}
            </div>
          </div>
        </div>

        {/* KPI 2: Buy Now Count */}
        <div
          className={`kpi-card-white cursor-pointer transition-all hover:border-emerald-300 hover:shadow-md select-none ${
            activeQuickFilter === "buy_now" ? "ring-2 ring-emerald-500 bg-emerald-50/40" : ""
          }`}
          id="heroKpiBuyNow"
          onClick={() => onQuickFilter?.("buy_now")}
          title="Нажмите, чтобы отфильтровать отели с Deal Score 80+ (рекомендовано к покупке)"
        >
          <div className="kpi-card-icon-box kpi-icon--buy">
            <Flame className="w-5 h-5" />
          </div>
          <div className="kpi-card-info">
            <div className="kpi-card-number text-emerald-600">
              {kpi.buyNowCount !== undefined ? pluralizeHotels(kpi.buyNowCount) : "—"}
            </div>
            <div className="kpi-card-title flex items-center gap-1">
              <span>К покупке сейчас</span>
              <span className="text-[10px] font-black bg-emerald-100 text-emerald-800 px-1 py-0.2 rounded">
                Score 80+
              </span>
            </div>
          </div>
        </div>

        {/* KPI 3: Dropped in 48h */}
        <div
          className={`kpi-card-white cursor-pointer transition-all hover:border-blue-300 hover:shadow-md select-none ${
            activeQuickFilter === "drops" ? "ring-2 ring-blue-500 bg-blue-50/40" : ""
          }`}
          id="heroKpiDrops48h"
          onClick={() => onQuickFilter?.("drops")}
          title={
            kpi.dropped48hCount && kpi.dropped48hCount > 0
              ? `Нажмите, чтобы показать ${kpi.dropped48hCount} отелей со скидками за последние 48ч`
              : "За последние 48 часов снижений цен не зафиксировано"
          }
        >
          <div className="kpi-card-icon-box kpi-icon--drop">
            <TrendingDown className="w-5 h-5" />
          </div>
          <div className="kpi-card-info min-w-0">
            <div className="kpi-card-number text-blue-600 flex items-baseline gap-1.5 flex-wrap">
              {kpi.dropped48hCount && kpi.dropped48hCount > 0 ? (
                <>
                  <span>{pluralizeHotels(kpi.dropped48hCount)}</span>
                  {kpi.dropped48hMaxPln && kpi.dropped48hMaxPln > 0 ? (
                    <span className="text-xs font-bold text-blue-500/90 whitespace-nowrap">
                      (до −{kpi.dropped48hMaxPln.toLocaleString("ru-RU")} zł)
                    </span>
                  ) : null}
                </>
              ) : (
                <span className="text-slate-600">0 отелей</span>
              )}
            </div>
            <div
              className="kpi-card-title truncate max-w-[280px]"
              title={
                kpi.dropped48hTopHotel
                  ? `Максимальное снижение: ${kpi.dropped48hTopHotel} (−${kpi.dropped48hMaxPln || 0} zł / −${kpi.dropped48hMaxPct || 0}%)`
                  : undefined
              }
            >
              {kpi.dropped48hCount && kpi.dropped48hCount > 0 && kpi.dropped48hTopHotel ? (
                <span>
                  Топ: <b className="text-slate-800 font-bold">{kpi.dropped48hTopHotel}</b>{" "}
                  {kpi.dropped48hMaxPct ? (
                    <span className="text-emerald-600 font-extrabold">(−{kpi.dropped48hMaxPct}%)</span>
                  ) : null}
                </span>
              ) : (
                <span>Цены стабильны за 48ч</span>
              )}
            </div>
          </div>
        </div>

        {/* KPI 4: Update Time */}
        <div className="kpi-card-white" id="heroKpiUpdate">
          <div className="kpi-card-icon-box kpi-icon--time">
            <Clock className="w-5 h-5" />
          </div>
          <div className="kpi-card-info">
            <div className="kpi-card-number text-slate-700">
              {kpi.lastUpdatedText || "12 мин. назад"}
            </div>
            <div className="kpi-status-tag">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>LIVE мониторинг</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

