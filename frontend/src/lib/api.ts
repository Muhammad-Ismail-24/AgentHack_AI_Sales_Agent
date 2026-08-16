/**
 * Every backend call in the app. Components import from here — never call
 * axios or fetch directly from a component.
 *
 * In dev, requests go to /api and Vite proxies them to the backend (see
 * vite.config.ts). Set VITE_API_URL to point at a backend directly instead.
 */

import axios, { AxiosError } from 'axios';

import type {
  Autopsy,
  AutopsyInsights,
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
  Verdict,
  Whisper,
  WhisperAudio,
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

/**
 * Resolve to null on a 404 instead of throwing.
 *
 * The intelligence endpoints 404 when a debate, autopsy or script has simply
 * never been generated for that record — a normal empty state, not a failure.
 * Any other error still propagates so the caller can toast it.
 */
async function nullOn404<T>(request: Promise<{ data: T }>): Promise<T | null> {
  try {
    return (await request).data;
  } catch (error) {
    if ((error as AxiosError)?.response?.status === 404) return null;
    throw error;
  }
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

// ── Intelligence: Devil's Advocate ───────────────────────────────────
// A debate costs three LLM calls, so it only ever runs from an explicit
// click — hence a POST to run it and a separate GET to read the last one.

export async function runDevilsAdvocate(leadId: string): Promise<Verdict> {
  const { data } = await client.post<Verdict>(
    `/intelligence/leads/${leadId}/devils-advocate`,
    undefined,
    { timeout: 120_000 },
  );
  return data;
}

export async function getDevilsAdvocate(leadId: string): Promise<Verdict | null> {
  return nullOn404(
    client.get<Verdict>(`/intelligence/leads/${leadId}/devils-advocate`),
  );
}

// ── Intelligence: Deal Autopsy ───────────────────────────────────────

export async function runAutopsy(leadId: string): Promise<Autopsy> {
  const { data } = await client.post<Autopsy>(
    `/intelligence/leads/${leadId}/autopsy`,
    undefined,
    { timeout: 120_000 },
  );
  return data;
}

export async function getAutopsy(leadId: string): Promise<Autopsy | null> {
  return nullOn404(client.get<Autopsy>(`/intelligence/leads/${leadId}/autopsy`));
}

export async function getAutopsyInsights(): Promise<AutopsyInsights> {
  const { data } = await client.get<AutopsyInsights>(
    '/intelligence/autopsies/insights',
  );
  return data;
}

// ── Intelligence: Executive Whisperer ────────────────────────────────

export async function buildWhisper(meetingId: string): Promise<Whisper> {
  const { data } = await client.post<Whisper>(
    `/intelligence/meetings/${meetingId}/whisper`,
    undefined,
    { timeout: 120_000 },
  );
  return data;
}

export async function getWhisper(meetingId: string): Promise<Whisper | null> {
  return nullOn404(
    client.get<Whisper>(`/intelligence/meetings/${meetingId}/whisper`),
  );
}

export async function buildWhisperAudio(meetingId: string): Promise<WhisperAudio> {
  const { data } = await client.post<WhisperAudio>(
    `/intelligence/meetings/${meetingId}/whisper/audio`,
    undefined,
    { timeout: 180_000 },
  );
  return data;
}

/**
 * Turn a backend-relative media path (`/audio/x.mp3`) into one the browser can
 * load. In dev that means going back through the `/api` proxy, which strips
 * the prefix again on the way to the backend.
 */
export function resolveMediaUrl(path: string): string {
  return `${baseURL}${path}`;
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
