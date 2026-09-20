import os
import certifi
from dotenv import load_dotenv

load_dotenv()
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import Any, TypedDict, Annotated
import operator
import uuid
import asyncio
import json
import psycopg
from psycopg.rows import dict_row
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from mistralai.client import Mistral


from mcp_client import (
    tavily_mcp_search,
    aviation_mcp_call,
    extract_destination,
    forecast_mcp_search,
    weather_mcp_search,
)
from tools.flight_tool import search_flights
from tools.tavily_tool import tavily_search
from tools.weather_tool import get_weather_bundle


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. "
            "Please add your Render PostgreSQL External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url


MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEMO_MODE = not bool(MISTRAL_API_KEY or GROQ_API_KEY)

# =========================
# LLM - live Groq when configured, deterministic demo fallback otherwise
# =========================
class _DemoLLM:
    def invoke(self, messages):
        if isinstance(messages, list):
            text = "\n".join(str(getattr(item, "content", item)) for item in messages)
        else:
            text = str(messages)

        lowered = text.lower()

        if '"allowed"' in text and "guardrail" in lowered:
            unsafe_terms = (
                "bomb", "weapon", "malware", "ransomware",
                "steal password", "credit card theft",
            )
            blocked = any(term in lowered for term in unsafe_terms)
            return AIMessage(
                content=json.dumps({
                    "allowed": not blocked,
                    "reason": (
                        "This demo blocks harmful or clearly unsafe requests."
                        if blocked else ""
                    ),
                })
            )

        if '"selected_agents"' in text and "trip_constraints" in lowered:
            return AIMessage(
                content=json.dumps({
                    "selected_agents": [
                        "flight_agent",
                        "hotel_agent",
                        "weather_agent",
                        "budget_agent",
                        "itinerary_agent",
                    ],
                    "trip_constraints": {
                        "destination": "",
                        "origin": "",
                        "duration": "",
                        "budget": "",
                        "travel_style": "",
                        "special_preferences": [],
                    },
                    "reasoning": (
                        "Demo mode selected the full specialist workflow so the "
                        "supervisor, guardrail, and HITL path remain observable."
                    ),
                })
            )

        if "analyze whether this trip is realistic" in lowered:
            return AIMessage(content=(
                "Demo budget assessment: separate airfare, accommodation, local "
                "transport, food, activities, insurance, and a 10-15% contingency. "
                "Live prices are not configured, so verify current rates before booking."
            ))

        if "create a complete travel itinerary" in lowered:
            return AIMessage(content=(
                "### Draft itinerary\n"
                "Day 1: Arrive, check in, and keep the schedule light.\n"
                "Day 2: Explore major landmarks and a central neighborhood.\n"
                "Day 3: Add a local experience, flexible activity, and evening review.\n"
                "Day 4: Reserve time for shopping, food, or a day trip based on the request.\n"
                "Day 5: Check out and depart with extra airport-transfer buffer.\n\n"
                "This is a deployment-safe demo draft. Configure provider keys for "
                "live flight, hotel-search, weather, and richer LLM-generated planning."
            ))

        if "generate the final travel response" in lowered:
            return AIMessage(content=(
                "## Trip Summary\nA practical travel plan has been prepared and reviewed.\n\n"
                "## Flight Information\nLive flight data is optional in demo mode; verify schedules and fares before booking.\n\n"
                "## Hotel Suggestions\nChoose a well-reviewed property near your main activity area and public transport.\n\n"
                "## Weather Information\nCheck the destination forecast shortly before departure and pack accordingly.\n\n"
                "## Day-by-Day Itinerary\nFollow the approved draft while keeping one flexible block each day.\n\n"
                "## Estimated Budget\nBudget for transport, stay, food, activities, insurance, and a contingency buffer.\n\n"
                "## Final Recommendations\nConfirm entry rules, reservations, travel insurance, and current local conditions."
            ))

        return AIMessage(content=(
            "Demo mode is active. Configure GROQ_API_KEY to enable live model generation."
        ))

