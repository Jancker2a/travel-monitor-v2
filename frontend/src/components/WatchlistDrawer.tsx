import React, { useState } from "react";
import {
  X,
  Trash2,
  Bell,
  BellOff,
  ExternalLink,
  ArrowDownRight,
  SlidersHorizontal,
  FileText,
  AlertTriangle,
  Check,
  Send,
  Sparkles,
} from "lucide-react";
import { WatchlistItem, UserProfile } from "../types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  items: WatchlistItem[];
  onDeleteItem: (watchId: string) => void;
  onUpdateItem?: (watchId: string, updates: Partial<WatchlistItem>) => void;
  onOpenPassport?: (hotelId: string) => void;
  currentUser?: UserProfile | null;
  onOpenUserSettings?: () => void;
}

export const WatchlistDrawer: React.FC<Props> = ({
  isOpen,
  onClose,
  items,
  onDeleteItem,
  onUpdateItem,
  onOpenPassport,
  currentUser,
  onOpenUserSettings,
}) => {
  const [expandedItemId, setExpandedItemId] = useState<string | null>(null);
  const [editingTargetPrice, setEditingTargetPrice] = useState<{ [watchId: string]: string }>({});

  if (!isOpen) return null;

  const hasTelegram = Boolean(currentUser?.telegram_chat_id?.trim());

  const handleToggleActive = (item: WatchlistItem, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onUpdateItem) return;
    const nextActive = item.is_active === false ? true : false;
    onUpdateItem(item.watch_id, { is_active: nextActive });
  };

  const handleSetThresholdPct = (item: WatchlistItem, pct: number | null) => {
    if (!onUpdateItem) return;
    onUpdateItem(item.watch_id, { alert_threshold_pct: pct ?? undefined, notify_any_drop: pct === null });
  };

  const handleSetMinDealScore = (item: WatchlistItem, score: number | null) => {
    if (!onUpdateItem) return;
    onUpdateItem(item.watch_id, { min_deal_score: score ?? undefined });
  };

  const handleSaveTargetPrice = (item: WatchlistItem) => {
    if (!onUpdateItem) return;
    const valStr = editingTargetPrice[item.watch_id];
    if (valStr === undefined) return;
    const val = parseFloat(valStr.replace(/[^\d.]/g, ""));
    onUpdateItem(item.watch_id, {
      target_price_pln: !isNaN(val) && val > 0 ? val : undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-slate-900 w-full max-w-md h-full shadow-2xl flex flex-col border-l border-slate-200 dark:border-slate-800">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Bell className="w-5 h-5 fill-current" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 dark:text-white text-base">
                Smart Watchlist & Алерты
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Мониторинг {items.length} избранных отелей
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Telegram status banner */}
        <div className="px-5 pt-4">
          {hasTelegram ? (
            <div className="p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/60 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-emerald-800 dark:text-emerald-300">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>
                  Telegram активен: <b>{currentUser?.telegram_chat_id}</b>
                </span>
              </div>
              {onOpenUserSettings && (
                <button
                  onClick={onOpenUserSettings}
                  className="px-2 py-1 rounded-lg bg-emerald-100 dark:bg-emerald-900/50 text-emerald-800 dark:text-emerald-200 hover:bg-emerald-200 font-bold text-[11px] transition-colors"
                >
                  Настроить
                </button>
              )}
            </div>
          ) : (
            <div className="p-3.5 rounded-2xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/60 flex items-start justify-between gap-3 text-xs">
              <div className="flex items-start gap-2 text-amber-800 dark:text-amber-300">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                <div>
                  <div className="font-bold">Telegram не подключен!</div>
                  <div className="text-[11px] text-amber-700/80 dark:text-amber-400/80 mt-0.5">
                    Укажите Chat ID, чтобы бот присылал алерты при падении цен.
                  </div>
                </div>
              </div>
              {onOpenUserSettings && (
                <button
                  onClick={onOpenUserSettings}
                  className="shrink-0 px-2.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-[11px] shadow-sm transition-all"
                >
                  Подключить
                </button>
              )}
            </div>
          )}
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3.5">
          {items.length === 0 ? (
            <div className="py-20 text-center text-slate-400">
              <Bell className="w-10 h-10 mx-auto text-slate-300 dark:text-slate-700 mb-3" />
              <p className="font-medium text-sm text-slate-600 dark:text-slate-300">
                Watchlist пока пуст
              </p>
              <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
                Нажимайте звездочку или колокольчик на карточке любого отеля, чтобы поставить тур на фоновый мониторинг.
              </p>
            </div>
          ) : (
            items.map((item) => {
              const isMuted = item.is_active === false;
              const isExpanded = expandedItemId === item.watch_id;
              const targetStr =
                editingTargetPrice[item.watch_id] !== undefined
                  ? editingTargetPrice[item.watch_id]
                  : item.target_price_pln ? String(item.target_price_pln) : "";

              return (
                <div
                  key={item.watch_id}
                  className={`rounded-2xl border transition-all shadow-sm flex flex-col justify-between overflow-hidden ${
                    isMuted
                      ? "border-slate-200 dark:border-slate-800 bg-slate-100/60 dark:bg-slate-900/40 opacity-75"
                      : "border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-800/40 hover:bg-white dark:hover:bg-slate-800"
                  }`}
                >
                  {/* Card Main Info */}
                  <div className="p-4">
                    <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1.5">
                      <div className="flex items-center gap-1.5 font-bold text-slate-700 dark:text-slate-300">
                        <span>{item.country}</span>
                        <span>•</span>
                        <span>🛫 {item.airport}</span>
                      </div>

                      {/* Mute/Active Bell Toggle */}
                      <button
                        type="button"
                        onClick={(e) => handleToggleActive(item, e)}
                        className={`p-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-all ${
                          isMuted
                            ? "bg-slate-200 dark:bg-slate-700 text-slate-500"
                            : "bg-amber-100/80 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300"
                        }`}
                        title={isMuted ? "Включить алерты" : "Поставить на паузу (Mute)"}
                      >
                        {isMuted ? <BellOff className="w-3.5 h-3.5" /> : <Bell className="w-3.5 h-3.5 fill-current" />}
                        <span className="text-[10px]">{isMuted ? "Пауза" : "Активен"}</span>
                      </button>
                    </div>

                    <h4 className="font-bold text-slate-900 dark:text-white text-sm line-clamp-1">
                      {item.hotel_name}
                    </h4>

                    <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mt-1">
                      <span>📅 {item.departure_date} ({item.duration_nights} ночей)</span>
                      {item.deal_score ? (
                        <span className="px-2 py-0.5 rounded-md bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 font-extrabold text-[10px]">
                          Deal Score {item.deal_score}
                        </span>
                      ) : null}
                    </div>

                    {/* Price and status bar */}
                    <div className="flex items-end justify-between pt-3 mt-2 border-t border-slate-200/60 dark:border-slate-700/60">
                      <div>
                        <div className="text-[11px] text-slate-400 font-medium">Текущая цена:</div>
                        <div className="text-base font-extrabold text-slate-900 dark:text-white">
                          {item.latest_price_pln ? item.latest_price_pln.toLocaleString("ru-RU") : "—"} zł
                        </div>
                        {item.target_price_pln ? (
                          <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 mt-0.5">
                            <ArrowDownRight className="w-3 h-3" />
                            Цель: {item.target_price_pln.toLocaleString("ru-RU")} zł
                            {item.target_reached && (
                              <span className="bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-200 text-[9px] px-1 rounded font-bold">
                                Достигнуто!
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="text-[10px] text-slate-400 mt-0.5">
                            Порог: падение {item.alert_threshold_pct ? `≥ ${item.alert_threshold_pct}%` : "любое"}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5">
                        {/* Expand thresholds editor */}
                        <button
                          type="button"
                          onClick={() => setExpandedItemId(isExpanded ? null : item.watch_id)}
                          className={`p-2 rounded-xl transition-colors ${
                            isExpanded
                              ? "bg-blue-600 text-white"
                              : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                          }`}
                          title="Тонкая настройка порогов цен"
                        >
                          <SlidersHorizontal className="w-3.5 h-3.5" />
                        </button>

                        {/* Open Hotel Passport */}
                        {onOpenPassport && item.hotel_id && (
                          <button
                            type="button"
                            onClick={() => onOpenPassport(item.hotel_id)}
                            className="p-2 rounded-xl bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 hover:bg-blue-100 transition-colors"
                            title="Открыть паспорт и график цен отеля"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </button>
                        )}

                        {/* Fly.pl link */}
                        {item.booking_url && (
                          <a
                            href={item.booking_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 transition-colors"
                            title="Открыть на Fly.pl"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        )}

                        {/* Delete button */}
                        <button
                          type="button"
                          onClick={() => onDeleteItem(item.watch_id)}
                          className="p-2 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 hover:bg-rose-100 transition-colors"
                          title="Удалить из мониторинга"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Fine-grained Alert Settings Drawer */}
                  {isExpanded && (
                    <div className="p-4 bg-white dark:bg-slate-800/90 border-t border-slate-200 dark:border-slate-700 space-y-3.5 animate-fade-in text-xs">
                      <div className="font-bold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                        <SlidersHorizontal className="w-3.5 h-3.5 text-blue-500" />
                        <span>Настройки алертов для отеля</span>
                      </div>

                      {/* 1. Target Price Input */}
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                          🎯 Целевая цена (уведомить если цена ≤):
                        </label>
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={targetStr}
                            onChange={(e) =>
                              setEditingTargetPrice((prev) => ({
                                ...prev,
                                [item.watch_id]: e.target.value,
                              }))
                            }
                            placeholder="Например: 6000"
                            className="flex-1 px-3 py-1.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
                          />
                          <button
                            type="button"
                            onClick={() => handleSaveTargetPrice(item)}
                            className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs transition-colors flex items-center gap-1"
                          >
                            <Check className="w-3 h-3" />
                            ОК
                          </button>
                        </div>
                      </div>

                      {/* 2. Drop % threshold chips */}
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                          📉 Порог падения цены:
                        </label>
                        <div className="grid grid-cols-4 gap-1.5">
                          {[
                            { label: "Любое", val: null },
                            { label: "≥ 5%", val: 5 },
                            { label: "≥ 10%", val: 10 },
                            { label: "≥ 15%", val: 15 },
                          ].map((chip) => {
                            const isSelected =
                              chip.val === null
                                ? Boolean(item.notify_any_drop && !item.alert_threshold_pct)
                                : item.alert_threshold_pct === chip.val;
                            return (
                              <button
                                key={chip.label}
                                type="button"
                                onClick={() => handleSetThresholdPct(item, chip.val)}
                                className={`py-1 rounded-lg text-[10px] font-bold transition-all border ${
                                  isSelected
                                    ? "bg-blue-600 text-white border-blue-600"
                                    : "bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-100"
                                }`}
                              >
                                {chip.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* 3. Min Deal Score filter */}
                      <div>
                        <label className="block text-[11px] font-bold text-slate-600 dark:text-slate-400 mb-1">
                          🔥 Фильтр качества сделки (Deal Score):
                        </label>
                        <div className="grid grid-cols-3 gap-1.5">
                          {[
                            { label: "Любой", val: null },
                            { label: "Good (≥75)", val: 75 },
                            { label: "Hot (≥85)", val: 85 },
                          ].map((chip) => {
                            const isSelected = item.min_deal_score === chip.val;
                            return (
                              <button
                                key={chip.label}
                                type="button"
                                onClick={() => handleSetMinDealScore(item, chip.val)}
                                className={`py-1 rounded-lg text-[10px] font-bold transition-all border ${
                                  isSelected
                                    ? "bg-amber-500 text-white border-amber-500"
                                    : "bg-slate-50 dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-100"
                                }`}
                              >
                                {chip.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer info */}
        <div className="p-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-blue-500" />
            <span>Алерты отправляются ботом при сканировании</span>
          </div>
          {onOpenUserSettings && (
            <button
              onClick={onOpenUserSettings}
              className="text-blue-600 dark:text-blue-400 font-bold hover:underline"
            >
              Настройки Telegram →
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
