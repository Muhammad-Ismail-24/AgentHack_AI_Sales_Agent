/**
 * Every backend call in the app. Components import from here — never call
 * axios or fetch directly from a component.
 *
 * In dev, requests go to /api and Vite proxies them to the backend (see
 * vite.config.ts). Set VITE_API_URL to point at a backend directly instead.
 */

import axios, { AxiosError } from 'axios';

import type {
  CompanyUploadResult,
  Email,
  ICPInput,
  ICPResult,
  InboxItem,
  Lead,
  LeadDetail,
  Meeting,
  MessageResult,
  PipelineStage,
  PipelineStatus,
} from './types';

const baseURL = import.meta.env.VITE_API_URL
  ? String(import.meta.env.VITE_API_URL).replace(/\/$/, '')
  : '/api';

const client = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

/** Turn an axios failure into a message worth showing in a toast. */
export function describeError(error: unknown): string {
  const axiosError = error as AxiosError<{ detail?: string }>;

  if (axiosError?.response) {
    const detail = axiosError.response.data?.detail;
    if (typeof detail === 'string') return detail;
    return `Request failed (${axiosError.response.status}).`;
  }
  if (axiosError?.code === 'ECONNABORTED') {
    return 'The request timed out. Is the backend still running?';
  }
  if (axiosError?.request) {
    return 'Could not reach the backend. Check that it is running on port 8000.';
  }
  return error instanceof Error ? error.message : 'Something went wrong.';
}

// ── Company / onboarding ─────────────────────────────────────────────

export async function uploadCompanyPDF(file: File): Promise<CompanyUploadResult> {
  const form = new FormData();
  form.append('file', file);

  const { data } = await client.post<CompanyUploadResult>('/company/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000, // a large PDF plus RAG ingest takes a while
  });
  return data;
}

export async function submitCompanyText(
  text: string,
  companyName?: string,
): Promise<CompanyUploadResult> {
  const { data } = await client.post<CompanyUploadResult>(
    '/company/text',
    { text, company_name: companyName ?? null },
    { timeout: 120_000 },
  );
  return data;
}

// ── ICP ──────────────────────────────────────────────────────────────

export async function defineICP(params: ICPInput): Promise<ICPResult> {
  const { data } = await client.post<ICPResult>('/icp/define', params, {
    timeout: 60_000,
  });
  return data;
}

export async function getICP(sessionId: string): Promise<ICPResult> {
  const { data } = await client.get<ICPResult>(`/icp/${sessionId}`);
  return data;
}

// ── Pipeline ─────────────────────────────────────────────────────────

export async function startPipeline(
  sessionId: string,
): Promise<{ session_id: string; status: string }> {
  const { data } = await client.post('/pipeline/start', { session_id: sessionId });
  return data;
}

export async function getPipelineStatus(sessionId: string): Promise<PipelineStatus> {
  const { data } = await client.get<PipelineStatus>(`/pipeline/status/${sessionId}`);
  return data;
}

export async function stopPipeline(
  sessionId: string,
): Promise<{ session_id: string; status: string }> {
  const { data } = await client.post(`/pipeline/stop/${sessionId}`);
  return data;
}

// ── Leads ────────────────────────────────────────────────────────────

export async function getLeads(sessionId?: string): Promise<Lead[]> {
  const { data } = await client.get<Lead[]>('/leads', {
    params: sessionId ? { session_id: sessionId } : undefined,
  });
  return data;
}

export async function getLeadDetail(leadId: string): Promise<LeadDetail> {
  const { data } = await client.get<LeadDetail>(`/leads/${leadId}`);
  return data;
}

export async function updateLeadStage(
  leadId: string,
  stage: PipelineStage,
): Promise<Lead> {
  const { data } = await client.patch<Lead>(`/leads/${leadId}`, {
    pipeline_stage: stage,
  });
  return data;
}

export async function deleteLead(leadId: string): Promise<MessageResult> {
  const { data } = await client.delete<MessageResult>(`/leads/${leadId}`);
  return data;
}

// ── Emails ───────────────────────────────────────────────────────────

export async function getEmails(): Promise<Email[]> {
  const { data } = await client.get<Email[]>('/emails');
  return data;
}

export async function sendEmail(
  leadId: string,
  contactId: string | null,
  subject: string,
  body: string,
): Promise<MessageResult> {
  const { data } = await client.post<MessageResult>(
    '/emails/send',
    { lead_id: leadId, contact_id: contactId, subject, body },
    { timeout: 60_000 },
  );
  return data;
}

// ── Inbox ────────────────────────────────────────────────────────────

export async function getInbox(): Promise<InboxItem[]> {
  const { data } = await client.get<InboxItem[]>('/inbox');
  return data;
}

// ── Meetings ─────────────────────────────────────────────────────────

export async function getMeetings(): Promise<Meeting[]> {
  const { data } = await client.get<Meeting[]>('/meetings');
  return data;
}

export async function createMeeting(
  leadId: string,
  contactId?: string | null,
): Promise<{ meeting_link: string; meeting_id?: string }> {
  const { data } = await client.post(
    '/meetings/create',
    { lead_id: leadId, contact_id: contactId ?? null },
    { timeout: 60_000 },
  );
  return data;
}

// ── Meta ─────────────────────────────────────────────────────────────

export async function getHealth(): Promise<{
  status: string;
  database: string;
  version: string;
}> {
  const { data } = await client.get('/health');
  return data;
}
