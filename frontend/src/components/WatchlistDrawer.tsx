import React from "react";
import { X, Trash2, Bell, CheckCircle2, ExternalLink, ArrowDownRight } from "lucide-react";
import { WatchlistItem } from "../types";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  items: WatchlistItem[];
  onDeleteItem: (watchId: string) => void;
}

export const WatchlistDrawer: React.FC<Props> = ({
  isOpen,
  onClose,
  items,
  onDeleteItem,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-sm animate-fade-in">
      <div className="bg-white w-full max-w-md h-full shadow-2xl flex flex-col border-l border-slate-200">
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-amber-50 text-amber-600">
              <Bell className="w-5 h-5 fill-current" />
            </div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">Ваш Smart Watchlist</h3>
              <p className="text-xs text-slate-500">Отслеживание {items.length} туров</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3">
          {items.length === 0 ? (
            <div className="py-20 text-center text-slate-400">
              <Bell className="w-10 h-10 mx-auto text-slate-300 mb-3" />
              <p className="font-medium text-sm text-slate-600">Watchlist пока пуст</p>
              <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
                Нажимайте колокольчик на карточке любого отеля, чтобы поставить тур на фоновый мониторинг.
              </p>
            </div>
          ) : (
            items.map((item) => (
              <div
                key={item.watch_id}
                className="p-4 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-white transition-all shadow-sm flex flex-col justify-between gap-3"
              >
                <div>
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                    <span className="font-semibold text-slate-700">{item.country}</span>
                    <span>🛫 {item.airport}</span>
                  </div>
                  <h4 className="font-bold text-slate-900 text-sm line-clamp-1">
                    {item.hotel_name}
                  </h4>
                  <div className="text-xs text-slate-500 mt-1">
                    📅 {item.departure_date} ({item.duration_nights} ночей)
                  </div>
                </div>

                {/* Price and status */}
                <div className="flex items-end justify-between pt-2 border-t border-slate-200/60">
                  <div>
                    <div className="text-xs text-slate-400 font-medium">Текущая цена:</div>
                    <div className="text-base font-extrabold text-slate-900">
                      {item.latest_price_pln.toLocaleString("ru-RU")} zł
                    </div>
                    {item.target_price_pln && (
                      <div className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1 mt-0.5">
                        <ArrowDownRight className="w-3 h-3" />
                        Цель: {item.target_price_pln.toLocaleString("ru-RU")} zł
                        {item.target_reached && (
                          <span className="bg-emerald-100 text-emerald-800 text-[10px] px-1 rounded">Достигнуто!</span>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5">
                    {item.booking_url && (
                      <a
                        href={item.booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 rounded-xl bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors"
                        title="Открыть на Fly.pl"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                    <button
                      onClick={() => onDeleteItem(item.watch_id)}
                      className="p-2 rounded-xl bg-rose-50 text-rose-600 hover:bg-rose-100 transition-colors"
                      title="Удалить из мониторинга"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer info */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 text-center text-xs text-slate-500">
          🤖 Уведомления о падении цен отправляются в Telegram Bot автоматически.
        </div>
      </div>
    </div>
  );
};