class _MistralLLM:
    """Minimal LangChain-compatible adapter around the official Mistral SDK."""

    def __init__(self, api_key: str, model: str = "mistral-small-latest"):
        self.client = Mistral(api_key=api_key)
        self.model = model

    @staticmethod
    def _role(message: Any) -> str:
        if isinstance(message, SystemMessage):
            return "system"
        if isinstance(message, HumanMessage):
            return "user"
        return "assistant"

    def invoke(self, messages):
        if not isinstance(messages, list):
            messages = [HumanMessage(content=str(messages))]

        payload = [
            {
                "role": self._role(message),
                "content": str(getattr(message, "content", message)),
            }
            for message in messages
        ]

        response = self.client.chat.complete(
            model=self.model,
            messages=payload,
        )
        content = response.choices[0].message.content
        if isinstance(content, list):
            content = "".join(
                str(getattr(chunk, "text", chunk))
                for chunk in content
            )
        return AIMessage(content=str(content or ""))


llm = (
    _MistralLLM(MISTRAL_API_KEY)
    if MISTRAL_API_KEY
    else (
        ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
        if GROQ_API_KEY
        else _DemoLLM()
    )
)

# =========================
# State - original fields kept, new control fields added
# =========================
class TravelState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str

    # Supervisor + guardrail state
    guardrail_allowed: bool
    guardrail_reason: str
    selected_agents: list[str]
    trip_constraints: dict[str, Any]
    supervisor_reasoning: str

    # Original specialist results
    flight_results: str
    hotel_results: str
    weather_results: str
    itinerary: str

    # New budget + HITL state
    budget_results: str
    approval_request: str
    approved: bool
    human_feedback: str
    final_response: str
    integration_trace: Annotated[list[dict[str, str]], operator.add]

    llm_calls: int


# =========================
# Shared helpers
# =========================
KNOWN_AGENTS = {
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
    "itinerary_agent",
}

AGENT_ORDER = [
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
    "itinerary_agent",
]


def _llm_text(system_prompt: str, user_prompt: str) -> str:
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    return str(response.content)


def _json_from_llm(text: str) -> dict[str, Any]:
    """Extract the first complete JSON object returned by the model."""
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("The model did not return a JSON object.")

    return json.loads(text[start : end + 1])


def _empty_constraints() -> dict[str, Any]:
    return {
        "destination": "",
        "origin": "",
        "duration": "",
        "budget": "",
        "travel_style": "",
        "special_preferences": [],
    }


