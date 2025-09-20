# import asyncio
# from json import load
# from fastapi import FastAPI
# from fastapi.responses import StreamingResponse
# from llama_index.core.agent.workflow import FunctionAgent, AgentWorkflow
# from llama_index.llms.openai import OpenAI
# from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
# from dotenv import load_dotenv

# load_dotenv()
# from llama_index.core.workflow import Context
# from llama_index.core.workflow.events import InputRequiredEvent, HumanResponseEvent
# from tools.kb_tool import rag_tool

# llm = OpenAI(model="gpt-4o")

# async def store_math_solution(ctx: Context, solution_summary: str, full_solution: str) -> str:
#     state = await ctx.get("state") or {}
#     state["math_solution"] = {"summary": solution_summary, "full": full_solution}
#     await ctx.set("state", state)
#     return "Math solution stored."

# # this is the human feedback gate - using llamaindex 
# async def math_feedback_gate(ctx: Context, solution: str):
#     """
#     Custom callback: after generating a solution, request human approval.
#     """
#     # Pause workflow until human feedback arrives
#     await ctx.send_event(
#         InputRequiredEvent(
#             key="math_feedback",
#             prompt="Review the proposed solution below and provide feedback.",
#             payload={"solution": solution},
#         )
#     )
#     # Wait for frontend response
#     response_event: HumanResponseEvent = await ctx.wait_for_event(
#         HumanResponseEvent, key="math_feedback"
#     )
#     feedback = response_event.response

#     if feedback.strip().lower() in ["yes", "approve", "ok", "looks good"]:
#         await store_math_solution(ctx, "Approved solution", solution)
#         return "Solution approved and stored."
#     else:
#         return f"Human Feedback: {feedback}"

# # get MCP tools (async)
# async def get_mcp_tools():
#     mcp_client = BasicMCPClient("http://localhost:8000/sse")  # Adjust as needed
#     mcp_tool_spec = McpToolSpec(client=mcp_client)
#     return await mcp_tool_spec.to_tool_list_async()

# # 3. Create agents with different tools
# async def create_agents():
#     mcp_tools = await get_mcp_tools()
#     tools = [rag_tool] + mcp_tools
#     research_agent = FunctionAgent(
#         name="ResearchAgent",
#         description=("""
#                 Senior Mathematics Researcher. Use available tools to gather, verify and organize information relevant to the user's {topic}. 
#                 Prefer the RAG vector DB (rag_tool) first, if relevancy is low or no results, fall back to websearch_tool. 
#                 When using websearch_tool, use `search_depth='basic'` for straightforward queries and `search_depth='advanced'` for complex
#                 questions or when instructed.
#                 """
#             ),
#         system_prompt=("""
#                 Role: You are a Senior Mathematics Researcher with 15 years of experience.
#                 Goal: Gather relevant information for the user's query {topic} using the provided tools.
#                 Behavior specifics:
#                 - First attempt retrieval from the vector DB via rag_tool. If results are high-quality, use them.
#                 - If the vector DB returns a low result, call websearch_tool with an appropriate search_depth.
#                 - Produce a nice detailed 'research summary' that the MathAgent can consume as context.
#                 - When research is sufficient, hand off control to MathAgent. """
#         ),
#         llm=llm,
#         tools=tools,
#         can_handoff_to=["MathAgent"],
#     )

#     # math agent
#     math_agent = FunctionAgent(
#         name="MathAgent",
#         description=("""Takes the ResearchAgent's findings (from workflow state) as context and solves the user's mathematical query in a step-by-step, detailed manner. 
#             Provide clear steps, justifications, and a final concise answer. 
#             Store the final solution using store_math_solution.
#             """
#             ),
#         system_prompt=("""You are MathAgent. 
#             Behavior:
#             - Read research notes given from ResearchAgent and treat them as authoritative context.
#             - Provide a careful, step-by-step derivation/solution to the user's problem.
#             - After producing the solution ask for human feedback to improve answers.
#             - Hand back to ResearchAgent if you need extra info or followup verification.
#         """
#         ),
#         llm=llm,
#         tools=[math_feedback_gate],
#         can_handoff_to=["ResearchAgent"]
#     )
#     return [research_agent,math_agent]

# # 4. Create the workflow
# async def get_workflow():
#     agents = await create_agents()
#     workflow = AgentWorkflow(
#         agents=agents,
#         root_agent=agents[0].name  # Start with the websearch agent
#     )
#     return workflow

# # 5. FastAPI app with streaming endpoint
# app = FastAPI()

# class ChatRequest(BaseModel):
#     topic: str

# class HumanInputRequest(BaseModel):
#     session_id: str
#     feedback: str

# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from typing import Dict,Any
# from pydantic import BaseModel

# origins = [
#     "http://localhost:3000",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# sessions : Dict[str, Dict[str,Any]] ={}

# @app.get("/chat")
# async def chat(user_msg: str):
#     workflow = await get_workflow()
#     handler = workflow.run(user_msg=user_msg)

#     async def event_generator():
#         async for event in handler.stream_events():
#             # You can customize what you yield based on event type
#             yield f"data: {str(event)}\n\n"

#     return StreamingResponse(event_generator(), media_type="text/event-stream")

# @app.post("/human-input")
# async def human_input(req: HumanInputRequest):
#     """Resume workflow with human feedback."""

#     agent_workflow = await get_workflow()
#     sess = sessions.get(req.session_id)
#     if not sess:
#         raise HTTPException(status_code=404, detail="Session not found")

#     if sess["status"] != "waiting_human":
#         raise HTTPException(status_code=400, detail="Not waiting for input")

#     ctx_dict = sess["ctx"]
#     if not ctx_dict:
#         raise HTTPException(status_code=500, detail="Missing context to restore")

#     # Restore context and resume workflow
#     restored_ctx = Context.from_dict(agent_workflow, ctx_dict, serializer=JsonSerializer())
#     handler = agent_workflow.run(ctx=restored_ctx)

#     # Inject human feedback
#     await handler.ctx.send_event(HumanResponseEvent(response=req.feedback))

#     # Collect final results
#     async for event in handler.stream_events():
#         sess["events"].append(str(event))

#     sess["status"] = "completed"
#     return {"status": "completed", "events": sess["events"]}

