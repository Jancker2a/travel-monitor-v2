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
    dropped48hPln?: number;
    lastUpdatedText?: string;
  };
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
            <div className="kpi-card-title truncate max-w-[190px]" title={kpi.minPriceHotel || "Минимальная цена"}>
              {kpi.minPriceHotel ? `${kpi.minPriceHotel} (${kpi.minPriceDate || ""})` : "Мин. цена в туре"}
            </div>
          </div>
        </div>

        {/* KPI 2: Buy Now Count */}
        <div className="kpi-card-white" id="heroKpiBuyNow">
          <div className="kpi-card-icon-box kpi-icon--buy">
            <Flame className="w-5 h-5" />
          </div>
          <div className="kpi-card-info">
            <div className="kpi-card-number text-emerald-600">
              {kpi.buyNowCount !== undefined ? `${kpi.buyNowCount} отелей` : "—"}
            </div>
            <div className="kpi-card-title">
              К покупке сейчас (Score 80+)
            </div>
          </div>
        </div>

        {/* KPI 3: Dropped in 48h */}
        <div className="kpi-card-white" id="heroKpiDrops48h">
          <div className="kpi-card-icon-box kpi-icon--drop">
            <TrendingDown className="w-5 h-5" />
          </div>
          <div className="kpi-card-info">
            <div className="kpi-card-number text-blue-600">
              {kpi.dropped48hPln ? `−${kpi.dropped48hPln.toLocaleString("ru-RU")} zł` : "Стабильно"}
            </div>
            <div className="kpi-card-title">
              Подешевели за 48ч
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
