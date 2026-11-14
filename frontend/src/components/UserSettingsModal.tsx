import React, { useState, useEffect } from "react";
import {
  X,
  Send,
  BellRing,
  Check,
  AlertCircle,
  ShieldCheck,
  User as UserIcon,
  MessageSquare,
  ExternalLink,
  Loader2,
  Calendar,
  Clock,
  Sparkles,
  Flame,
  Award,
  Layers,
  Moon,
} from "lucide-react";
import { UserProfile } from "../types";
import { updateUserProfile, sendTestTelegram, sendTestDailyDigest } from "../services/api";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile;
  onUserUpdated: (user: UserProfile) => void;
}

export const UserSettingsModal: React.FC<Props> = ({
  isOpen,
  onClose,
  currentUser,
  onUserUpdated,
}) => {
  const [activeTab, setActiveTab] = useState<"profile" | "digest">("profile");

  // Profile & Telegram states
  const [fullName, setFullName] = useState(currentUser.full_name || "");
  const [telegramChatId, setTelegramChatId] = useState(currentUser.telegram_chat_id || "");
  const [notificationsEnabled, setNotificationsEnabled] = useState(
    currentUser.telegram_notifications_enabled !== false
  );

  // Daily Digest states
  const [digestEnabled, setDigestEnabled] = useState(currentUser.digest_enabled !== false);
  const [digestTime, setDigestTime] = useState(currentUser.digest_time || "09:00");
  const [digestDays, setDigestDays] = useState(currentUser.digest_days || "ALL");
  const [includeWatchlist, setIncludeWatchlist] = useState(currentUser.digest_include_watchlist !== false);
  const [includeTopDrops, setIncludeTopDrops] = useState(currentUser.digest_include_top_drops !== false);
  const [includeHotDeals, setIncludeHotDeals] = useState(currentUser.digest_include_hot_deals !== false);
  const [includeHistoricLows, setIncludeHistoricLows] = useState(currentUser.digest_include_historic_lows !== false);
  const [minDealScore, setMinDealScore] = useState<number>(currentUser.digest_min_deal_score || 80);
  const [maxOffers, setMaxOffers] = useState<number>(currentUser.digest_max_offers || 5);
  const [onlyIfChanges, setOnlyIfChanges] = useState(currentUser.digest_only_if_changes !== false);

  // Quiet hours
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(currentUser.quiet_hours_enabled !== false);

  // Feedback states
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Test states
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const [isTestingDigest, setIsTestingDigest] = useState(false);
  const [digestResult, setDigestResult] = useState<{ success: boolean; message: string } | null>(null);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setErrorMsg(null);
    setSaveSuccess(false);

    try {
      const updated = await updateUserProfile({
        full_name: fullName.trim() || undefined,
        telegram_chat_id: telegramChatId.trim() || undefined,
        telegram_notifications_enabled: notificationsEnabled,
        digest_enabled: digestEnabled,
        digest_time: digestTime,
        digest_days: digestDays,
        digest_include_watchlist: includeWatchlist,
        digest_include_top_drops: includeTopDrops,
        digest_include_hot_deals: includeHotDeals,
        digest_include_historic_lows: includeHistoricLows,
        digest_min_deal_score: minDealScore,
        digest_max_offers: maxOffers,
        digest_only_if_changes: onlyIfChanges,
        quiet_hours_enabled: quietHoursEnabled,
      });
      onUserUpdated(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || "Не удалось сохранить настройки");
    } finally {
      setIsSaving(false);
    }
  };

  const handleSendTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    setErrorMsg(null);

    const targetId = telegramChatId.trim();
    if (!targetId) {
      setTestResult({
        success: false,
        message: "Пожалуйста, сначала укажите Telegram Chat ID.",
      });
      setIsTesting(false);
      return;
    }

    try {
      if (targetId !== currentUser.telegram_chat_id) {
        const updated = await updateUserProfile({
          telegram_chat_id: targetId,
          telegram_notifications_enabled: notificationsEnabled,
        });
        onUserUpdated(updated);
      }

      const res = await sendTestTelegram(targetId);
      setTestResult({
        success: res.success,
        message: res.message,
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        message: err.message || "Ошибка при отправке тестового сообщения",
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSendTestDigest = async () => {
    setIsTestingDigest(true);
    setDigestResult(null);
    setErrorMsg(null);

    const targetId = telegramChatId.trim();
    if (!targetId) {
      setDigestResult({
        success: false,
        message: "Сначала укажите ваш Telegram Chat ID на вкладке Профиль.",
      });
      setIsTestingDigest(false);
      return;
    }

    try {
      // Save digest settings first
      await updateUserProfile({
        telegram_chat_id: targetId,
        digest_enabled: digestEnabled,
        digest_time: digestTime,
        digest_days: digestDays,
        digest_include_watchlist: includeWatchlist,
        digest_include_top_drops: includeTopDrops,
        digest_include_hot_deals: includeHotDeals,
        digest_include_historic_lows: includeHistoricLows,
        digest_min_deal_score: minDealScore,
        digest_max_offers: maxOffers,
        digest_only_if_changes: onlyIfChanges,
      });

      const res = await sendTestDailyDigest();
      setDigestResult({
        success: res.success,
        message: res.message,
      });
    } catch (err: any) {
      setDigestResult({
        success: false,
        message: err.message || "Ошибка при отправке тестового дайджеста",
      });
    } finally {
      setIsTestingDigest(false);
    }
  };

  const isConnected = Boolean(telegramChatId.trim());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold">
              <UserIcon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 dark:text-white">
                Настройки профиля и алертов
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Управление Telegram-ботом, ежедневным дайджестом и аккаунтом
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

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 dark:border-slate-800 bg-slate-100/60 dark:bg-slate-800/40 p-1.5 gap-1.5 px-5">
          <button
            type="button"
            onClick={() => setActiveTab("profile")}
            className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
              activeTab === "profile"
                ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-xs"
                : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Telegram & Профиль</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("digest")}
            className={`flex-1 py-2 px-3 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
              activeTab === "digest"
                ? "bg-white dark:bg-slate-900 text-amber-600 dark:text-amber-400 shadow-xs"
                : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>🌅 Ежедневный дайджест</span>
          </button>
        </div>

        {/* Scrollable Body */}
        <form onSubmit={handleSave} className="p-6 overflow-y-auto space-y-6">
          {errorMsg && (
            <div className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {saveSuccess && (
            <div className="p-3.5 rounded-2xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/60 text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-2.5 animate-fade-in">
              <Check className="w-4 h-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <span>Настройки успешно сохранены!</span>
            </div>
          )}

          {activeTab === "profile" && (
            <div className="space-y-6">
              {/* Account Details */}
              <div className="space-y-3">
                <h3 className="text-xs font-black uppercase tracking-wider text-slate-400">
                  Личные данные
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Ваше имя
                    </label>
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Андрей"
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500 font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      value={currentUser.email}
                      disabled
                      className="w-full px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/80 text-xs text-slate-500 dark:text-slate-400 cursor-not-allowed font-medium"
                    />
                  </div>
                </div>
              </div>

              {/* Telegram Integration Card */}
              <div className="p-4 rounded-2xl bg-gradient-to-br from-blue-500/5 via-indigo-500/5 to-transparent border border-blue-200/80 dark:border-blue-900/50 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-blue-500 text-white flex items-center justify-center font-black text-sm shadow-sm shadow-blue-500/20">
                      ✈️
                    </div>
                    <div>
                      <h4 className="text-xs font-black text-slate-900 dark:text-white">
                        Подключение Telegram
                      </h4>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {isConnected ? "Бот привязан к вашему аккаунту" : "Укажите Chat ID для получения алертов"}
                      </p>
                    </div>
                  </div>

                  {isConnected && (
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      ПОДКЛЮЧЕН
                    </span>
                  )}
                </div>

                {/* Master Switch */}
                <div className="flex items-center justify-between pt-2 border-t border-blue-100 dark:border-blue-900/30">
                  <div className="flex items-center gap-2">
                    <BellRing className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                      Мастер-тумблер Telegram-уведомлений
                    </span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={notificationsEnabled}
                      onChange={(e) => setNotificationsEnabled(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-slate-200 peer-focus:outline-hidden rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {/* Chat ID Input & Test Button */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Telegram Chat ID
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={telegramChatId}
                      onChange={(e) => setTelegramChatId(e.target.value)}
                      placeholder="Например: 123456789"
                      className="flex-1 px-3.5 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs text-slate-900 dark:text-white focus:outline-hidden focus:ring-2 focus:ring-blue-500 font-mono"
                    />
                    <button
                      type="button"
                      onClick={handleSendTest}
                      disabled={isTesting || !telegramChatId.trim()}
                      className="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs tracking-tight transition-all flex items-center gap-1.5 cursor-pointer shadow-sm disabled:cursor-not-allowed shrink-0"
                    >
                      {isTesting ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          <span>Шлём...</span>
                        </>
                      ) : (
                        <>
                          <Send className="w-3.5 h-3.5" />
                          <span>Тест</span>
                        </>
                      )}
                    </button>
                  </div>
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

                {/* Connection Instructions */}
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/80 text-[11px] text-slate-600 dark:text-slate-400 space-y-1.5">
                  <p className="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                    <span>💡 Как подключить бота за 1 минуту:</span>
                  </p>
                  <ol className="list-decimal list-inside space-y-1 text-slate-600 dark:text-slate-400 pl-1 leading-relaxed">
                    <li>
                      Откройте бота <b className="text-slate-800 dark:text-slate-200">@userinfobot</b> в Telegram, чтобы скопировать свой числовой <b>Id</b>.
                    </li>
                    <li>
                      Вставьте ID в поле выше и сохраните.
                    </li>
                    <li>
                      Перейдите в бота мониторинга и нажмите кнопку <b className="text-blue-600 dark:text-blue-400">/start</b>.
                    </li>
                    <li>
                      Нажмите кнопку <b className="text-slate-800 dark:text-slate-200">«Тест»</b> выше, чтобы проверить доставку.
                    </li>
                  </ol>
                </div>
              </div>
            </div>
          )}

          {activeTab === "digest" && (
            <div className="space-y-5">
              {/* Digest Master Switch */}
              <div className="p-4 rounded-2xl bg-amber-500/5 border border-amber-200/70 dark:border-amber-900/50 flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-black text-slate-900 dark:text-white flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-amber-500" />
                    <span>Ежедневный дайджест в Telegram</span>
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    Утренняя структурированная сводка цен, новых минимумов и лучших Hot Deals
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={digestEnabled}
                    onChange={(e) => setDigestEnabled(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-slate-200 peer-focus:outline-hidden rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-slate-600 peer-checked:bg-amber-500"></div>
                </label>
              </div>

              {/* Time & Days Row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Время доставки
                  </label>
                  <select
                    value={digestTime}
                    onChange={(e) => setDigestTime(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs font-bold text-slate-800 dark:text-white"
                  >
                    <option value="07:00">07:00 (Раннее утро)</option>
                    <option value="08:00">08:00 (Перед работой)</option>
                    <option value="09:00">09:00 (Стандартный утренний)</option>
                    <option value="10:00">10:00 (После первых чартеров)</option>
                    <option value="12:00">12:00 (Обеденный замер)</option>
                    <option value="19:00">19:00 (Вечерняя сводка)</option>
                    <option value="21:00">21:00 (Перед сном)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Дни отправки
                  </label>
                  <div className="grid grid-cols-3 gap-1">
                    {[
                      { id: "ALL", label: "Каждый день" },
                      { id: "WEEKDAYS", label: "Будни" },
                      { id: "WEEKENDS", label: "Выходные" },
                    ].map((d) => (
                      <button
                        key={d.id}
                        type="button"
                        onClick={() => setDigestDays(d.id)}
                        className={`py-2 rounded-xl text-[11px] font-bold transition-all ${
                          digestDays === d.id
                            ? "bg-amber-500 text-slate-950 font-black shadow-xs"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
                        }`}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* What to include (Interactive Checkboxes) */}
              <div className="space-y-2">
                <label className="block text-xs font-black uppercase tracking-wider text-slate-400">
                  Состав дайджеста
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 cursor-pointer hover:bg-slate-100/60 dark:hover:bg-slate-800">
                    <input
                      type="checkbox"
                      checked={includeWatchlist}
                      onChange={(e) => setIncludeWatchlist(e.target.checked)}
                      className="rounded text-amber-500 focus:ring-amber-500 w-4 h-4"
                    />
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      🏨 Отели из Watchlist
                    </span>
                  </label>

                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 cursor-pointer hover:bg-slate-100/60 dark:hover:bg-slate-800">
                    <input
                      type="checkbox"
                      checked={includeTopDrops}
                      onChange={(e) => setIncludeTopDrops(e.target.checked)}
                      className="rounded text-amber-500 focus:ring-amber-500 w-4 h-4"
                    />
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      📉 Топ падений цен за сутки
                    </span>
                  </label>

                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 cursor-pointer hover:bg-slate-100/60 dark:hover:bg-slate-800">
                    <input
                      type="checkbox"
                      checked={includeHotDeals}
                      onChange={(e) => setIncludeHotDeals(e.target.checked)}
                      className="rounded text-amber-500 focus:ring-amber-500 w-4 h-4"
                    />
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      🔥 Лучшие Hot Deals
                    </span>
                  </label>

                  <label className="flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 cursor-pointer hover:bg-slate-100/60 dark:hover:bg-slate-800">
                    <input
                      type="checkbox"
                      checked={includeHistoricLows}
                      onChange={(e) => setIncludeHistoricLows(e.target.checked)}
                      className="rounded text-amber-500 focus:ring-amber-500 w-4 h-4"
                    />
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-300">
                      🏆 Рекордные минимумы
                    </span>
                  </label>
                </div>
              </div>

              {/* Deal Score Threshold & Max Offers */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Порог Deal Score для дайджеста
                  </label>
                  <div className="flex gap-1">
                    {[
                      { val: 0, label: "Любой" },
                      { val: 80, label: "80+" },
                      { val: 85, label: "85+ 🔥" },
                      { val: 90, label: "90+ Hot" },
                    ].map((s) => (
                      <button
                        key={s.val}
                        type="button"
                        onClick={() => setMinDealScore(s.val)}
                        className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition-all ${
                          minDealScore === s.val
                            ? "bg-blue-600 text-white"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-slate-900"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Предложений в блоке
                  </label>
                  <div className="flex gap-1">
                    {[3, 5, 10].map((num) => (
                      <button
                        key={num}
                        type="button"
                        onClick={() => setMaxOffers(num)}
                        className={`flex-1 py-1.5 rounded-xl text-xs font-bold transition-all ${
                          maxOffers === num
                            ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900"
                            : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400"
                        }`}
                      >
                        Топ-{num}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Only if changes toggle */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800">
                <div>
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200 block">
                    Умный режим («Без спама»)
                  </span>
                  <span className="text-[11px] text-slate-500">
                    Не отправлять дайджест, если на рынке не было изменений цен
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={onlyIfChanges}
                  onChange={(e) => setOnlyIfChanges(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
                />
              </div>

              {/* Instant Test Digest Button */}
              <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between">
                <div>
                  <span className="text-xs font-black text-amber-900 dark:text-amber-200 block">
                    Проверить вид дайджеста в Telegram
                  </span>
                  <span className="text-[11px] text-amber-700/80 dark:text-amber-300/70">
                    Сформирует реальную сводку по текущей базе и пришлет на телефон
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleSendTestDigest}
                  disabled={isTestingDigest || !telegramChatId.trim()}
                  className="px-3 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-xs tracking-tight transition-all flex items-center gap-1.5 cursor-pointer shadow-sm shrink-0"
                >
                  {isTestingDigest ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Формируем...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>⚡ Отправить сейчас</span>
                    </>
                  )}
                </button>
              </div>

              {digestResult && (
                <div
                  className={`p-3 rounded-xl text-xs flex items-start gap-2 ${
                    digestResult.success
                      ? "bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
                      : "bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300"
                  }`}
                >
                  {digestResult.success ? (
                    <Check className="w-4 h-4 shrink-0 text-emerald-600 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                  )}
                  <span>{digestResult.message}</span>
                </div>
              )}
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
                  <span>Сохранить настройки</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
