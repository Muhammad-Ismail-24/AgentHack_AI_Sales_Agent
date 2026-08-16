/**
 * Every TypeScript interface in the app. One source of truth — never define a
 * shape inline in a component.
 *
 * Field names mirror backend/db/models.py and backend/api/schemas.py exactly.
 * Change one, change all three.
 */

// ── Enums ────────────────────────────────────────────────────────────

export const ACTIVE_STAGES = [
  'Discovered',
  'Potential',
  'Researching',
  'Qualified',
  'Contacted',
  'Interested',
  'Meeting Scheduled',
  'Converted',
] as const;

export const REJECTED_STAGES = [
  'Not Qualified',
  'Not Interested',
  'Do Not Contact',
] as const;

export const PIPELINE_STAGES = [...ACTIVE_STAGES, ...REJECTED_STAGES] as const;

export type ActiveStage = (typeof ACTIVE_STAGES)[number];
export type RejectedStage = (typeof REJECTED_STAGES)[number];
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

export type EmailStatus = 'draft' | 'sent' | 'failed' | 'replied';
export type MeetingStatus = 'link_sent' | 'confirmed' | 'completed' | 'cancelled';
export type FollowUpStatus = 'pending' | 'sent' | 'cancelled';

export type Classification =
  | 'Interested'
  | 'Pricing Objection'
  | 'Not Interested'
  | 'Meeting Requested'
  | 'Out of Office'
  | 'Unclear';

export type BadgeColor =
  | 'green'
  | 'lime'
  | 'yellow'
  | 'honey'
  | 'red'
  | 'gray'
  | 'terra';

// ── Entities ─────────────────────────────────────────────────────────

export interface Contact {
  id: string;
  lead_id: string;
  name: string | null;
  role: string | null;
  email: string | null;
  linkedin_url: string | null;
  is_primary: boolean;
}

export interface Lead {
  id: string;
  company_name: string;
  website: string | null;
  industry: string | null;
  location: string | null;
  employee_count: number | null;
  pipeline_stage: PipelineStage;
  lead_score: number | null;
  score_explanation: string | null;
  recommended_service: string | null;
  pitch_angle: string | null;
  icp_fit: boolean | null;
  research_summary: string | null;
  apollo_data: Record<string, unknown> | null;
  session_id: string | null;
  created_at: string;
  updated_at: string;
  contacts: Contact[];
}

export interface Email {
  id: string;
  lead_id: string;
  contact_id: string | null;
  subject: string | null;
  body: string | null;
  status: EmailStatus;
  sent_at: string | null;
  created_at: string;
}

export interface Reply {
  id: string;
  email_id: string;
  raw_body: string | null;
  classification: Classification | null;
  summary: string | null;
  next_action: string | null;
  received_at: string;
}

export interface MeetingBriefing {
  customer_problem?: string;
  recommended_service?: string;
  key_points?: string[];
  watch_out_for?: string[];
  [key: string]: unknown;
}

export interface Meeting {
  id: string;
  lead_id: string;
  contact_id: string | null;
  meeting_link: string | null;
  scheduled_at: string | null;
  briefing: MeetingBriefing | null;
  admin_notified: boolean;
  status: MeetingStatus;
  created_at: string;
}

export interface FollowUp {
  id: string;
  lead_id: string;
  original_email_id: string;
  followup_email_id: string | null;
  scheduled_for: string | null;
  status: FollowUpStatus;
  created_at: string;
}

export interface PipelineEvent {
  id: string;
  lead_id: string;
  from_stage: PipelineStage | null;
  to_stage: PipelineStage | null;
  reason: string | null;
  created_at: string;
}

// ── Composites ───────────────────────────────────────────────────────

export interface LeadDetail {
  lead: Lead;
  contacts: Contact[];
  emails: Email[];
  replies: Reply[];
  meetings: Meeting[];
  events: PipelineEvent[];
}

/** A reply with its lead and contact already resolved — GET /inbox. */
export interface InboxItem {
  reply: Reply;
  email: Email;
  lead_id: string;
  company_name: string;
  contact_name: string | null;
}

// ── Onboarding / pipeline ────────────────────────────────────────────

export interface CompanyUploadResult {
  session_id: string;
  company_name: string;
  status: string;
  chars_ingested: number | null;
  message: string | null;
}

export interface ICPInput {
  session_id: string;
  location: string;
  industry: string;
  company_size: string;
  special_focus?: string;
}

export interface ICPResult {
  session_id: string;
  icp: Record<string, unknown>;
}

export interface PipelineStatus {
  session_id: string;
  stage: string;
  is_running: boolean;
  raw_leads_count: number;
  filtered_count: number;
  qualified_count: number;
  outreach_count: number;
  total_leads: number;
  stage_counts: Record<string, number>;
  error: string | null;
}

export interface MessageResult {
  success: boolean;
  message: string | null;
}
