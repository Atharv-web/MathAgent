import asyncio
from dotenv import load_dotenv
from llama_index.core.workflow import Context
from tools.kb_tool import rag_tool
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import FunctionAgent, AgentWorkflow
from llama_index.core.workflow.events import InputRequiredEvent, HumanResponseEvent
load_dotenv()

# setting the llm
llm= OpenAI(model="gpt-4o")

# function that stores agents answer in context
async def store_math_solution(ctx: Context, solution_summary: str, full_solution: str) -> str:
    state = await ctx.get("state") or {}
    state["math_solution"] = {"summary": solution_summary, "full": full_solution}
    await ctx.set("state", state)
    return "Math solution stored."

# this is the human feedback gate - using llamaindex 
async def math_feedback_gate(ctx: Context, solution: str):
    """
    Custom callback: after generating a solution, request human approval.
    """
    # Pause workflow until human feedback arrives
    await ctx.send_event(
        InputRequiredEvent(
            key="math_feedback",
            prompt="Review the proposed solution below and provide feedback.",
            payload={"solution": solution},
        )
    )
    # Wait for frontend response
    response_event: HumanResponseEvent = await ctx.wait_for_event(
        HumanResponseEvent, key="math_feedback"
    )
    feedback = response_event.response

    if feedback.strip().lower() in ["yes", "approve", "ok", "looks good"]:
        await store_math_solution(ctx, "Approved solution", solution)
        return "Solution approved and stored."
    else:
        return f"Human Feedback: {feedback}"

# wrapping our mcp tool
mcp_client = BasicMCPClient("python", args=["mcp_server.py"])
mcp_tool_spec = McpToolSpec(client=mcp_client)
mcp_tools = asyncio.run(mcp_tool_spec.to_tool_list_async())
    # all the tools required by the researcher.
tools = [rag_tool] + mcp_tools
# research agent
research_agent = FunctionAgent(
    name="ResearchAgent",
    description=("""
            Senior Mathematics Researcher. Use available tools to gather, verify and organize information relevant to the user's {topic}. 
            Prefer the RAG vector DB (rag_tool) first, if relevancy is low or no results, fall back to websearch_tool. 
            When using websearch_tool, use `search_depth='basic'` for straightforward queries and `search_depth='advanced'` for complex
            questions or when instructed.
            """
        ),
    system_prompt=("""
            Role: You are a Senior Mathematics Researcher with 15 years of experience.
            Goal: Gather relevant information for the user's query {topic} using the provided tools.
            Behavior specifics:
            - First attempt retrieval from the vector DB via rag_tool. If results are high-quality, use them.
            - If the vector DB returns a low result, call websearch_tool with an appropriate search_depth.
            - Produce a nice detailed 'research summary' that the MathAgent can consume as context.
            - When research is sufficient, hand off control to MathAgent. """
    ),
    llm=llm,
    tools=agent_tools,
    can_handoff_to=["MathAgent"],
)
    
# math agent 
math_agent = FunctionAgent(
    name="MathAgent",
    description=("""Takes the ResearchAgent's findings (from workflow state) as context and solves the user's mathematical query in a step-by-step, detailed manner. 
        Provide clear steps, justifications, and a final concise answer. 
        Store the final solution using store_math_solution.
        """
        ),
    system_prompt=("""You are MathAgent. 
        Behavior:
        - Read research notes given from ResearchAgent and treat them as authoritative context.
        - Provide a careful, step-by-step derivation/solution to the user's problem.
        - After producing the solution ask for human feedback to improve answers.
        - Hand back to ResearchAgent if you need extra info or followup verification.
    """
    ),
    llm=llm,
    tools=[math_feedback_gate],
    can_handoff_to=["ResearchAgent"]
)

# set the agent workflow
agent_workflow = AgentWorkflow(
    agents=[research_agent, math_agent],
    root_agent=research_agent.name,
    initial_state={
        "topic": None,
    },
)


