import React, { useState, useEffect } from "react";
import {
  X,
  Bell,
  BellRing,
  Send,
  Check,
  AlertCircle,
  Sparkles,
  Plane,
  DollarSign,
  TrendingDown,
  Award,
  Star,
  Loader2,
  Lock,
} from "lucide-react";
import { UserProfile, DashboardAlertSubscription } from "../types";
import {
  getDashboardAlertSubscription,
  updateDashboardAlertSubscription,
  sendTestDashboardAlert,
} from "../services/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  monitorId: string;
  monitorTitle: string;
  currentUser: UserProfile | null;
  onRequestAuth: () => void;
  onSaved?: (subscription: DashboardAlertSubscription) => void;
}

const AIRPORTS = [
  { code: "WAW", label: "Варшава (WAW)" },
  { code: "KTW", label: "Катовице (KTW)" },
  { code: "KRK", label: "Краков (KRK)" },
  { code: "POZ", label: "Познань (POZ)" },
  { code: "WRO", label: "Вроцлав (WRO)" },
  { code: "GDN", label: "Гданьск (GDN)" },
];

export const MonitorAlertsModal: React.FC<Props> = ({
  isOpen,
  onClose,
  monitorId,
  monitorTitle,
  currentUser,
  onRequestAuth,
  onSaved,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Alert settings states
  const [isActive, setIsActive] = useState(true);
  const [notifyMode, setNotifyMode] = useState<"INSTANT" | "DIGEST_ONLY">("INSTANT");
  const [minDropPct, setMinDropPct] = useState<number>(5.0);
  const [minDropPln, setMinDropPln] = useState<number | "">("");
  const [minDealScore, setMinDealScore] = useState<number>(80);
  const [maxBudgetPln, setMaxBudgetPln] = useState<number | "">("");
  const [onlyHistoricLow, setOnlyHistoricLow] = useState(false);
  const [minTaRating, setMinTaRating] = useState<number | null>(4.0);
  const [selectedAirports, setSelectedAirports] = useState<string[]>([]);

  // Testing states
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Load existing settings when modal opens
  useEffect(() => {
    if (!isOpen || !currentUser) return;
    setIsLoading(true);
    setErrorMsg(null);
    setSaveSuccess(false);
    setTestResult(null);

    getDashboardAlertSubscription(monitorId, monitorTitle)
      .then((sub: DashboardAlertSubscription) => {
        setIsActive(sub.is_active);
        setNotifyMode(sub.notify_mode || "INSTANT");
        setMinDropPct(sub.min_drop_pct ?? 5.0);
        setMinDropPln(sub.min_drop_pln ?? "");
        setMinDealScore(sub.min_deal_score ?? 80);
        setMaxBudgetPln(sub.max_budget_pln ?? "");
        setOnlyHistoricLow(Boolean(sub.only_historic_low));
        setMinTaRating(sub.min_ta_rating ?? 4.0);
        if (sub.preferred_airports) {
          setSelectedAirports(sub.preferred_airports.split(",").map((s) => s.trim()).filter(Boolean));
        } else {
          setSelectedAirports([]);
        }
      })
      .catch((err) => {
        setErrorMsg(err.message || "Не удалось загрузить настройки алертов");
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [isOpen, monitorId, monitorTitle, currentUser]);

  if (!isOpen) return null;

  if (!currentUser) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl w-full max-w-md p-6 shadow-2xl text-center space-y-4">
          <div className="w-14 h-14 rounded-2xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 flex items-center justify-center mx-auto">
            <Lock className="w-7 h-7" />
          </div>
          <div>
            <h3 className="text-lg font-black text-slate-900 dark:text-white">
              Требуется авторизация
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Войдите в систему, чтобы привязать Telegram и настроить гибкие алерты для мониторинга «{monitorTitle}».
            </p>
          </div>
          <div className="pt-2 flex gap-2 justify-center">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => {
                onClose();
                onRequestAuth();
              }}
              className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-sm cursor-pointer"
            >
              Войти или зарегистрироваться
            </button>
          </div>
        </div>
      </div>
    );
  }

  const handleToggleAirport = (code: string) => {
    setSelectedAirports((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSaveSuccess(false);

    try {
      const saved = await updateDashboardAlertSubscription(
        monitorId,
        {
          is_active: isActive,
          notify_mode: notifyMode,
          min_drop_pct: Number(minDropPct) || 0,
          min_drop_pln: minDropPln !== "" ? Number(minDropPln) : null,
          min_deal_score: Number(minDealScore) || 0,
          max_budget_pln: maxBudgetPln !== "" ? Number(maxBudgetPln) : null,
          only_historic_low: onlyHistoricLow,
          min_ta_rating: minTaRating !== null ? Number(minTaRating) : null,
          preferred_airports: selectedAirports.length > 0 ? selectedAirports.join(",") : null,
          monitor_title: monitorTitle,
        },
        monitorTitle
      );
      setSaveSuccess(true);
      if (onSaved) onSaved(saved);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err: any) {
      setErrorMsg(err.message || "Ошибка сохранения настроек");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestAlert = async () => {
    setIsTesting(true);
    setTestResult(null);
    setErrorMsg(null);

    try {
      const res = await sendTestDashboardAlert(monitorId, monitorTitle);
      setTestResult({
        success: res.success,
        message: res.message,
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.message || "Ошибка отправки тестового алерта",
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center font-bold">
              <BellRing className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 dark:text-white">
                Telegram-алерты мониторинга
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400 font-medium truncate max-w-xs sm:max-w-sm">
                {monitorTitle}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSave} className="p-6 overflow-y-auto space-y-5">
          {errorMsg && (
            <div className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {saveSuccess && (
            <div className="p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-2.5 animate-fade-in">
              <Check className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>Настройки алертов успешно сохранены!</span>
            </div>
          )}

          {/* Master Toggle for this Monitor */}
          <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-500/5 to-indigo-500/5 border border-blue-200/80 dark:border-blue-900/50 flex items-center justify-between">
            <div>
              <span className="text-xs font-black text-slate-900 dark:text-white block">
                Уведомления для этого мониторинга
              </span>
              <span className="text-[11px] text-slate-500 dark:text-slate-400">
                {isActive ? "Алерты активны: бот следит за ценами" : "Алерты на паузе"}
              </span>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-200 peer-focus:outline-hidden rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {/* Delivery Mode: Instant vs Digest */}
          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-slate-400 mb-2">
              Режим оповещений
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setNotifyMode("INSTANT")}
                className={`p-3 rounded-2xl border text-left transition-all ${
                  notifyMode === "INSTANT"
                    ? "border-blue-500 bg-blue-50/50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-100 shadow-xs"
                    : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-1.5 font-bold text-xs mb-0.5">
                  <span>⚡ Мгновенно</span>
                </div>
                <div className="text-[10px] text-slate-500">
                  Сразу при обнаружении падения краулером
                </div>
              </button>

              <button
                type="button"
                onClick={() => setNotifyMode("DIGEST_ONLY")}
                className={`p-3 rounded-2xl border text-left transition-all ${
                  notifyMode === "DIGEST_ONLY"
                    ? "border-amber-500 bg-amber-50/50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-100 shadow-xs"
                    : "border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-400 hover:border-slate-300"
                }`}
              >
                <div className="flex items-center gap-1.5 font-bold text-xs mb-0.5">
                  <span>🌅 Только в дайджесте</span>
                </div>
                <div className="text-[10px] text-slate-500">
                  В утренней сводке без шума в течение дня
                </div>
              </button>
            </div>
          </div>

          {/* Drop Percentage Chips */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                Порог падения цены (%)
              </label>
              <span className="text-[11px] font-black text-blue-600 dark:text-blue-400">
                {minDropPct === 0 ? "Любое снижение" : `≥ ${minDropPct}%`}
              </span>
            </div>
            <div className="flex gap-1.5">
              {[
                { val: 0, label: "Любое" },
                { val: 5, label: "5%" },
                { val: 10, label: "10%" },
                { val: 15, label: "15%" },
                { val: 20, label: "20%" },
              ].map((chip) => (
                <button
                  key={chip.val}
                  type="button"
                  onClick={() => setMinDropPct(chip.val)}
                  className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    minDropPct === chip.val
                      ? "bg-blue-600 text-white shadow-xs"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
                  }`}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>

          {/* Drop PLN & Max Budget Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                Минимум скидки в злотых (PLN)
              </label>
              <input
                type="number"
                value={minDropPln}
                onChange={(e) => setMinDropPln(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="Например: 500 zł"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-800 dark:text-white"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                Потолок бюджета (Max PLN)
              </label>
              <input
                type="number"
                value={maxBudgetPln}
                onChange={(e) => setMaxBudgetPln(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="Не дороже: ... zł"
                className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-medium text-slate-800 dark:text-white"
              />
            </div>
          </div>

          {/* Minimum Deal Score */}
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              Минимальный Deal Score (Фильтр качества)
            </label>
            <div className="flex gap-1.5">
              {[
                { val: 0, label: "Все" },
                { val: 75, label: "75+ Good" },
                { val: 80, label: "80+ Great" },
                { val: 85, label: "85+ Super" },
                { val: 90, label: "90+ 🔥 Hot" },
              ].map((s) => (
                <button
                  key={s.val}
                  type="button"
                  onClick={() => setMinDealScore(s.val)}
                  className={`flex-1 py-1.5 rounded-xl text-[11px] font-bold transition-all ${
                    minDealScore === s.val
                      ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900 shadow-xs"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Historic Low & TripAdvisor Rating Row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
                  Только рекорды
                </span>
                <span className="text-[10px] text-slate-500">
                  Исторические минимумы
                </span>
              </div>
              <input
                type="checkbox"
                checked={onlyHistoricLow}
                onChange={(e) => setOnlyHistoricLow(e.target.checked)}
                className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                Рейтинг TripAdvisor
              </label>
              <div className="flex gap-1">
                {[
                  { val: null, label: "Любой" },
                  { val: 4.0, label: "★ 4.0+" },
                  { val: 4.5, label: "★ 4.5+" },
                ].map((r) => (
                  <button
                    key={String(r.val)}
                    type="button"
                    onClick={() => setMinTaRating(r.val)}
                    className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all ${
                      minTaRating === r.val
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                    }`}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Preferred Airports (Multi-select) */}
          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              Город вылета (не выбрано = любые аэропорты)
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
              {AIRPORTS.map((apt) => {
                const isSelected = selectedAirports.includes(apt.code);
                return (
                  <button
                    key={apt.code}
                    type="button"
                    onClick={() => handleToggleAirport(apt.code)}
                    className={`px-2.5 py-1.5 rounded-xl text-[11px] font-bold border transition-all ${
                      isSelected
                        ? "bg-blue-50 dark:bg-blue-950/40 border-blue-400 text-blue-700 dark:text-blue-300"
                        : "border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-slate-300"
                    }`}
                  >
                    {apt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Test Button Card */}
          <div className="p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 flex items-center justify-between">
            <div>
              <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
                Тестовое уведомление
              </span>
              <span className="text-[11px] text-slate-500">
                Пришлет лучший тур с этого дашборда вам в Telegram
              </span>
            </div>
            <button
              type="button"
              onClick={handleTestAlert}
              disabled={isTesting}
              className="px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-xs tracking-tight transition-all flex items-center gap-1.5 cursor-pointer shadow-sm shrink-0"
            >
              {isTesting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Шлём...</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Тест алерта</span>
                </>
              )}
            </button>
          </div>

          {testResult && (
            <div
              className={`p-3 rounded-xl text-xs flex items-start gap-2 ${
                testResult.success
                  ? "bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
                  : "bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300"
              }`}
            >
              {testResult.success ? (
                <Check className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
              )}
              <span>{testResult.message}</span>
            </div>
          )}

          {/* Footer Save Button */}
          <div className="pt-2 flex items-center justify-end gap-2.5 border-t border-slate-100 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs tracking-tight transition-all flex items-center gap-1.5 shadow-sm cursor-pointer"
            >
              {isSaving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Сохранение...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Сохранить алерты</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
