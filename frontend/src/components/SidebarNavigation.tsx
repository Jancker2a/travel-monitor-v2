import React from "react";
import {
  Plane,
  ChevronLeft,
  ChevronRight,
  Radio,
  Search,
  Scale,
  Calendar,
  Layers,
  Sparkles,
  ExternalLink,
  PlusCircle,
} from "lucide-react";

export interface NavFilterItem {
  id: string;
  title: string;
  destination: string;
  icon?: string;
  badge?: string;
  target_url?: string;
  is_active?: boolean;
}

interface SidebarNavigationProps {
  isOpen: boolean;
  onToggle: () => void;
  activeFilterId: string;
  onSelectFilter: (id: string) => void;
  onOpenSearch: () => void;
  onOpenArbitrage: () => void;
  activeTab: "filter" | "search" | "arbitrage";
}

export const SidebarNavigation: React.FC<SidebarNavigationProps> = ({
  isOpen,
  onToggle,
  activeFilterId,
  onSelectFilter,
  onOpenSearch,
  onOpenArbitrage,
  activeTab,
}) => {
  const filterGroups: {
    group: string;
    icon: string;
    items: { id: string; title: string; badge?: string }[];
  }[] = [
    {
      group: "🇹🇷 Турция",
      icon: "🇹🇷",
      items: [
        { id: "turkey_7_10_days", title: "7–10 дней (2 взр + 1 реб)" },
        { id: "turkey_11_14_days", title: "11–14 дней (2 взр + 1 реб)" },
        { id: "turkey_7_10_adults", title: "7–10 дней (2 взрослых)" },
        { id: "turkey_aquapark", title: "1-я линия и Аквапарки" },
      ],
    },
    {
      group: "🇪🇬 Египет",
      icon: "🇪🇬",
      items: [
        { id: "egypt_7_10_days", title: "7–10 дней (2 взр + 1 реб)" },
        { id: "egypt_sharm", title: "Шарм-эль-Шейх (бухты без ветра)" },
        { id: "egypt_hurghada", title: "Хургада песчаный пляж" },
      ],
    },
    {
      group: "🇬🇷 Греция & Испания",
      icon: "🇬🇷",
      items: [
        { id: "greece_islands", title: "Крит и Родос 7–10 дней" },
        { id: "spain_mallorca", title: "Майорка 7–10 дней" },
      ],
    },
    {
      group: "🐣 Раннее бронирование",
      icon: "🐣",
      items: [
        { id: "early_booking_2027", title: "Лето 2027 (ранний радар)", badge: "2027" },
      ],
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          onClick={onToggle}
          className="fixed inset-0 bg-slate-900/60 z-30 lg:hidden backdrop-blur-sm"
        />
      )}

      {/* Main Sidebar */}
      <aside
        id="sidebar"
        className={`fixed top-0 bottom-0 left-0 z-40 bg-slate-900 text-slate-200 w-72 flex flex-col border-r border-slate-800 transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Sidebar Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-md shadow-blue-500/20">
              ✈️
            </div>
            <div>
              <div className="text-sm font-extrabold tracking-tight text-white flex items-center gap-1.5">
                <span>TRAVEL MONITOR</span>
                <span className="text-[9px] font-bold bg-blue-500/20 text-blue-400 px-1 py-0.2 rounded border border-blue-500/30">
                  v2.0
                </span>
              </div>
              <p className="text-[10px] text-slate-400">Радар цен & Meta-Search</p>
            </div>
          </div>

          <button
            id="sidebarClose"
            onClick={onToggle}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
            title="Свернуть панель"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        </div>

        {/* Global Nav Modes */}
        <div className="p-3 border-b border-slate-800 space-y-1">
          <button
            onClick={() => {
              onOpenSearch();
            }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === "search"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                : "text-slate-300 hover:bg-slate-800 hover:text-white"
            }`}
          >
            <Search className="w-4 h-4 text-blue-400" />
            <span>🔍 Интерактивный поиск v2</span>
          </button>

          <button
            onClick={() => {
              onOpenArbitrage();
            }}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === "arbitrage"
                ? "bg-blue-600 text-white shadow-sm shadow-blue-500/30"
                : "text-slate-300 hover:bg-slate-800 hover:text-white"
            }`}
          >
            <Scale className="w-4 h-4 text-emerald-400" />
            <span>🇩🇪 Немецкий арбитраж (BER)</span>
          </button>
        </div>

        {/* Filter Presets List (V1 Core Dashboards) */}
        <div className="flex-1 overflow-y-auto p-3 space-y-4 text-xs scrollbar-thin">
          <div className="px-2 text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span>Канонические радары (24/7)</span>
            <span className="flex items-center gap-1 text-[9px] text-emerald-400 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          </div>

          {filterGroups.map((grp) => (
            <div key={grp.group} className="space-y-1">
              <div className="px-2 py-1 text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
                <span>{grp.icon}</span>
                <span>{grp.group}</span>
              </div>

              {grp.items.map((item) => {
                const isSelected = activeTab === "filter" && activeFilterId === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelectFilter(item.id)}
                    className={`w-full text-left flex items-center justify-between px-3 py-1.5 rounded-lg text-xs transition-colors ${
                      isSelected
                        ? "bg-sky-500/20 text-sky-300 font-semibold border border-sky-500/40"
                        : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                    }`}
                  >
                    <span className="truncate">{item.title}</span>
                    {item.badge && (
                      <span className="text-[9px] bg-amber-500/20 text-amber-300 px-1 py-0.2 rounded border border-amber-500/30 font-bold">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Sidebar Footer */}
        <div className="p-3 border-t border-slate-800 bg-slate-900/90 text-[11px] text-slate-400 space-y-1">
          <div className="flex items-center justify-between">
            <span>База данных:</span>
            <span className="font-semibold text-slate-200">43 651 цен</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Почасовой опрос:</span>
            <span className="text-emerald-400 font-semibold">Активен</span>
          </div>
        </div>
      </aside>
    </>
  );
};
