import React from "react";
import { Plane, TrendingDown, Award } from "lucide-react";
import { AirportStat } from "../types";

interface Props {
  stats: AirportStat[];
}

export const AirportComparisonWidget: React.FC<Props> = ({ stats }) => {
  if (!stats || stats.length === 0) return null;

  const minPrice = Math.min(...stats.map((s) => s.avg_price_pln));
  const maxPrice = Math.max(...stats.map((s) => s.avg_price_pln));
  const range = maxPrice - minPrice || 1;

  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-5 mb-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-xl bg-blue-600 text-white shadow-sm shadow-blue-500/20">
            <Plane className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Сравнение цен вылетов по городам (Аэропорты)
            </h3>
            <p className="text-[11px] text-slate-500">
              Средняя стоимость тура и минимальный порог входа по каждому направлению
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {stats.map((s, idx) => {
          const isCheapest = s.avg_price_pln === minPrice;
          const barPct = Math.max(15, ((s.avg_price_pln - minPrice) / range) * 85 + 15);

          return (
            <div
              key={s.airport_code}
              className={`p-3.5 rounded-2xl border transition-all ${
                isCheapest
                  ? "bg-emerald-50/60 border-emerald-300 ring-1 ring-emerald-400"
                  : "bg-slate-50/70 border-slate-200 hover:bg-slate-100/60"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-extrabold text-xs text-slate-900 flex items-center gap-1.5">
                  <span>🛫</span>
                  <span>{s.airport_code}</span>
                  {isCheapest && (
                    <span className="text-[9px] font-bold bg-emerald-600 text-white px-1.5 py-0.2 rounded-full uppercase flex items-center gap-0.5">
                      <Award className="w-2.5 h-2.5" />
                      Выгодно
                    </span>
                  )}
                </span>
                <span className="text-[10px] text-slate-500 font-medium">
                  {s.hotel_count} отелей
                </span>
              </div>

              <div className="text-base font-black text-slate-900 leading-tight">
                {s.avg_price_pln.toLocaleString("ru-RU")} <span className="text-xs font-semibold text-slate-500">zł ср.</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                от <span className="font-bold text-slate-700">{s.min_price_pln.toLocaleString("ru-RU")} zł</span> • {s.avg_night_pax.toFixed(0)} zł/ночь/чел.
              </div>

              {/* Visual Relative Cost Bar */}
              <div className="mt-2.5 w-full bg-slate-200/80 rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    isCheapest ? "bg-emerald-500" : "bg-blue-500"
                  }`}
                  style={{ width: `${barPct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