# =========================
# Supervisor Agent + Input Guardrail
# =========================
def supervisor_agent(state: TravelState):
    query = state["user_query"]
    llm_calls = state.get("llm_calls", 0)

    guardrail_prompt = f"""
Determine whether the following request belongs to travel planning or travel
information. Valid requests can include destinations, flights, hotels, weather,
budgets, visas, transportation, sightseeing, food, packing, or itineraries.

Block clearly unrelated requests and requests asking for harmful or illegal
instructions. Do not block a valid travel request merely because some details
are missing.

Return strict JSON only:
{{
  "allowed": true,
  "reason": ""
}}

User request:
{query}
"""

    # Fail open on parser/model errors so a temporary JSON-format issue does not
    # break the original travel-planning behavior.
    try:
        guardrail_raw = _llm_text(
            "You are the input guardrail for a travel-planning application. "
            "Return strict JSON only.",
            guardrail_prompt,
        )
        guardrail_result = _json_from_llm(guardrail_raw)
        allowed = bool(guardrail_result.get("allowed", True))
        guardrail_reason = str(guardrail_result.get("reason", "")).strip()
        llm_calls += 1
    except Exception as exc:
        print(f"Guardrail fallback used: {exc}")
        allowed = True
        guardrail_reason = "Guardrail validation fallback allowed the request."

    if not allowed:
        reason = guardrail_reason or (
            "TripMate AI can only help with travel-planning requests. "
            "Please ask about a destination, flight, hotel, weather, budget, "
            "or itinerary."
        )
        return {
            "guardrail_allowed": False,
            "guardrail_reason": reason,
            "selected_agents": [],
            "trip_constraints": _empty_constraints(),
            "supervisor_reasoning": reason,
            "final_response": reason,
            "messages": [AIMessage(content=f"Guardrail blocked request: {reason}")],
            "llm_calls": llm_calls,
        }

    supervisor_prompt = f"""
You are the supervisor of a multi-agent travel-planning system.
Choose only the specialist agents needed for the request.

Available agents:
- flight_agent: flights, airports, airlines, routes, airfare, or booking advice
- hotel_agent: hotels, accommodation, neighborhoods, or places to stay
- weather_agent: weather, climate, season, forecast, or packing advice
- budget_agent: cost, affordability, price limits, or budget feasibility
- itinerary_agent: creates the integrated travel plan and must always be included

Return strict JSON only using this schema:
{{
  "selected_agents": ["flight_agent", "hotel_agent", "weather_agent", "budget_agent", "itinerary_agent"],
  "trip_constraints": {{
    "destination": "",
    "origin": "",
    "duration": "",
    "budget": "",
    "travel_style": "",
    "special_preferences": []
  }},
  "reasoning": ""
}}

User request:
{query}
"""

    try:
        supervisor_raw = _llm_text(
            "You route work to travel specialist agents. Return strict JSON only.",
            supervisor_prompt,
        )
        parsed = _json_from_llm(supervisor_raw)
        requested_agents = parsed.get("selected_agents", [])
        selected_agents = [
            name for name in AGENT_ORDER
            if name in requested_agents and name in KNOWN_AGENTS
        ]

        # The itinerary agent integrates whichever specialist results were selected.
        if "itinerary_agent" not in selected_agents:
            selected_agents.append("itinerary_agent")

        constraints = _empty_constraints()
        parsed_constraints = parsed.get("trip_constraints", {})
        if isinstance(parsed_constraints, dict):
            constraints.update(parsed_constraints)

        reasoning = str(parsed.get("reasoning", "")).strip()
        llm_calls += 1
    except Exception as exc:
        print(f"Supervisor fallback used: {exc}")
        # Original workflow behavior is preserved as the fallback.
        selected_agents = AGENT_ORDER.copy()
        constraints = _empty_constraints()
        reasoning = (
            "Supervisor parsing failed, so the original full travel workflow "
            "was selected as a safe fallback."
        )

    return {
        "guardrail_allowed": True,
        "guardrail_reason": guardrail_reason,
        "selected_agents": selected_agents,
        "trip_constraints": constraints,
        "supervisor_reasoning": reasoning,
        "messages": [AIMessage(content="Supervisor created the agent plan.")],
        "llm_calls": llm_calls,
    }


# =========================
# Guardrail blocked response
# =========================
def guardrail_blocked_agent(state: TravelState):
    reason = state.get("final_response") or state.get("guardrail_reason") or (
        "This request was blocked by the travel input guardrail."
    )
    return {
        "final_response": reason,
        "messages": [AIMessage(content=reason)],
    }


# =========================
# Flight Agent - original behavior kept
# =========================
FLIGHT_AGENT_PROMPT = """
You are a travel flight expert.

User Query:
{query}

Airport Information:
{airport_data}

Airline Information:
{airline_data}

Generate:
1. Likely departure airport
2. Likely arrival airport
3. Airlines serving this route
4. Typical flight duration
5. Estimated airfare range
6. Peak season pricing warning
7. Booking advice

Return concise travel guidance.
"""


