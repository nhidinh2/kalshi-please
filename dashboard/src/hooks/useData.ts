import { useState, useEffect } from "react";
import type { Summary, DashboardData, MarketFeature } from "../types";

const BASE = import.meta.env.BASE_URL;

async function loadJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

export function useSummary() {
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadJSON<Summary>("data/summary.json")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);
  return { data, loading };
}

export function useDashboardData() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadJSON<DashboardData>("data/dashboard_data.json")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);
  return { data, loading };
}

export function useMarketFeatures() {
  const [data, setData] = useState<MarketFeature[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    loadJSON<MarketFeature[]>("data/market_features.json")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);
  return { data, loading };
}
