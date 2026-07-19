export interface CalibrationBin {
  bin_center: number;
  mean_predicted: number;
  realized_frequency: number;
  count: number;
  calibration_error: number;
  brier_score?: number;
  log_loss?: number;
  abs_error?: number;
  n_observations?: number;
  n_markets?: number;
  time_horizon?: string;
  liquidity?: string;
}

export interface MarketFeature {
  market_ticker: string;
  event_ticker: string;
  category: string;
  event_title: string;
  yes_sub_title: string;
  result: string;
  result_binary: number;
  open_time: string;
  close_time: string;
  duration_hours: number;
  n_price_observations: number;
  total_volume: number;
  avg_daily_volume: number;
  last_price: number | null;
  price_1d_before: number | null;
  price_3d_before: number | null;
  price_7d_before: number | null;
  avg_spread: number | null;
  price_volatility: number | null;
  liquidity_bucket: string;
  brier_score: number | null;
}

export interface CategoryStats {
  n_markets: number;
  brier: number;
  brier_last_tick: number;
  brier_1d_before: number | null;
  n_markets_1d: number;
  brier_7d_before: number | null;
  n_markets_7d: number;
  avg_volume: number;
  yes_rate: number;
}

export interface Summary {
  total_markets: number;
  total_observations: number;
  n_categories: number;
  n_categories_all: number;
  yes_outcomes: number;
  no_outcomes: number;
  overall_brier_score: number;
  overall_brier_1d_before: number | null;
  overall_brier_7d_before: number | null;
  overall_log_loss: number;
  mean_volume: number;
  median_volume: number;
  mean_duration_hours: number;
  n_hourly_clock_markets: number;
  categories: Record<string, number>;
  liquidity_distribution: Record<string, number>;
  category_stats: Record<string, CategoryStats>;
}

export interface DomainTimeEntry {
  brier: number;
  log_loss: number;
  abs_error: number;
  n: number;
  n_markets: number;
  cal_curve: CalibrationBin[];
}

export interface FeatureCorrelation {
  feature: string;
  label: string;
  spearman_r: number;
  p_value: number;
  n: number;
  significant: boolean;
}

export interface RegressionCoefficient {
  feature: string;
  label: string;
  coefficient: number;
  direction: string;
}

export interface CategoryProfile {
  category: string;
  brier_score: number;
  avg_spread: number | null;
  total_volume: number | null;
  n_price_observations: number | null;
  duration_hours: number | null;
  price_volatility: number | null;
  late_volatility: number | null;
  late_price_move: number | null;
  price_range: number | null;
  late_volume_share: number | null;
  yes_rate: number;
  n_markets: number;
  base_rate_imbalance: number;
}

export interface CategoryNarrative {
  text: string;
  quality: string;
  reasons: string[];
  brier: number;
}

export interface ExplanatoryData {
  correlations: FeatureCorrelation[];
  category_profiles: CategoryProfile[];
  regression_r2: number | null;
  regression_coefficients: RegressionCoefficient[];
  category_correlations: FeatureCorrelation[];
  narratives: Record<string, CategoryNarrative>;
}

export interface ModelComparison {
  model: string;
  r2: number;
  adj_r2: number;
  aic: number;
  n: number;
}

export interface DomainCoefficient {
  category: string;
  coef_no_controls: number | null;
  p_no_controls: number | null;
  coef_with_controls: number;
  p_with_controls: number;
  survives: boolean;
}

export interface ControlCoefficient {
  feature: string;
  coefficient: number;
  p_value: number;
  significant: boolean;
}

export interface RegressionData {
  model_comparison: ModelComparison[];
  domain_coefficients: DomainCoefficient[];
  control_coefficients: ControlCoefficient[];
  r2_with_domain: number;
  r2_without_domain: number;
  r2_lift: number;
  verdict: string;
  surviving_domains: string[];
  n_sig_interactions: number;
  n_interactions: number;
  reference_category: string;
}

export interface CategoryImprovement {
  category: string;
  raw_brier: number;
  recalibrated_brier: number;
  improvement_pct: number;
  n_test: number;
}

export interface DomainCI {
  category: string;
  effect: number;
  ci_lower: number;
  ci_upper: number;
  significant: boolean;
}

export interface RecalibrationData {
  raw_brier: number;
  recalibrated_brier: number;
  improvement_pct: number;
  improvement_mean_pct: number;
  improvement_sd_pct: number;
  improvement_se_pct: number;
  improvement_range_pct: [number, number];
  improvement_reliable: boolean;
  n_seeds: number;
  n_observations: number;
  n_markets: number;
  n_folds: number;
  category_improvements: CategoryImprovement[];
  confidence_intervals: DomainCI[];
  reference_category: string;
}

export interface DashboardData {
  overall_calibration: CalibrationBin[];
  time_horizon_calibration: Record<string, CalibrationBin[]>;
  liquidity_calibration: Record<string, CalibrationBin[]>;
  domain_time_matrix: Record<string, Record<string, DomainTimeEntry>>;
  explanatory: ExplanatoryData;
  regression: RegressionData;
  recalibration: RecalibrationData;
}
