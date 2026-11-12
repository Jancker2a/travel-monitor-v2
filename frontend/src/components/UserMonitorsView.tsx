import React, { useState } from "react";
import {
  BellRing,
  Plus,
  Play,
  Pause,
  Trash2,
  RefreshCw,
  ExternalLink,
  Clock,
  Sparkles,
  AlertTriangle,
  Lock,
  ArrowRight,
  TrendingDown,
  Layers,
  BarChart3,
} from "lucide-react";
import { UserMonitor, UserProfile } from "../types";
import { runUserMonitorNow, toggleUserMonitor, deleteUserMonitor } from "../services/api";

interface Props {
  currentUser: UserProfile | null;
  monitors: UserMonitor[];
  isLoading: boolean;
  onRefresh: () => void;
  onOpenCreateModal: () => void;
  onRequestAuth: () => void;
  onOpenDashboard: (monitor: UserMonitor) => void;
}

export const UserMonitorsView: React.FC<Props> = ({
  currentUser,
  monitors,
  isLoading,
  onRefresh,
  onOpenCreateModal,
  onRequestAuth,
  onOpenDashboard,
}) => {
  const [runningId, setRunningId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<{ id: string; text: string } | null>(null);

  if (!currentUser) {
    return (
      <div className="max-w-3xl mx-auto py-12 px-4 text-center">
        <div className="w-16 h-16 rounded-3xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center mx-auto mb-4 shadow-sm">
          <Lock className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">
          Персональный мониторинг туров
        </h2>
        <p className="text-sm text-slate-600 max-w-lg mx-auto mt-2 leading-relaxed font-medium">
          Войдите или зарегистрируйтесь, чтобы ставить любые поисковые запросы (или ссылки с сайта Fly.pl) на непрерывный контроль цен с мгновенными алертами в Telegram.
        </p>
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={onRequestAuth}
            className="px-6 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-black text-sm tracking-tight shadow-md transition-all flex items-center gap-2 cursor-pointer hover:shadow-lg hover:-translate-y-0.5"
          >
            <span>Войти или Зарегистрироваться</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  const handleRunNow = async (id: string) => {
    setRunningId(id);
    setActionMsg(null);
    try {
      const res = await runUserMonitorNow(id);
      setActionMsg({
        id,
        text: `Сканирование завершено: найдено ${res.total_found} туров (мин. ${res.min_price_pln ? res.min_price_pln.toLocaleString("ru-RU") + " zł" : "—"})`,
      });
      onRefresh();
    } catch (err: any) {
      setActionMsg({ id, text: `Ошибка: ${err.message}` });
    } finally {
      setRunningId(null);
    }
  };

  const handleToggle = async (id: string) => {
    setTogglingId(id);
    try {
      await toggleUserMonitor(id);
      onRefresh();
    } finally {
      setTogglingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Удалить этот мониторинг? Накопленные алерты будут остановлены.")) return;
    try {
      await deleteUserMonitor(id);
      onRefresh();
    } catch (err: any) {
      alert(err.message || "Ошибка удаления");
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-3xl bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white shadow-xl">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-sky-200 text-xs font-bold backdrop-blur-md mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Автономный сканер 24/7</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-black tracking-tight">
            Мои отслеживания цен
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 font-medium mt-0.5">
            Только ваши индивидуальные фильтры и ссылки. Проверяются по расписанию в фоне.
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenCreateModal}
          className="px-5 py-2.5 rounded-2xl bg-sky-500 hover:bg-sky-400 text-white font-black text-xs sm:text-sm tracking-tight shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer shrink-0"
        >
          <Plus className="w-4 h-4 stroke-[3]" />
          <span>Добавить мониторинг</span>
        </button>
      </div>

      {/* Monitors List */}
      {isLoading ? (
        <div className="py-16 text-center text-slate-400 font-bold">
          Загрузка ваших мониторингов...
        </div>
      ) : monitors.length === 0 ? (
        <div className="p-12 text-center bg-white rounded-3xl border border-slate-200/80 shadow-2xs">
          <div className="w-14 h-14 rounded-2xl bg-amber-50 text-amber-500 flex items-center justify-center mx-auto mb-3">
            <BellRing className="w-7 h-7" />
          </div>
          <h3 className="text-base font-black text-slate-900">
            У вас пока нет активных мониторингов
          </h3>
          <p className="text-xs text-slate-500 font-medium max-w-md mx-auto mt-1 mb-5">
            Поставьте на контроль текущий поиск или вставьте любую готовую ссылку с сайта Fly.pl, чтобы система ловила падения цен.
          </p>
          <button
            type="button"
            onClick={onOpenCreateModal}
            className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
          >
            + Создать первый мониторинг
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {monitors.map((m) => {
            const isBusy = runningId === m.id || togglingId === m.id;
            return (
              <div
                key={m.id}
                className={`p-5 rounded-3xl bg-white border transition-all shadow-2xs hover:shadow-md flex flex-col justify-between ${
                  !m.is_active
                    ? "border-slate-200 opacity-70 bg-slate-50/50"
                    : "border-slate-200/90 hover:border-blue-300"
                }`}
              >
                <div>
                  {/* Card Header: Title & Badges */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`text-[10px] font-black px-2 py-0.5 rounded-md uppercase tracking-wider ${
                            m.source_type === "FLY_URL"
                              ? "bg-purple-100 text-purple-700"
                              : "bg-blue-100 text-blue-700"
                          }`}
                        >
                          {m.source_type === "FLY_URL" ? "🔗 Fly.pl URL" : "⚙️ Поиск UI"}
                        </span>

                        <span
                          className={`text-[10.5px] font-bold px-2 py-0.5 rounded-md flex items-center gap-1 ${
                            m.status === "RUNNING"
                              ? "bg-amber-100 text-amber-800"
                              : m.is_active
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-200 text-slate-700"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              m.is_active ? "bg-emerald-500" : "bg-slate-400"
                            }`}
                          />
                          {m.status === "RUNNING"
                            ? "Сканирует..."
                            : m.is_active
                            ? "Активен"
                            : "На паузе"}
                        </span>
                      </div>

                      <h4 className="text-base font-black text-slate-900 tracking-tight truncate">
                        {m.title}
                      </h4>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => handleToggle(m.id)}
                        className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                        title={m.is_active ? "Поставить на паузу" : "Возобновить"}
                      >
                        {m.is_active ? (
                          <Pause className="w-4 h-4" />
                        ) : (
                          <Play className="w-4 h-4 text-emerald-600" />
                        )}
                      </button>

                      <button
                        type="button"
                        disabled={isBusy}
                        onClick={() => handleDelete(m.id)}
                        className="p-2 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                        title="Удалить мониторинг"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Metrics Row */}
                  <div className="grid grid-cols-3 gap-2 my-3 p-3 rounded-2xl bg-slate-50 border border-slate-100">
                    <div>
                      <span className="text-[10.5px] font-bold text-slate-400 block">
                        Мин. цена
                      </span>
                      <span className="text-sm font-black text-slate-900">
                        {m.last_min_price_pln
                          ? `${m.last_min_price_pln.toLocaleString("ru-RU")} zł`
                          : "—"}
                      </span>
                    </div>

                    <div>
                      <span className="text-[10.5px] font-bold text-slate-400 block">
                        Найдено туров
                      </span>
                      <span className="text-sm font-black text-slate-900 flex items-center gap-1">
                        <Layers className="w-3.5 h-3.5 text-blue-500" />
                        <span>{m.last_offers_count || 0}</span>
                      </span>
                    </div>

                    <div>
                      <span className="text-[10.5px] font-bold text-slate-400 block">
                        Порог алерта
                      </span>
                      <span className="text-sm font-black text-emerald-600 flex items-center gap-0.5">
                        <TrendingDown className="w-3.5 h-3.5" />
                        <span>-{m.min_drop_pct}%</span>
                      </span>
                    </div>
                  </div>

                  {/* Feedback Message */}
                  {actionMsg && actionMsg.id === m.id && (
                    <div className="mb-3 p-2 rounded-xl bg-blue-50 text-blue-900 text-xs font-bold">
                      {actionMsg.text}
                    </div>
                  )}

                  {m.last_error_message && (
                    <div className="mb-3 p-2 rounded-xl bg-rose-50 text-rose-700 text-xs font-medium flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-500" />
                      <span className="truncate">{m.last_error_message}</span>
                    </div>
                  )}
                </div>

                {/* Card Footer: Last check & Action */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <div className="flex items-center gap-1 font-semibold text-[11px]">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>
                      {m.last_checked_at
                        ? `Проверено: ${new Date(m.last_checked_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
                        : "Ожидает первой проверки"}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span>каждые {m.check_interval_hours}ч</span>
                  </div>

                  <div className="flex items-center gap-2">
                    {m.fly_source_url && (
                      <a
                        href={m.fly_source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-slate-500 hover:text-blue-600 font-bold flex items-center gap-1 transition-colors"
                        title="Открыть исходный поиск на Fly.pl"
                      >
                        <span>Fly.pl</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}

                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => handleRunNow(m.id)}
                      className="px-2.5 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors flex items-center gap-1 cursor-pointer disabled:opacity-50"
                      title="Выполнить сканирование прямо сейчас"
                    >
                      <RefreshCw className={`w-3 h-3 ${runningId === m.id ? "animate-spin" : ""}`} />
                      <span>{runningId === m.id ? "Сканирование..." : "Проверить ⚡"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onOpenDashboard(m)}
                      className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-black text-xs transition-all shadow-sm flex items-center gap-1.5 cursor-pointer hover:shadow-md"
                      title="Открыть полный интерактивный дашборд с отелями и ценами"
                    >
                      <BarChart3 className="w-3.5 h-3.5" />
                      <span>Открыть дашборд</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

