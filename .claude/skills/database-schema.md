# Database Schema

## leads
id, company_name, website, industry, location, employee_count,
pipeline_stage, lead_score, score_explanation, recommended_service,
icp_fit, research_summary, created_at, updated_at

## contacts
id, lead_id (FK), name, role, email, linkedin_url, is_primary

## emails
id, lead_id (FK), contact_id (FK), subject, body, sent_at, status

## replies
id, email_id (FK), raw_body, classification, received_at

## meetings
id, lead_id (FK), contact_id (FK), meeting_link, scheduled_at,
briefing, admin_notified, created_at

## followups
id, lead_id (FK), scheduled_for, status, email_id (FK → sent email)

## pipeline_events
id, lead_id (FK), from_stage, to_stage, reason, created_at