def flight_agent(state: TravelState):
    query = state["user_query"]
    source = "mcp:aviationstack"

    try:
        airports = asyncio.run(aviation_mcp_call("list_airports"))
        airlines = asyncio.run(aviation_mcp_call("list_airlines"))
        prompt = FLIGHT_AGENT_PROMPT.format(
            query=query,
            airport_data=str(airports)[:3000],
            airline_data=str(airlines)[:3000],
        )
        response = llm.invoke(
            [
                SystemMessage(content="You are an expert travel flight planner."),
                HumanMessage(content=prompt),
            ]
        )
        flight_data = str(response.content)
    except Exception as mcp_exc:
        print(f"FLIGHT MCP FALLBACK: {type(mcp_exc).__name__}: {mcp_exc}", flush=True)
        try:
            flight_data = search_flights(query)
            if "API_KEY is missing" in flight_data or "Flight API error" in flight_data:
                raise RuntimeError(flight_data)
            source = "direct:aviationstack"
        except Exception as direct_exc:
            print(
                f"FLIGHT DIRECT FALLBACK: {type(direct_exc).__name__}: {direct_exc}",
                flush=True,
            )
            source = "fallback:guidance"
            flight_data = (
                "Live flight data is not configured for this deployment. "
                "Use the likely major airports for the requested route, compare nonstop "
                "and one-stop options, and verify current schedules and fares before booking. "
                "AviationStack is used for status/schedule context and may not provide ticket prices."
            )

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight specialist completed.")],
        "integration_trace": [{"agent": "flight_agent", "source": source}],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =========================
