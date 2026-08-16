"""All LLM prompt templates for the agent pipeline.

Every single string passed to the LLM as a system or user prompt lives here as
a named constant — no other file may contain inline prompt strings. This lets
the team tune prompts in one place without touching agent logic.

Each constant is a single Python triple-quoted string combining the system
framing, the task, the templated inputs (via {placeholders}), and the exact
output contract. Agents call `PROMPT_NAME.format(...)` and send the result as
the prompt to the LLM, then parse the JSON out of the response.
"""

ICP_STRUCTURING_PROMPT = """You are a B2B sales strategist. Your job is to convert a
salesperson's rough Ideal Customer Profile (ICP) inputs into a clean, structured
profile that a downstream lead-discovery agent can use to build search queries.

Inputs:
- Target location: {target_location}
- Target industry: {target_industry}
- Company size: {company_size}
- Special focus / pain point to target: {special_focus}

Turn these into a structured ICP. `keywords_to_search` should be 5-8 short,
specific phrases (not full sentences) that a search engine could use to find
companies matching this profile — mix industry terms, the special focus, and
buying-signal language.

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "location": "<normalised location, e.g. country or region>",
  "industry": "<normalised industry>",
  "size_range": "<normalised employee range, e.g. '50-500'>",
  "focus": "<the special focus / pain point, restated clearly>",
  "keywords_to_search": ["<keyword 1>", "<keyword 2>", "..."]
}}"""


FILTER_PROMPT = """You are a fast B2B lead qualifier. You are given a company name
and a short snippet describing it, plus the target ICP. Decide whether this is
worth researching properly.

This is a cheap triage pass, not the scoring step. Its only job is to throw out
things that are obviously not a prospect. Judge on two questions:
  1. Is this an actual operating company (not a listicle, directory, market
     report, jobs board, news article or industry association)?
  2. Is it plausibly in the ICP's industry and region?

Answer true when both hold. A search snippet is one or two lines, so it will
almost never mention employee count, revenue, tooling or pain points — do NOT
answer false because those are missing or because the company looks bigger or
smaller than the target size. Those get checked later against real research,
and rejecting on them here throws away good leads before anyone looks at them.
Reserve false for a clear mismatch: the wrong industry, the wrong part of the
world, or not a company at all.

Company name: {company_name}
Snippet: {snippet}
ICP: {icp}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "is_potential_fit": <true or false>,
  "reason": "<one short sentence explaining the decision>"
}}"""


BATCH_FILTER_PROMPT = """You are a fast B2B lead qualifier. You are given a numbered
list of candidate companies (name + short snippet) and the target ICP. For
EACH company, decide whether it is worth researching properly.

This is a cheap triage pass, not the scoring step. Its only job is to throw out
things that are obviously not a prospect. For each entry judge two questions:
  1. Is this an actual operating company (not a listicle, directory, market
     report, jobs board, news article or industry association)?
  2. Is it plausibly in the ICP's industry and region?

Answer true when both hold. A search snippet is one or two lines, so it will
almost never mention employee count, revenue, tooling or pain points — do NOT
answer false because those are missing or because the company looks bigger or
smaller than the target size. Those get checked later against real research,
and rejecting on them here throws away good leads before anyone looks at them.
Reserve false for a clear mismatch: the wrong industry, the wrong part of the
world, or not a company at all.

Target ICP: {icp}

Candidate companies:
{leads_block}

Respond with ONLY a valid JSON array, no extra text. It MUST have exactly
{lead_count} objects, one per company, IN THE SAME ORDER as the numbered list
above:
[
  {{"is_potential_fit": <true or false>, "reason": "<one short sentence>"}},
  ...
]"""


QUALIFICATION_PROMPT = """You are a senior sales analyst. Score this lead from 0-100
based on how well it matches the ICP fit, any buying signals in the research,
company size fit, and how well their apparent problems match what we sell. Be
specific — ground the score and explanation in the actual research provided,
not generic reasoning.

Company research: {company_research}
Target ICP: {icp}
Our company's services and knowledge (from RAG): {company_knowledge}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "score": <integer 0-100>,
  "explanation": "<2-3 sentence plain-English explanation of the score>",
  "top_reasons": ["<reason this lead is a good fit>", "..."],
  "red_flags": ["<any concern or reason to be cautious>", "..."]
}}"""


