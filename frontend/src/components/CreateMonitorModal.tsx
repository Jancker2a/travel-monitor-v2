import React, { useState, useEffect } from "react";
import {
  X,
  Link as LinkIcon,
  Search,
  BellRing,
  Clock,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Send,
  Sliders,
} from "lucide-react";
import { parseFlyUrl, createUserMonitor } from "../services/api";
import { SearchRequest, UserMonitor, UserProfile, FlyUrlParseResponse } from "../types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (monitor: UserMonitor) => void;
  currentSearchReq?: SearchRequest;
  currentUser: UserProfile | null;
  onRequestAuth: () => void;
}

export const CreateMonitorModal: React.FC<Props> = ({
  isOpen,
  onClose,
  onCreated,
  currentSearchReq,
  currentUser,
  onRequestAuth,
}) => {
  const [sourceType, setSourceType] = useState<"CUSTOM_FILTER" | "FLY_URL">("CUSTOM_FILTER");
  const [title, setTitle] = useState("");
  const [flyUrl, setFlyUrl] = useState("");
  const [isParsingUrl, setIsParsingUrl] = useState(false);
  const [parsedData, setParsedData] = useState<FlyUrlParseResponse | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  // Settings
  const [intervalHours, setIntervalHours] = useState(3);
  const [minDropPct, setMinDropPct] = useState(5.0);
  const [maxBudget, setMaxBudget] = useState<string>("");
  const [notifyTelegram, setNotifyTelegram] = useState(true);
  const [notifyEmail, setNotifyEmail] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pre-fill from currentSearchReq if opened
  useEffect(() => {
    if (isOpen && currentSearchReq && sourceType === "CUSTOM_FILTER") {
      const dest = currentSearchReq.destination || "Курорт";
      const ap = currentSearchReq.airports?.length ? ` (${currentSearchReq.airports.join(", ")})` : "";
      setTitle(`Мониторинг: ${dest}${ap} • ${currentSearchReq.duration?.min_nights || 7}-${currentSearchReq.duration?.max_nights || 10}н`);
    }
  }, [isOpen, currentSearchReq, sourceType]);

  if (!isOpen) return null;

  const handleParseUrl = async (urlToParse?: string) => {
    const target = urlToParse || flyUrl;
    if (!target.trim()) return;
    setIsParsingUrl(true);
    setParseError(null);
    try {
      const res = await parseFlyUrl(target.trim());
      setParsedData(res);
      if (res.is_valid) {
        setTitle(res.parsed_title);
      } else {
        setParseError(res.error_message || "Не удалось разобрать ссылку");
      }
    } catch (err: any) {
      setParseError(err.message || "Ошибка распознавания ссылки");
    } finally {
      setIsParsingUrl(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentUser) {
      onRequestAuth();
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      let filterParams: Record<string, any> = {};

      if (sourceType === "CUSTOM_FILTER") {
        filterParams = currentSearchReq || {
          destination: "turkey",
          airports: ["WAW", "KTW"],
          duration: { min_nights: 7, max_nights: 10 },
          travelers: { adults: 2, children: 0, children_ages: [] },
        };
      } else {
        if (!parsedData || !parsedData.is_valid) {
          throw new Error("Сначала вставьте и распознайте корректную ссылку с Fly.pl");
        }
        filterParams = parsedData.structured_search_request;
      }

      const monitor = await createUserMonitor({
        title: title.trim() || "Новый мониторинг",
        source_type: sourceType,
        fly_source_url: sourceType === "FLY_URL" ? flyUrl.trim() : undefined,
        filter_params: filterParams,
        check_interval_hours: intervalHours,
        min_drop_pct: minDropPct,
        max_budget_pln: maxBudget ? parseFloat(maxBudget) : undefined,
        notify_telegram: notifyTelegram,
        notify_email: notifyEmail,
      });

      onCreated(monitor);
      onClose();
    } catch (err: any) {
      setError(err.message || "Не удалось создать задачу мониторинга");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="relative w-full max-w-xl bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden flex flex-col max-h-[92vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center">
              <BellRing className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-black text-slate-900 tracking-tight">
                Поставить поиск на мониторинг
              </h3>
              <p className="text-xs text-slate-500 font-semibold">
                Автоматическое сканирование котировок с оповещениями
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Source Mode Selector */}
        <div className="px-6 pt-4">
          <div className="grid grid-cols-2 gap-2 bg-slate-100 p-1 rounded-2xl">
            <button
              type="button"
              onClick={() => {
                setSourceType("CUSTOM_FILTER");
                setError(null);
              }}
              className={`flex items-center justify-center gap-2 py-2 rounded-xl text-xs font-black transition-all cursor-pointer ${
                sourceType === "CUSTOM_FILTER"
                  ? "bg-white text-blue-600 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Sliders className="w-4 h-4" />
              <span>Текущий поиск UI</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setSourceType("FLY_URL");
                setError(null);
              }}
              className={`flex items-center justify-center gap-2 py-2 rounded-xl text-xs font-black transition-all cursor-pointer ${
                sourceType === "FLY_URL"
                  ? "bg-white text-blue-600 shadow-xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <LinkIcon className="w-4 h-4" />
              <span>Ссылка с Fly.pl</span>
            </button>
          </div>
        </div>

        {/* Scrollable Form Body */}
        <form onSubmit={handleSubmit} className="px-6 py-4 space-y-4 overflow-y-auto flex-1">
          {error && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-bold flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          {sourceType === "FLY_URL" ? (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1.5">
                  Вставьте URL поиска с сайта Fly.pl
                </label>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={flyUrl}
                    onChange={(e) => {
                      setFlyUrl(e.target.value);
                      if (e.target.value.includes("fly.pl")) {
                        handleParseUrl(e.target.value);
                      }
                    }}
                    placeholder="https://fly.pl/wyszukiwarka/turcja/..."
                    className="flex-1 px-3.5 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-800 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                  />
                  <button
                    type="button"
                    disabled={isParsingUrl || !flyUrl.trim()}
                    onClick={() => handleParseUrl()}
                    className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all cursor-pointer shrink-0 disabled:opacity-50"
                  >
                    {isParsingUrl ? <Loader2 className="w-4 h-4 animate-spin" /> : "Распознать"}
                  </button>
                </div>
              </div>

              {parseError && (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs font-bold flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0 text-amber-600" />
                  <span>{parseError}</span>
                </div>
              )}

              {parsedData && parsedData.is_valid && (
                <div className="p-3.5 rounded-2xl bg-emerald-50/70 border border-emerald-200 space-y-2">
                  <div className="flex items-center gap-1.5 text-emerald-800 font-black text-xs">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Параметры успешно распознаны:</span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-slate-700 text-[11px] font-bold">
                      📍 {parsedData.destination || "Курорт"}
                    </span>
                    {parsedData.departure_airports.length > 0 && (
                      <span className="px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-slate-700 text-[11px] font-bold">
                        ✈️ {parsedData.departure_airports.join(", ")}
                      </span>
                    )}
                    <span className="px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-slate-700 text-[11px] font-bold">
                      ⏱️ {parsedData.duration_min}-{parsedData.duration_max} ночей
                    </span>
                    <span className="px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-slate-700 text-[11px] font-bold">
                      👥 {parsedData.adults} взр {parsedData.children > 0 ? `+ ${parsedData.children} реб` : ""}
                    </span>
                    {parsedData.catering && (
                      <span className="px-2 py-0.5 rounded-md bg-white border border-emerald-200 text-slate-700 text-[11px] font-bold">
                        🍽️ {parsedData.catering}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Current UI Search Summary Card */
            <div className="p-3.5 rounded-2xl bg-blue-50/60 border border-blue-200 space-y-2">
              <div className="flex items-center gap-1.5 text-blue-900 font-black text-xs">
                <Sparkles className="w-4 h-4 text-blue-600" />
                <span>Параметры из активного поискового фильтра:</span>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="px-2.5 py-1 rounded-lg bg-white border border-blue-200 text-slate-800 text-xs font-bold">
                  📍 {currentSearchReq?.destination || "Турция"}
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-blue-200 text-slate-800 text-xs font-bold">
                  ✈️ {currentSearchReq?.airports?.length ? currentSearchReq.airports.join(", ") : "Все аэропорты"}
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-blue-200 text-slate-800 text-xs font-bold">
                  ⏱️ {currentSearchReq?.duration?.min_nights || 7}-{currentSearchReq?.duration?.max_nights || 10} ночей
                </span>
                <span className="px-2.5 py-1 rounded-lg bg-white border border-blue-200 text-slate-800 text-xs font-bold">
                  👥 {currentSearchReq?.travelers?.adults || 2} взр
                </span>
              </div>
            </div>
          )}

          {/* Title Input */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Название мониторинга
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например: Крит на сентябрь из Катовице"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm font-bold text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>

          {/* Execution Interval */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Интервал автоматического сканирования
            </label>
            <div className="grid grid-cols-5 gap-2">
              {[1, 3, 6, 12, 24].map((hrs) => (
                <button
                  key={hrs}
                  type="button"
                  onClick={() => setIntervalHours(hrs)}
                  className={`py-2 rounded-xl text-xs font-extrabold border transition-all cursor-pointer ${
                    intervalHours === hrs
                      ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                      : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {hrs === 1 ? "1 час" : hrs === 24 ? "24ч (день)" : `${hrs}ч`}
                </button>
              ))}
            </div>
          </div>

          {/* Alert Threshold */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Порог уведомления о снижении цены
            </label>
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: "Любое", val: 1.0 },
                { label: "от -5%", val: 5.0 },
                { label: "от -10%", val: 10.0 },
                { label: "от -15%", val: 15.0 },
              ].map((thresh) => (
                <button
                  key={thresh.val}
                  type="button"
                  onClick={() => setMinDropPct(thresh.val)}
                  className={`py-2 rounded-xl text-xs font-extrabold border transition-all cursor-pointer ${
                    minDropPct === thresh.val
                      ? "bg-amber-500 text-white border-amber-600 shadow-xs"
                      : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {thresh.label}
                </button>
              ))}
            </div>
          </div>

          {/* Max Budget (Optional) */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5 flex items-center justify-between">
              <span>Ценовой потолок (бюджет тура)</span>
              <span className="text-[11px] font-semibold text-slate-400">Опционально</span>
            </label>
            <div className="relative">
              <input
                type="number"
                value={maxBudget}
                onChange={(e) => setMaxBudget(e.target.value)}
                placeholder="Например: 6000 (уведомлять только если цена ниже)"
                className="w-full pl-3.5 pr-10 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-sm font-semibold text-slate-800 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400">
                zł
              </span>
            </div>
          </div>

          {/* Notifications Channels */}
          <div className="pt-2 border-t border-slate-100 space-y-2">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={notifyTelegram}
                onChange={(e) => setNotifyTelegram(e.target.checked)}
                className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500"
              />
              <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
                <Send className="w-3.5 h-3.5 text-blue-500" />
                Мгновенный алерт в Telegram при падении цены
              </span>
            </label>
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
          >
            Отмена
          </button>

          <button
            type="button"
            disabled={isLoading || (sourceType === "FLY_URL" && (!parsedData || !parsedData.is_valid))}
            onClick={handleSubmit}
            className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-black text-xs tracking-tight shadow-md transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <span>Запустить мониторинг 🚀</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
