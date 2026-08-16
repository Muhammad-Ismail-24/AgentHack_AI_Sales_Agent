"""LangGraph master graph — wires the agent nodes into the sales pipeline.

Flow: rag -> icp_agent -> discovery -> filter -> research -> combined_processing

combined_processing does in one LLM call per lead what qualification,
service_matching, decision_maker and email_writer used to do in four. Those
four modules still exist under agents/ but nothing imports them any more.
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents import (
    combined_processing_agent,
    discovery_agent,
    filter_agent,
    icp_agent,
    rag_agent,
    research_agent,
)
from utils.logger import logger


class PipelineState(TypedDict, total=False):
    """Shared state threaded through every node in the pipeline.

    Set by:
      session_id           - caller (run_pipeline)
      raw_input             - caller (run_pipeline)
      input_type             - caller (run_pipeline)
      icp_raw                - caller (run_pipeline)
      company_collection    - rag_agent
      company_name           - rag_agent
      icp                     - icp_agent
      raw_leads               - discovery_agent
      filtered_leads          - filter_agent
      researched_leads        - research_agent
      qualified_leads          - combined_processing_agent
      outreach_queue            - combined_processing_agent
    """

    session_id: str
    raw_input: str
    input_type: str
    icp_raw: dict
    company_collection: str
    company_name: str
    icp: dict
    raw_leads: list[dict]
    filtered_leads: list[dict]
    researched_leads: list[dict]
    qualified_leads: list[dict]
    outreach_queue: list[dict]


def build_graph():
    """Build and compile the LangGraph StateGraph for the sales pipeline."""
    graph = StateGraph(PipelineState)

    graph.add_node("rag", rag_agent.run)
    # Named "icp_agent", not "icp" — PipelineState already has an `icp` field,
    # and LangGraph rejects a node name that collides with a state key.
    graph.add_node("icp_agent", icp_agent.run)
    graph.add_node("discovery", discovery_agent.run)
    graph.add_node("filter", filter_agent.run)
    graph.add_node("research", research_agent.run)
    graph.add_node("combined_processing", combined_processing_agent.run)

    graph.add_edge(START, "rag")
    graph.add_edge("rag", "icp_agent")
    graph.add_edge("icp_agent", "discovery")
    graph.add_edge("discovery", "filter")
    graph.add_edge("filter", "research")
    graph.add_edge("research", "combined_processing")
    graph.add_edge("combined_processing", END)

    return graph.compile()


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def build_icp(session_id: str, raw_icp: dict) -> dict | None:
    """Structure the ICP form answers on their own, without running the graph.

    POST /icp/define calls this through orchestrator_bridge so the ICP screen
    can show a real structured profile. Until it existed the bridge's getattr
    found nothing and every session fell back to echoing the form fields back
    with `structured: False`.

    Returns None when the LLM gives us nothing usable — the bridge owns the
    fallback, so there is no second copy of it here.
    """
    state = await icp_agent.run({"session_id": session_id, "icp_raw": raw_icp})
    icp = state.get("icp")

    if not isinstance(icp, dict) or not icp:
        logger.warning(
            f"orchestrator: could not structure ICP for session_id='{session_id}'"
        )
        return None

    return {**icp, "structured": True}


async def run_pipeline(
    session_id: str,
    raw_input: str,
    input_type: str,
    icp_raw: dict,
) -> dict:
    """Run the full sales-intelligence pipeline end-to-end.

    Builds the initial state, invokes the compiled graph, and returns the
    final state (including outreach_queue, ready for comms/ to consume).
    """
    initial_state: PipelineState = {
        "session_id": session_id,
        "raw_input": raw_input,
        "input_type": input_type,
        "icp_raw": icp_raw,
        "icp": {},
        "raw_leads": [],
        "filtered_leads": [],
        "researched_leads": [],
        "qualified_leads": [],
        "outreach_queue": [],
    }

    logger.info(f"orchestrator: starting pipeline run for session_id='{session_id}'")
    compiled = get_compiled_graph()
    final_state = await compiled.ainvoke(initial_state)
    logger.info(f"orchestrator: pipeline run complete for session_id='{session_id}'")
    return final_state
