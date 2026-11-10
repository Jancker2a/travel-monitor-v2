import React from "react";
import { Loader2, Sparkles } from "lucide-react";

export interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg" | "xl";
  label?: string;
  description?: string;
  variant?: "inline" | "card" | "overlay" | "skeleton-table" | "skeleton-cards" | "skeleton-chart";
  className?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = "md",
  label,
  description,
  variant = "card",
  className = "",
}) => {
  // Size metrics
  const sizeMap = {
    sm: { spinner: "w-4 h-4", text: "text-xs", ring: "w-8 h-8", padding: "p-3" },
    md: { spinner: "w-6 h-6", text: "text-sm", ring: "w-12 h-12", padding: "p-6" },
    lg: { spinner: "w-8 h-8", text: "text-base", ring: "w-16 h-16", padding: "p-8" },
    xl: { spinner: "w-12 h-12", text: "text-lg", ring: "w-20 h-20", padding: "p-12" },
  };

  const { spinner, text, ring, padding } = sizeMap[size];

  // 1. Table Skeleton
  if (variant === "skeleton-table") {
    return (
      <div className={`w-full bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-2xs ${className}`}>
        {label && (
          <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              <span>{label}</span>
            </div>
            {description && <span className="text-[11px] text-slate-400">{description}</span>}
          </div>
        )}
        <div className="divide-y divide-slate-100">
          {[1, 2, 3, 4, 5].map((idx) => (
            <div key={idx} className="p-4 flex items-center justify-between gap-4 animate-pulse">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <div className="w-12 h-12 rounded-xl bg-slate-200 shrink-0" />
                <div className="space-y-2 flex-1">
                  <div className="h-4 bg-slate-200 rounded w-2/5" />
                  <div className="h-3 bg-slate-100 rounded w-1/4" />
                </div>
              </div>
              <div className="h-5 bg-slate-100 rounded w-20 hidden sm:block" />
              <div className="h-6 bg-slate-200 rounded w-24 shrink-0" />
              <div className="h-8 bg-slate-100 rounded-xl w-20 shrink-0" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  // 2. Chart Skeleton
  if (variant === "skeleton-chart") {
    return (
      <div className={`w-full bg-white rounded-2xl border border-slate-200 p-6 flex flex-col items-center justify-center min-h-[340px] shadow-2xs relative overflow-hidden ${className}`}>
        {/* Subtle background pulse wave */}
        <div className="absolute inset-0 flex items-end justify-between px-8 py-6 opacity-20 pointer-events-none gap-2">
          {[40, 65, 55, 80, 70, 95, 85, 60, 75, 90, 85, 100].map((h, i) => (
            <div
              key={i}
              className="flex-1 bg-gradient-to-t from-blue-500 to-indigo-500 rounded-t-md animate-pulse"
              style={{ height: `${h}%`, animationDelay: `${i * 80}ms` }}
            />
          ))}
        </div>

        <div className="relative z-10 flex flex-col items-center text-center max-w-sm">
          <div className="relative mb-3 flex items-center justify-center">
            <div className="absolute inset-0 rounded-full bg-blue-500/20 blur-md animate-ping" />
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-md shadow-blue-500/30">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          </div>
          <h4 className="text-sm font-extrabold text-slate-900 tracking-tight">
            {label || "Построение ценового графика..."}
          </h4>
          {description && (
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">{description}</p>
          )}
        </div>
      </div>
    );
  }

  // 3. Cards Skeleton
  if (variant === "skeleton-cards") {
    return (
      <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ${className}`}>
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="bg-white rounded-2xl border border-slate-200 p-4 space-y-3 animate-pulse shadow-2xs">
            <div className="h-40 bg-slate-200 rounded-xl w-full" />
            <div className="h-4 bg-slate-200 rounded w-3/4" />
            <div className="h-3 bg-slate-100 rounded w-1/2" />
            <div className="pt-2 flex justify-between items-center border-t border-slate-100">
              <div className="h-6 bg-slate-200 rounded w-20" />
              <div className="h-8 bg-slate-100 rounded-xl w-24" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Spinner Icon with glowing background
  const SpinnerGraphic = (
    <div className="relative flex items-center justify-center shrink-0">
      <div className={`absolute rounded-full bg-blue-500/15 blur-sm animate-pulse ${ring}`} />
      <div className={`rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-sm shadow-blue-500/25 ${ring}`}>
        <Loader2 className={`${spinner} animate-spin`} />
      </div>
    </div>
  );

  // 4. Inline Variant
  if (variant === "inline") {
    return (
      <div className={`inline-flex items-center gap-2.5 text-slate-600 ${className}`}>
        <Loader2 className="w-4 h-4 animate-spin text-blue-600 shrink-0" />
        {label && <span className={`font-semibold ${text}`}>{label}</span>}
      </div>
    );
  }

  // 5. Overlay Variant (fits absolute inset-0)
  if (variant === "overlay") {
    return (
      <div className={`absolute inset-0 bg-white/80 backdrop-blur-[2px] z-30 flex flex-col items-center justify-center rounded-2xl transition-all duration-200 ${className}`}>
        {SpinnerGraphic}
        {label && (
          <div className="mt-3 text-center px-4">
            <div className="font-extrabold text-slate-900 text-sm tracking-tight">{label}</div>
            {description && (
              <div className="text-xs text-slate-500 mt-0.5 leading-snug">{description}</div>
            )}
          </div>
        )}
      </div>
    );
  }

  // 6. Default Card Variant
  return (
    <div className={`w-full bg-white rounded-3xl border border-slate-200/90 ${padding} flex flex-col items-center justify-center text-center shadow-2xs ${className}`}>
      {SpinnerGraphic}
      {label && (
        <h4 className={`font-extrabold text-slate-900 tracking-tight mt-3.5 ${text}`}>
          {label}
        </h4>
      )}
      {description && (
        <p className="text-xs text-slate-500 mt-1 max-w-sm leading-relaxed">{description}</p>
      )}
    </div>
  );
};