# Hotel Agent - original behavior kept
# =========================
def hotel_agent(state: TravelState):
    query = f"Best hotels, neighborhoods, and accommodation options for {state['user_query']}"
    source = "mcp:tavily"

    try:
        hotel_results = asyncio.run(tavily_mcp_search(query))
    except Exception as mcp_exc:
        print(f"HOTEL MCP FALLBACK: {type(mcp_exc).__name__}: {mcp_exc}", flush=True)
        try:
            hotel_results = tavily_search(query)
            source = "direct:tavily"
        except Exception as direct_exc:
            print(
                f"HOTEL DIRECT FALLBACK: {type(direct_exc).__name__}: {direct_exc}",
                flush=True,
            )
            source = "fallback:guidance"
            hotel_results = (
                "Live hotel search is not configured. Prefer a well-reviewed property "
                "near the main activity area or a transit hub, compare cancellation terms, "
                "and verify taxes and resort fees before booking."
            )

    return {
        "hotel_results": str(hotel_results),
        "messages": [AIMessage(content="Hotel specialist completed.")],
        "integration_trace": [{"agent": "hotel_agent", "source": source}],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =========================
# Weather Agent - original behavior kept
# =========================
def weather_agent(state: TravelState):
    city = extract_destination(state["user_query"])
    source = "mcp:openweather"

    try:
        weather_data = asyncio.run(weather_mcp_search(city))
        forecast_data = asyncio.run(forecast_mcp_search(city))
        weather_results = (
            f"Current Weather:\n{weather_data}\n\n"
            f"Forecast:\n{forecast_data}"
        )
    except Exception as mcp_exc:
        print(f"WEATHER MCP FALLBACK: {type(mcp_exc).__name__}: {mcp_exc}", flush=True)
        try:
            weather_results = get_weather_bundle(city)
            source = "direct:openweather"
        except Exception as direct_exc:
            print(
                f"WEATHER DIRECT FALLBACK: {type(direct_exc).__name__}: {direct_exc}",
                flush=True,
            )
            source = "fallback:guidance"
            weather_results = (
                f"Live weather for {city} is not configured. Check a current forecast "
                "before departure and keep the itinerary flexible for heat, rain, or wind."
            )

    return {
        "weather_results": weather_results,
        "messages": [AIMessage(content="Weather specialist completed.")],
        "integration_trace": [{"agent": "weather_agent", "source": source}],
    }


# =========================
# Budget Agent - new specialist
# =========================
def budget_agent(state: TravelState):
    prompt = f"""
Analyze whether this trip is realistic for the user's budget.

User Query:
{state['user_query']}

Trip Constraints:
{state.get('trip_constraints', {})}

Flight Results:
{state.get('flight_results', '')}

Hotel Results:
{state.get('hotel_results', '')}

Weather Results:
{state.get('weather_results', '')}

Return:
1. Estimated cost categories
2. Budget risk areas
3. Money-saving suggestions
4. Overall feasibility

If exact live prices are unavailable, clearly label estimates as approximate.
"""

    response = llm.invoke(
        [
            SystemMessage(content="You are a practical travel budget analyst."),
            HumanMessage(content=prompt),
        ]
    )

    return {
        "budget_results": response.content,
        "messages": [AIMessage(content="Budget assessment generated.")],
        "integration_trace": [{"agent": "budget_agent", "source": "model:analysis"}],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =========================
# Itinerary Agent - original behavior extended with selected results
# =========================
def itinerary_agent(state: TravelState):
    prompt = f"""
Create a complete travel itinerary.

User Query:
{state['user_query']}

Trip Constraints:
{state.get('trip_constraints', {})}

Flight Results:
{state.get('flight_results', '')}

Hotel Results:
{state.get('hotel_results', '')}

Weather Results:
{state.get('weather_results', '')}

Budget Results:
{state.get('budget_results', '')}

Make the itinerary practical, budget-aware, and easy to follow.
Create a clear draft that is ready for human review.
"""

    response = llm.invoke(
        [
            SystemMessage(content="You are an expert travel planner."),
            HumanMessage(content=prompt),
        ]
    )

    approval_request = (
        "Please review the generated draft itinerary. Approve it to create the "
        "final polished plan, or provide feedback for revision."
    )

    return {
        "itinerary": response.content,
        "approval_request": approval_request,
        "messages": [AIMessage(content="Draft itinerary created for human review.")],
        "integration_trace": [{"agent": "itinerary_agent", "source": "model:planning"}],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =========================
# Human-in-the-Loop approval
# =========================
def human_approval_agent(state: TravelState):
    # Do not wrap interrupt() in try/except. LangGraph uses it to pause execution.
    review = interrupt(
        {
            "question": "Do you approve this itinerary?",
            "draft_itinerary": state.get("itinerary", ""),
            "approval_request": state.get("approval_request", ""),
            "selected_agents": state.get("selected_agents", []),
            "supervisor_reasoning": state.get("supervisor_reasoning", ""),
            "expected_response": {
                "approved": True,
                "feedback": "Optional revision feedback",
            },
        }
    )

    approved = bool(review.get("approved", False))
    human_feedback = str(review.get("feedback", "")).strip()

    return {
        "approved": approved,
        "human_feedback": human_feedback,
        "messages": [AIMessage(content="Human approval step completed.")],
    }


# =========================
# Final Response Agent - original format kept, HITL feedback added
# =========================
def final_agent(state: TravelState):
    if state.get("approved", False):
        review_instruction = (
            "The user approved the draft. Preserve its decisions while polishing it."
        )
    else:
        review_instruction = f"""
The user requested a revision. Apply this feedback carefully:
{state.get('human_feedback', '') or 'Improve the draft before finalizing it.'}
"""

    final_prompt = f"""
Generate the final travel response for the user.

Human Review:
{review_instruction}

User Request:
{state['user_query']}

Supervisor Constraints:
{state.get('trip_constraints', {})}

Flights:
{state.get('flight_results', '')}

Hotels:
{state.get('hotel_results', '')}

Weather:
{state.get('weather_results', '')}

Budget Analysis:
{state.get('budget_results', '')}

Draft Itinerary:
{state.get('itinerary', '')}

Format the final answer beautifully using these sections:
1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Weather Information
5. Day-by-Day Itinerary
6. Estimated Budget
7. Final Recommendations

Important:
- Be clear and practical.
- Mention that live flight APIs may not provide ticket prices when pricing is unavailable.
- Include weather-based travel advice.
- Keep the response useful for real travel planning.
- Incorporate the human feedback when revision was requested.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content="You are a professional AI travel booking assistant."
            ),
            HumanMessage(content=final_prompt),
        ]
    )

    return {
        "final_response": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# =========================
# Dynamic Supervisor Routing
# =========================
ROUTE_MAP = {
    "guardrail_blocked": "guardrail_blocked",
    "flight_agent": "flight_agent",
    "hotel_agent": "hotel_agent",
    "weather_agent": "weather_agent",
    "budget_agent": "budget_agent",
    "itinerary_agent": "itinerary_agent",
}


def _selected_agents(state: TravelState) -> list[str]:
    selected = state.get("selected_agents", [])
    return [agent for agent in AGENT_ORDER if agent in selected]


def route_from_supervisor(state: TravelState) -> str:
    if not state.get("guardrail_allowed", True):
        return "guardrail_blocked"

    selected = _selected_agents(state)
    return selected[0] if selected else "itinerary_agent"


def route_after_agent(current_agent: str):
    def route(state: TravelState) -> str:
        selected = _selected_agents(state)
        current_index = AGENT_ORDER.index(current_agent)

        for next_agent in AGENT_ORDER[current_index + 1 :]:
            if next_agent in selected:
                return next_agent

        return "itinerary_agent"

    return route


# =========================
# Build Graph
# =========================
graph = StateGraph(TravelState)

graph.add_node("supervisor", supervisor_agent)
graph.add_node("guardrail_blocked", guardrail_blocked_agent)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("weather_agent", weather_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("human_approval", human_approval_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "supervisor")
graph.add_conditional_edges("supervisor", route_from_supervisor, ROUTE_MAP)

graph.add_conditional_edges(
    "flight_agent", route_after_agent("flight_agent"), ROUTE_MAP
)
graph.add_conditional_edges(
    "hotel_agent", route_after_agent("hotel_agent"), ROUTE_MAP
)
graph.add_conditional_edges(
    "weather_agent", route_after_agent("weather_agent"), ROUTE_MAP
)
graph.add_conditional_edges(
    "budget_agent", route_after_agent("budget_agent"), ROUTE_MAP
)

graph.add_edge("itinerary_agent", "human_approval")
graph.add_edge("human_approval", "final_agent")
graph.add_edge("final_agent", END)
graph.add_edge("guardrail_blocked", END)

# =========================
# Checkpointer
# PostgreSQL is used when DATABASE_URL is configured. The public portfolio
# deployment falls back to in-memory checkpoints so the HITL demo still works.
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
_conn = None
PERSISTENCE_MODE = "memory"

if DATABASE_URL:
    try:
        if "sslmode=" not in DATABASE_URL:
            separator = "&" if "?" in DATABASE_URL else "?"
            DATABASE_URL = f"{DATABASE_URL}{separator}sslmode=require"

        _conn = psycopg.connect(
            DATABASE_URL,
            autocommit=True,
            row_factory=dict_row,
        )
        checkpointer = PostgresSaver(_conn)
        checkpointer.setup()
        PERSISTENCE_MODE = "postgres"
    except Exception as exc:
        print(f"PostgreSQL unavailable; using MemorySaver: {exc}")
        checkpointer = MemorySaver()
else:
    checkpointer = MemorySaver()

travel_graph = graph.compile(checkpointer=checkpointer)


# =========================
# FastAPI-facing helpers
# =========================
def _interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None

    first_interrupt = interrupts[0]
    payload = getattr(first_interrupt, "value", first_interrupt)
    return payload if isinstance(payload, dict) else {"value": payload}


def _serialize_result(
    result: dict[str, Any],
    thread_id: str,
) -> dict[str, Any]:
    messages = result.get("messages", [])
    last_message = messages[-1].content if messages else ""
    answer = result.get("final_response") or last_message
    interrupt_payload = _interrupt_payload(result)

    if interrupt_payload:
        answer = interrupt_payload.get("draft_itinerary") or result.get(
            "itinerary", ""
        )

    return {
        "thread_id": thread_id,
        "answer": answer,
        "requires_approval": interrupt_payload is not None,
        "approval_request": (
            interrupt_payload.get("approval_request", "")
            if interrupt_payload
            else result.get("approval_request", "")
        ),
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "weather_results": result.get("weather_results", ""),
        "budget_results": result.get("budget_results", ""),
        "itinerary": (
            interrupt_payload.get("draft_itinerary", "")
            if interrupt_payload
            else result.get("itinerary", "")
        ),
        "selected_agents": result.get("selected_agents", []),
        "trip_constraints": result.get("trip_constraints", {}),
        "supervisor_reasoning": result.get("supervisor_reasoning", ""),
        "guardrail_allowed": result.get("guardrail_allowed", True),
        "guardrail_reason": result.get("guardrail_reason", ""),
        "approved": result.get("approved"),
        "human_feedback": result.get("human_feedback", ""),
        "integration_trace": result.get("integration_trace", []),
        "demo_mode": DEMO_MODE,
        "persistence_mode": PERSISTENCE_MODE,
        "llm_calls": result.get("llm_calls", 0),
    }


def run_travel_agent(user_input: str, thread_id: str | None = None):
    """Start a new travel-planning run and pause at human approval."""
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {"configurable": {"thread_id": thread_id}}

    result = travel_graph.invoke(
        {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
            "guardrail_allowed": True,
            "guardrail_reason": "",
            "selected_agents": [],
            "trip_constraints": _empty_constraints(),
            "supervisor_reasoning": "",
            "flight_results": "",
            "hotel_results": "",
            "weather_results": "",
            "budget_results": "",
            "itinerary": "",
            "approval_request": "",
            "approved": False,
            "human_feedback": "",
            "final_response": "",
            "integration_trace": [],
            "llm_calls": 0,
        },
        config=config,
    )

    return _serialize_result(result, thread_id)


def resume_travel_agent(
    thread_id: str,
    approved: bool,
    feedback: str = "",
):
    """Resume the paused LangGraph thread after human review."""
    if not thread_id:
        raise ValueError("thread_id is required to resume a travel plan.")

    config = {"configurable": {"thread_id": thread_id}}
    result = travel_graph.invoke(
        Command(
            resume={
                "approved": approved,
                "feedback": feedback.strip(),
            }
        ),
        config=config,
    )

    return _serialize_result(result, thread_id)


def system_capabilities() -> dict[str, Any]:
    """Return safe, non-secret deployment capability metadata for the UI."""
    aviation_key = bool(
        os.getenv("AVIATION_STACK_API_KEY") or os.getenv("AVIATIONSTACK_API_KEY")
    )
    return {
        "app": "TripMate AI",
        "version": "3.1.0",
        "demo_mode": DEMO_MODE,
        "llm": (
            "Mistral mistral-small-latest"
            if MISTRAL_API_KEY
            else (
                "Groq llama-3.3-70b-versatile"
                if GROQ_API_KEY
                else "Deterministic demo engine"
            )
        ),
        "persistence": PERSISTENCE_MODE,
        "integrations": {
            "tavily": bool(os.getenv("TAVILY_API_KEY")),
            "aviationstack": aviation_key,
            "openweather": bool(os.getenv("OPENWEATHER_API_KEY")),
            "mcp": True,
        },
        "features": [
            "input_guardrail",
            "supervisor_routing",
            "multi_agent_specialists",
            "mcp_first_with_direct_fallbacks",
            "human_in_the_loop",
            "fastapi",
        ],
    }