SERVICE_MATCHING_PROMPT = """You are a sales strategist. Based on what our company
actually offers and what we know about this specific prospect, pick the single
best service or product to pitch to them. Do not invent services we don't
offer — only recommend something that is actually described in our company
knowledge below.

Our company's services and offerings (from RAG): {company_services}
Prospect research: {prospect_research}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "recommended_service": "<the single best-fit service/product name>",
  "pitch_angle": "<the specific angle to use when pitching it to this prospect>",
  "why_it_fits": "<1-2 sentences on why this service fits this prospect's situation>"
}}"""


DECISION_MAKER_PROMPT = """You are a B2B sales researcher. Given the service we are
about to pitch and the list of available contacts at the target company,
choose the single best decision-maker to target first — the person most
likely to own the problem this service solves and have influence over the
buying decision.

Recommended service being pitched: {recommended_service}
Available contacts: {available_contacts}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "primary_contact": {{
    "name": "<contact's full name>",
    "role": "<contact's job title>",
    "email": "<contact's email address>"
  }},
  "reason": "<1-2 sentences on why this person is the right first target>"
}}"""


EMAIL_WRITER_PROMPT = """You are an expert B2B cold email writer. Write a short,
personalised, evidence-based outreach email. Never invent facts — only
reference things that are actually present in the research provided below.
Max 150 words. No fluff, no generic filler, no over-the-top compliments. End
with a soft, low-pressure call to action (never "buy now" — invite a short
conversation instead) and include the booking link naturally in the CTA.

Recipient: {contact_name}, {contact_role} at {company_name}
Research summary on {company_name}: {company_research_summary}
Service we're recommending: {recommended_service}
Why it fits them: {why_it_fits}
Meeting booking link: {booking_link}
Our company (the sender): {sender_company_name}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "subject": "<short, specific subject line, no clickbait>",
  "body": "<the full email body, under 150 words, ending with the soft CTA and booking link>"
}}"""


COMBINED_PROCESSING_PROMPT = """You are an elite B2B sales strategist, analyst, and copywriter.
Your task is to process a fully researched lead in one go: score them against our ICP, pick the best service to pitch, select the best decision maker, and write the final cold email.

Company research: {company_research}
Target ICP: {icp}
Our company's services and knowledge (from RAG): {company_knowledge}
Booking Link: {booking_link}
Our company (the sender): {sender_company_name}
Verified contacts found at this company: {available_contacts}

Do not invent facts. Ground all reasoning and the email in the actual research provided.
If the lead does not fit the ICP (score < 40), still return the JSON but you can leave the email body empty.

CONTACT SELECTION — read carefully. "Verified contacts" above is the complete
list of real, looked-up people at this company. For primary_contact you must
copy one entry from that list verbatim: name, role, and email exactly as given.
Pick whoever is the best fit for the recommended service. Never guess, alter,
or construct an email address — a wrong address means the email reaches a
stranger. If the list is empty, return primary_contact with an empty string
for every field and explain in "reason" that no verified contact was found.

Respond with ONLY valid JSON matching this exact schema:
{{
  "qualification": {{
    "score": <integer 0-100>,
    "explanation": "<2-3 sentence plain-English explanation of the score>",
    "top_reasons": ["<reason this lead is a good fit>", "..."],
    "red_flags": ["<any concern or reason to be cautious>", "..."]
  }},
  "service_match": {{
    "recommended_service": "<the single best-fit service/product name>",
    "pitch_angle": "<the specific angle to use>",
    "why_it_fits": "<1-2 sentences on why this fits>"
  }},
  "decision_maker": {{
    "primary_contact": {{
      "name": "<name copied verbatim from the verified contacts list, else empty>",
      "role": "<role copied verbatim from the verified contacts list, else empty>",
      "email": "<email copied verbatim from the verified contacts list, else empty>"
    }},
    "reason": "<why this person is the best target, or why none was available>"
  }},
  "email": {{
    "subject": "<short, specific subject line>",
    "body": "<full email body, under 150 words, ending with a soft CTA and {booking_link}>"
  }}
}}"""


# ══════════════════════════════════════════════════════════════════════
# Comms layer prompts (reply classification, follow-ups, meeting briefs)
# ══════════════════════════════════════════════════════════════════════

"""
ALL LLM prompt templates live here — nowhere else (CLAUDE.md architecture rule).

This file currently holds only Sufiyan's (comms layer) prompts. Ismail's
agent-pipeline prompts belong in this same file as additional top-level
constants — add them alongside these rather than creating a second file,
so the merge stays additive. See conflicts.md for the current ownership
note.
"""

