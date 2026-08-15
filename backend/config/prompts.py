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
and a short snippet describing it, plus the target ICP. Decide quickly whether
this company could plausibly be a fit for the ICP.

Be aggressive at filtering — say NO quickly. This is a cheap first pass before
expensive research, so only keep companies that are a clear, plausible fit.
When the snippet gives too little information to judge, prefer NO over
guessing.

Company name: {company_name}
Snippet: {snippet}
ICP: {icp}

Respond with ONLY valid JSON matching this exact schema, no extra text:
{{
  "is_potential_fit": <true or false>,
  "reason": "<one short sentence explaining the decision>"
}}"""


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
