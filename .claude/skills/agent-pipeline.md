# Agent Pipeline — How it works

## LangGraph flow (orchestrator.py)
RAG Agent → ICP Agent → Discovery Agent → Filter Agent →
Research Agent → Qualification Agent → Service Matching Agent →
Decision Maker Agent → Email Writer Agent

## State object passed between nodes
{
  "company_knowledge": {},   # from RAG
  "icp": {},                 # from ICP agent
  "raw_leads": [],           # from Discovery
  "filtered_leads": [],      # after Filter
  "researched_leads": [],    # after Research
  "qualified_leads": [],     # after Qualification (with score + explanation)
  "outreach_queue": []       # after Email Writer
}

## Important: agents are async
All agent functions are async def. Use await for all LLM and tool calls.