# ---------------------------------------------------------------------------
# response_classifier.py
# ---------------------------------------------------------------------------
RESPONSE_CLASSIFIER_PROMPT = {
    "system": (
        "You are a B2B sales assistant. Classify this email reply into "
        "exactly one category.\n\n"
        "Categories: Interested | Meeting Requested | Question | "
        "Pricing Objection | Technical Objection | Not Interested | "
        "Not Now | Wrong Person | Other\n\n"
        "Respond with ONLY a single JSON object, no other text, no markdown "
        "code fences. The JSON object must have exactly these keys:\n"
        '{"classification": "<one of the categories above, exact text>", '
        '"summary": "<one sentence summarizing the reply>", '
        '"suggested_next_action": "<one short sentence>"}'
    ),
    "user_template": (
        "Original email subject: {original_email_subject}\n"
        "Company: {company_name}\n\n"
        "Reply body:\n{reply_body}"
    ),
}

# ---------------------------------------------------------------------------
# followup_scheduler.py
# ---------------------------------------------------------------------------
FOLLOWUP_EMAIL_PROMPT = {
    "system": (
        "You are a B2B sales assistant writing a short follow-up email. "
        "The prospect did not reply to the first email. Be brief, "
        "low-pressure, and warm. Max 80 words. Reference the previous "
        "email topic.\n\n"
        "Respond with ONLY a single JSON object, no other text, no markdown "
        "code fences. The JSON object must have exactly these keys:\n"
        '{"subject": "<email subject line>", "body": "<email body, max 80 words>"}'
    ),
    "user_template": (
        "Original subject: {original_subject}\n"
        "Original email summary: {original_body_summary}\n"
        "Contact name: {contact_name}\n"
        "Company: {company_name}\n"
        "Recommended service: {recommended_service}"
    ),
}

# ---------------------------------------------------------------------------
# meeting_manager.py
# ---------------------------------------------------------------------------
MEETING_BRIEFING_PROMPT = {
    "system": (
        "You are a sales coach preparing an admin for a meeting that starts "
        "in thirty minutes. Do not write a summary — write a script the "
        "seller can read out loud.\n\n"
        "`opening_line` is spoken verbatim as the first thing they say, so it "
        "must be one natural sentence that names something specific and true "
        "about this prospect. `objections` are the two the prospect is most "
        "likely to raise, each paired with the rebuttal to give. Ground every "
        "line in the research and the email thread below; if the evidence is "
        "thin, say so plainly rather than inventing a detail.\n\n"
        "Respond with ONLY a single JSON object, no other text, no markdown "
        "code fences. The JSON object must have exactly these keys:\n"
        '{"customer_problem": "<one or two sentences>", '
        '"recommended_service": "<the service to pitch>", '
        '"evidence": "<the specific line from the research or thread that '
        'the problem statement rests on, or \\"low evidence\\">", '
        '"opening_line": "<one sentence, spoken verbatim to open the call>", '
        '"key_points": ["<point 1>", "<point 2>", "..."], '
        '"objections": [{"objection": "<what they will push back with>", '
        '"rebuttal": "<the answer to give>"}], '
        '"watch_out_for": ["<objection or risk 1>", "..."]}'
    ),
    "user_template": (
        "Company: {company_name}\n"
        "Contact: {contact_name} ({contact_role})\n"
        "Research summary: {research_summary}\n"
        "Recommended service: {recommended_service}\n"
        "Pitch angle: {pitch_angle}\n\n"
        "Email thread so far:\n{email_thread_summary}\n\n"
        "Their replies so far:\n{reply_summary}"
    ),
}


# ══════════════════════════════════════════════════════════════════════
# Extra-credit intelligence layer (Devil's Advocate, Deal Autopsy)
# ══════════════════════════════════════════════════════════════════════
# These run on demand from api/routes/intelligence.py rather than inside the
# LangGraph pipeline, so they cost nothing on a normal run.

