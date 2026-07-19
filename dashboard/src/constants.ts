// Shared category colors. Previously copy-pasted into four page components
// (and missing Health), which is how a Health row silently fell back to gray.
export const CAT_COLORS: Record<string, string> = {
  Politics: "#2563eb",
  Economics: "#10b981",
  Sports: "#ef4444",
  Entertainment: "#f59e0b",
  "Climate and Weather": "#06b6d4",
  Elections: "#8b5cf6",
  Financials: "#ec4899",
  Crypto: "#f97316",
  Companies: "#84cc16",
  World: "#6366f1",
  Mentions: "#14b8a6",
  "Science and Technology": "#a855f7",
  Social: "#78716c",
  Health: "#e11d48",
  Education: "#0ea5e9",
};

export const catColor = (cat: string): string => CAT_COLORS[cat] || "#6b7280";

export const TIME_HORIZONS = ["30+ days", "7-30 days", "1-7 days", "< 24 hours"];
export const TIME_COLORS = ["#ef4444", "#f59e0b", "#10b981", "#2563eb"];
