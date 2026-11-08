import React from "react";
import { Flame, ArrowDownRight, ExternalLink } from "lucide-react";
import { PriceDropItem } from "../types";

interface Props {
  drops: PriceDropItem[];
  onSelectHotel: (hotelId: string) => void;
}

export const TopDropsCarousel: React.FC<Props> = ({ drops, onSelectHotel }) => {
  if (!drops || drops.length === 0) return null;

  return (
    <div className="bg-gradient-to-r from-amber-500/10 via-rose-500/10 to-blue-500/10 border border-amber-200/60 rounded-3xl p-5 mb-6">
      <div className="flex items-center justify-between mb-3.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-xl bg-amber-500 text-white shadow-sm shadow-amber-500/30">
            <Flame className="w-4 h-4 fill-current" />
          </div>
          <div>
            <h3 className="text-sm font-black text-slate-900 tracking-tight flex items-center gap-2">
              <span>РАДАР СКИДОК: ТОП ПАДЕНИЙ ЗА 24–48 ЧАСОВ</span>
              <span className="text-[10px] bg-rose-500 text-white font-bold px-1.5 py-0.2 rounded-full">
                LIVE
              </span>
            </h3>
            <p className="text-[11px] text-slate-500">
              Отели с максимальным снижением цены относительно предыдущего замера
            </p>
          </div>
        </div>
      </div>

      {/* Horizontal Scroll Carousel */}
      <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-none">
        {drops.map((item) => (
          <div
            key={item.cohort_hash}
            className="w-72 shrink-0 bg-white rounded-2xl p-3.5 border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                <span className="font-semibold text-slate-700">{item.country}</span>
                <span className="bg-slate-100 font-medium px-1.5 py-0.5 rounded text-[10px]">
                  🛫 {item.airport}
                </span>
              </div>
              <h4 className="font-bold text-slate-900 text-xs line-clamp-1 mb-1">
                {item.hotel_name}
              </h4>
              <div className="text-[11px] text-slate-500 mb-2">
                📅 {item.departure_date} ({item.duration_nights} ночей)
              </div>
            </div>

            {/* Price change badge & CTA */}
            <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
              <div>
                <div className="text-[10px] text-slate-400 line-through">
                  {item.previous_price_pln.toLocaleString("ru-RU")} zł
                </div>
                <div className="text-sm font-extrabold text-slate-900 flex items-center gap-1">
                  <span>{item.current_price_pln.toLocaleString("ru-RU")} zł</span>
                  <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1 py-0.5 rounded flex items-center">
                    <ArrowDownRight className="w-3 h-3" />
                    -{item.drop_amount_pln.toFixed(0)} zł
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onSelectHotel(item.hotel_id)}
                  className="px-2 py-1.5 rounded-lg text-[10px] font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                >
                  Паспорт
                </button>
                {item.booking_url && (
                  <a
                    href={item.booking_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                    title="Забронировать на Fly.pl"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
