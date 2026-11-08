import React, { useState, useEffect } from "react";
import { Radio, RefreshCw, Plus, ExternalLink, Clock, Sparkles, CheckCircle2, AlertCircle } from "lucide-react";
import { getFilterMonitors, runMonitorNow, createCustomMonitor } from "../services/api";

interface MonitorItem {
  id: string;
  group_id: string;
  title: string;
  subtitle?: string;
  destination: string;
  target_url: string;
  is_active: boolean;
  is_hourly: boolean;
  last_scraped_at?: string;
  last_offers_count: number;
  last_min_price_pln?: number;
  last_status: string;
  created_by: string;
}

interface Props {
  onSelectMonitor: (monitor: MonitorItem) => void;
}

export const FilterMonitorsView: React.FC<Props> = ({ onSelectMonitor }) => {
  const [monitors, setMonitors] = useState<MonitorItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeGroup, setActiveGroup] = useState<string>("all");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Form state
  const [newTitle, setNewTitle] = useState("");
  const [newSubtitle, setNewSubtitle] = useState("");
  const [newDest, setNewDest] = useState("turkey");
  const [newUrl, setNewUrl] = useState("");

  const loadMonitors = async () => {
    setIsLoading(true);
    try {
      const data = await getFilterMonitors();
      setMonitors(data);
    } catch (err) {
      console.error("Failed to load monitors:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadMonitors();
  }, []);

  const handleRunNow = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRunningId(id);
    try {
      await runMonitorNow(id);
      await loadMonitors();
    } catch (err: any) {
      alert("Ошибка запуска скрапинга: " + err.message);
    } finally {
      setRunningId(null);
    }
  };

  const handleCreateMonitor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle || !newUrl) {
      alert("Заполните название и URL с Fly.pl");
      return;
    }

    try {
      await createCustomMonitor({
        title: newTitle,
        subtitle: newSubtitle || "Пользовательский фильтр",
        destination: newDest,
        target_url: newUrl,
      });
      setIsAddModalOpen(false);
      setNewTitle("");
      setNewSubtitle("");
      setNewUrl("");
      await loadMonitors();
    } catch (err: any) {
      alert("Ошибка создания: " + err.message);
    }
  };

  const filteredMonitors = monitors.filter((m) => {
    if (activeGroup === "all") return true;
    return m.group_id === activeGroup;
  });

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-3xl border border-slate-200 shadow-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
            <h2 className="text-lg font-extrabold text-slate-900 tracking-tight">
              24/7 МОНИТОРИНГ ЗАДАННЫХ ФИЛЬТРОВ
            </h2>
          </div>
          <p className="text-xs text-slate-500">
            Автоматический почасовой опрос заданных когорт (Турция 7-10, Египет, Греция, Раннее бронирование) с фиксацией динамики в БД
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white transition-all shadow-sm flex items-center gap-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Добавить фильтр</span>
          </button>
          <button
            onClick={loadMonitors}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
            title="Обновить статусы"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? "animate-spin text-blue-600" : ""}`} />
          </button>
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex gap-2 overflow-x-auto pb-1 text-xs font-bold scrollbar-none">
        {[
          { id: "all", label: `Все фильтры (${monitors.length})` },
          { id: "turkey", label: "🇹🇷 Турция" },
          { id: "egypt", label: "🇪🇬 Египет" },
          { id: "greece", label: "🇬🇷 Греция" },
          { id: "early_booking", label: "🏷️ Раннее бронирование 2027" },
          { id: "arbitrage", label: "🇩🇪 Немецкий арбитраж" },
          { id: "custom", label: "✨ Мои фильтры" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveGroup(tab.id)}
            className={`px-3.5 py-2 rounded-xl transition-all whitespace-nowrap ${
              activeGroup === tab.id
                ? "bg-slate-900 text-white shadow-sm"
                : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Monitors Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredMonitors.map((m) => {
          const isRunning = runningId === m.id;
          return (
            <div
              key={m.id}
              onClick={() => onSelectMonitor(m)}
              className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-300 transition-all cursor-pointer flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                    {m.group_id}
                  </span>
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Почасовой 24/7</span>
                  </div>
                </div>

                <h3 className="font-extrabold text-slate-900 text-sm group-hover:text-blue-600 transition-colors">
                  {m.title}
                </h3>
                {m.subtitle && (
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                    {m.subtitle}
                  </p>
                )}
              </div>

              <div className="mt-5 pt-3.5 border-t border-slate-100">
                <div className="flex items-center justify-between text-xs text-slate-600 mb-3">
                  <span className="flex items-center gap-1 text-[11px] text-slate-400">
                    <Clock className="w-3 h-3" />
                    {m.last_scraped_at ? new Date(m.last_scraped_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Не запускался"}
                  </span>
                  <span className="font-bold text-slate-800">
                    {m.last_offers_count > 0 ? `${m.last_offers_count} отелей` : "База готова"}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectMonitor(m);
                    }}
                    className="flex-1 py-2 px-3 rounded-xl text-xs font-bold bg-blue-50 hover:bg-blue-100 text-blue-700 transition-colors text-center"
                  >
                    Открыть офферы
                  </button>

                  <button
                    type="button"
                    onClick={(e) => handleRunNow(m.id, e)}
                    disabled={isRunning}
                    className="py-2 px-3 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors flex items-center gap-1 disabled:opacity-50"
                    title="Запустить опрос Fly.pl прямо сейчас"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? "animate-spin text-blue-600" : ""}`} />
                    <span>{isRunning ? "Скрапинг..." : "Скрап"}</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Add Custom Monitor Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200">
            <h3 className="text-lg font-black text-slate-900 mb-1">
              Добавить свой фильтр на почасовой мониторинг
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Вставьте поисковую ссылку с сайта Fly.pl с нужными вам датами, курортами и составом семьи.
            </p>

            <form onSubmit={handleCreateMonitor} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Название фильтра</label>
                <input
                  type="text"
                  placeholder="например: Турция • Кемер 5* • Отпуск в июне"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Описание / Заметка</label>
                <input
                  type="text"
                  placeholder="например: 2 взрослых + ребенок 6 лет • Первая линия"
                  value={newSubtitle}
                  onChange={(e) => setNewSubtitle(e.target.value)}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">Направление</label>
                <select
                  value={newDest}
                  onChange={(e) => setNewDest(e.target.value)}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="turkey">Турция</option>
                  <option value="egypt">Египет</option>
                  <option value="greece">Греция</option>
                  <option value="spain">Испания</option>
                  <option value="cyprus">Кипр</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">URL поиска с Fly.pl</label>
                <input
                  type="url"
                  placeholder="https://fly.pl/szukaj-wycieczek/?..."
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  className="w-full text-xs p-2.5 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-100 hover:bg-slate-200 text-slate-700"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white"
                >
                  Поставить на мониторинг 24/7
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