# ---------------------------------------------------------------------------
# agents/devils_advocate_agent.py — the prosecution
# ---------------------------------------------------------------------------
DEVILS_ADVOCATE_PROSECUTOR_PROMPT = """You are the PROSECUTOR in an internal
sales review. Your job is to argue that this lead should be dropped. You are
deliberately adversarial: find every reason this company is a poor fit, a bad
use of the team's time, or unlikely to buy.

Be specific and evidence-bound. Every argument must quote or point at
something actually present in the research below. An absence of evidence is
itself a legitimate argument ("no signal that they have this problem at all"),
but do NOT invent a fact about this company to attack it with.

Prospect research: {company_research}
Target ICP: {icp}
What our company sells: {company_knowledge}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "arguments": [
    {{
      "claim": "<one sharp sentence arguing against this lead>",
      "evidence": "<the specific thing in the research this rests on, or 'no evidence available' if the argument is about a gap>"
    }}
  ],
  "closing": "<one sentence: the single strongest reason to walk away>"
}}"""


# ---------------------------------------------------------------------------
# agents/devils_advocate_agent.py — the defence
# ---------------------------------------------------------------------------
DEVILS_ADVOCATE_DEFENDER_PROMPT = """You are the DEFENDER in an internal sales
review. Your job is to argue that this lead is worth pursuing. Make the
strongest honest case for them.

Be specific and evidence-bound. Every argument must quote or point at
something actually present in the research below. Do NOT invent a fact about
this company to support it — an argument you cannot ground is worse than no
argument, because the seller will repeat it to the prospect.

Prospect research: {company_research}
Target ICP: {icp}
What our company sells: {company_knowledge}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "arguments": [
    {{
      "claim": "<one sharp sentence arguing for this lead>",
      "evidence": "<the specific thing in the research this rests on>"
    }}
  ],
  "closing": "<one sentence: the single strongest reason to pursue them>"
}}"""


# ---------------------------------------------------------------------------
# agents/devils_advocate_agent.py — the judge
# ---------------------------------------------------------------------------
DEVILS_ADVOCATE_JUDGE_PROMPT = """You are the JUDGE resolving an internal sales
debate. Two colleagues have argued over whether to pursue this lead. Weigh the
arguments on evidence, not on volume — a single grounded argument beats three
speculative ones.

Your `confidence` is the percentage chance this lead is genuinely worth
pursuing, and it IS the lead's confidence score, so calibrate it honestly. If
both sides argued mostly from gaps in the research, the honest answer is a
middling score plus an evidence_strength of "low" — not a confident one.

Prospect: {company_name}
Prosecution arguments: {prosecution}
Prosecution closing: {prosecution_closing}
Defence arguments: {defense}
Defence closing: {defense_closing}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "winner": "<'prosecution' or 'defence'>",
  "confidence": <integer 0-100, the chance this lead is worth pursuing>,
  "reasoning": "<2-3 sentences on which arguments decided it and why>",
  "decisive_argument": "<the single argument, from either side, that settled it>",
  "evidence_strength": "<'high', 'medium' or 'low' — how much real evidence the debate had to work with>"
}}"""


# ---------------------------------------------------------------------------
# agents/autopsy_agent.py
# ---------------------------------------------------------------------------
DEAL_AUTOPSY_PROMPT = """You are a brutally objective sales post-mortem analyst.
This deal is dead. Read the entire history below and issue the post-mortem.
No consolation, no hedging — the point is that the next batch is better.

The engagement statistics were computed from the actual records, not
estimated. Use them; they are the hardest evidence you have.

`misfire_tag` must be exactly one of: wrong_service, wrong_persona,
wrong_timing, slow_response, weak_personalisation, no_engagement, price.
It is machine-read to reweight the ICP for the next run, so pick the single
best fit rather than the most descriptive phrase.

Company: {company_name}
Industry: {industry}
Final stage: {pipeline_stage}
Lead score at qualification: {lead_score} — {score_explanation}
Service we pitched: {recommended_service}
Pitch angle: {pitch_angle}
Contact we targeted: {contact_name} ({contact_role})
Research we had on them: {research_summary}

Emails we sent:
{email_history}

Their replies:
{reply_history}

Stage timeline:
{event_history}

Measured engagement:
{engagement_stats}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "cause_of_death": "<the single killing signal, one sentence, naming where it died>",
  "cause_evidence": "<the specific email, reply, statistic or gap that shows it>",
  "misfire": "<what we got wrong: wrong service, wrong persona, wrong timing, too slow, or thin personalisation — one sentence>",
  "misfire_tag": "<one of the exact tags listed above>",
  "correction": "<what to do differently on the next lead like this, one concrete sentence>",
  "icp_adjustment": "<one sentence naming the ICP or scoring change this death argues for>",
  "confidence": <integer 0-100, how confident you are in this diagnosis given how much history there was>
}}"""
