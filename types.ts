export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'INSUFFICIENT_EVIDENCE';

export interface User {
  id: number;
  full_name: string;
  email: string;
  phone?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ConsentListItem {
  id: number;
  organisation: string;
  service_name: string;
  original_purpose: string;
  original_consent_text?: string | null;
  data_categories: string[];
  source_type: 'official_text' | 'user_summary';
  consent_date: string | null;
  created_at: string;
  latest_risk: RiskLevel | null;
  latest_score?: number | null;
  analyses_count: number;
}

export interface EvidenceRead {
  id: number;
  consent_id: number;
  title: string;
  evidence_type: 'email' | 'policy' | 'notification' | 'sms' | 'other';
  content: string;
  source: string | null;
  file_name?: string | null;
  content_hash: string;
  submitted_at: string;
  integrity_status?: string;
}

export interface QuoteSpan {
  start: number;
  end: number;
  text?: string;
  quote?: string;
}

export interface RuleSignal {
  signal: string;
  matched_text: string;
  category?: string;
  start?: number;
  end?: number;
}

export interface ScoreSignalBreakdown {
  signal: string;
  matched_text: string;
  weight: number;
  covered_by_baseline: boolean;
  score_contribution: number;
}

export interface ScoreBreakdown {
  final_score: number;
  risk: RiskLevel;
  base_score: number;
  quote_bonus?: number;
  formula: string;
  signals: ScoreSignalBreakdown[];
}

export interface AnalysisRead {
  id: number;
  evidence_id: number;
  consent_id: number;
  mode: 'rules-only' | 'hybrid';
  risk: RiskLevel;
  score: number;
  score_breakdown: ScoreBreakdown;
  highlight_spans: number[][];
  original_purposes: string[];
  new_purposes: string[];
  data_categories_affected: string[];
  third_party_sharing: 'yes' | 'no' | 'unclear';
  evidence_quotes: string[];
  rule_signals: RuleSignal[];
  explanation: string;
  recommended_action: string;
  statement_labels: {
    directly_stated: string[];
    ai_interpretation: string[];
  };
  warnings: string[];
  created_at: string;
  evidence_content?: string;
  quote_spans?: QuoteSpan[];
  consent_service_name?: string;
  consent_organisation?: string;
  consent_original_purpose?: string;
  integrity_status?: string;
}

export interface ConsentDetail extends ConsentListItem {
  evidence: EvidenceRead[];
  analyses: AnalysisRead[];
}

export interface ConsentCreateInput {
  organisation: string;
  service_name: string;
  original_purpose: string;
  original_consent_text?: string;
  data_categories: string[];
  source_type: 'official_text' | 'user_summary';
  consent_date?: string | null;
}

export interface EvidenceCreateInput {
  consent_id: number;
  title: string;
  evidence_type: 'email' | 'policy' | 'notification' | 'sms' | 'other';
  content: string;
  source?: string;
  file_name?: string;
}

export interface AlertEvent {
  id: number;
  alert_id: number;
  event: string;
  created_at: string;
}

export type AlertStatus = 'new' | 'acknowledged' | 'clarification_sent' | 'resolved' | 'dismissed';

export interface Alert {
  id: number;
  user_id: number;
  analysis_id: number;
  consent_id: number;
  risk: 'MEDIUM' | 'HIGH';
  status: AlertStatus;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  service_name?: string;
  organisation?: string;
  score?: number;
  events?: AlertEvent[];
}

export type DraftTemplate = 'general' | 'dpdp' | 'gdpr' | 'ccpa';
export type DraftStatus = 'draft' | 'sent' | 'responded';

export interface ComplaintDraft {
  id: number;
  user_id: number;
  consent_id: number;
  analysis_id?: number | null;
  template: DraftTemplate;
  subject: string;
  body: string;
  status: DraftStatus;
  created_at: string;
  updated_at: string;
  service_name?: string;
  organisation?: string;
}

export interface NotificationItem {
  id: number;
  user_id: number;
  message: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  type: 'consent_created' | 'evidence_submitted' | 'alert_raised' | 'draft_generated';
  title: string;
  description: string;
  risk?: RiskLevel | null;
  score?: number | null;
  timestamp: string;
  link?: string | null;
}

export interface AnalyticsData {
  summary: {
    total_applications: number;
    total_evidence: number;
    total_alerts: number;
    total_drafts: number;
  };
  consent_health: {
    percentage: number | null;
    status: string;
    low_count: number;
    total_evidence: number;
    formula: string;
  };
  risk_distribution: {
    LOW: number;
    MEDIUM: number;
    HIGH: number;
    INSUFFICIENT_EVIDENCE: number;
  };
  top_signals: {
    signal: string;
    raw_signal: string;
    count: number;
  }[];
  top_high_orgs: {
    organisation: string;
    count: number;
  }[];
  alerts_over_time: {
    date: string;
    total: number;
    high: number;
    medium: number;
  }[];
}

export interface EvalMetric {
  support: number;
  precision: number;
  recall: number;
  f1: number;
}

export interface EvalModeResult {
  total: number;
  accuracy: number;
  false_high_count: number;
  confusion_matrix: Record<string, Record<string, number>>;
  per_class: Record<string, EvalMetric>;
}

export interface EvalResultsResponse {
  status: string;
  generated_at?: string;
  sample_count?: number;
  metrics?: {
    rules_only?: EvalModeResult;
    hybrid?: EvalModeResult;
  };
  message?: string;
}

export type EvaluationResults = EvalResultsResponse;
