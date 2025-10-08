import asyncio, uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any,Optional
from pydantic import BaseModel
from agents import MathematicalAgent

app = FastAPI(title="Math Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://math-agent-mu.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: Dict[str, Any] = {}

class ChatRequest(BaseModel):
    topic: str
    session_id: Optional[str] = None

class HumanInputRequest(BaseModel):
    session_id: str
    feedback: str

async def process_math_question(session_id: str, topic: str):
    """Process a math question: research -> solve -> await feedback"""
    sess = sessions.get(session_id)
    if not sess:
        return
    try:
        agent = sess["agent"]
        
        # Step 1: Research
        sess["status"] = "researching"
        research_result = await agent.research_topic(topic)
        sess["research_context"] = research_result
        print(f"Research completed for {session_id}")
        
        # Step 2: Solve
        sess["status"] = "solving"
        solution = await agent.solve_problem(topic, research_result)
        print(f"Solution generated for {session_id}")
        
        # Step 3: Present and await feedback
        sess["current_solution"] = solution
        sess["waiting_for_approval"] = True
        sess["status"] = "waiting_for_approval"
        
        approval_message = f""" Yay! Solution Complete!
        Here's my step by step solution:

        {solution}

        ---
        Please Review:
        - Type "approve" if the solution is correct
        - Or provide specific feedback for improvements."""
        
        sess["messages"].append({
            "role": "assistant",
            "content": approval_message
        })
        
        print(f" Awaiting feedback for {session_id}")
        
    except Exception as e:
        print(f"Error processing question: {e}")
        if session_id in sessions:
            sessions[session_id]["status"] = "error"
            sessions[session_id]["messages"].append({
                "role": "assistant",
                "content": f"I encountered an error: {str(e)}"
            })

@app.get("/")
async def root():
    return {"message": "Math Agent API is running"}

@app.post("/chat")
async def chat(req: ChatRequest):
    """Start a new math session or continue existing one"""
    try:
        print(f"Chat request: topic='{req.topic[:100]}...', session_id={req.session_id}")
        
        # Continue existing session
        if req.session_id and req.session_id in sessions:
            session_id = req.session_id
            sess = sessions[session_id]
            
            sess["messages"].append({"role": "user", "content": req.topic})
            asyncio.create_task(process_math_question(session_id, req.topic))
            
            return {
                "session_id": session_id,
                "status": "processing",
                "messages": sess["messages"]
            }
        
        # Create new session
        session_id = uuid.uuid4().hex
        
        sessions[session_id] = {
            "agent": MathematicalAgent(),
            "status": "processing",
            "messages": [{"role": "user", "content": req.topic}],
            "waiting_for_approval": False,
            "current_solution": None,
            "current_topic": req.topic,
            "research_context": None
        }

        asyncio.create_task(process_math_question(session_id, req.topic))
        
        return {
            "session_id": session_id,
            "status": "processing", 
            "messages": sessions[session_id]["messages"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f" Error starting chat: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/chat/{session_id}")
async def get_chat(session_id: str):
    """Get current session state"""
    sess = sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "status": sess["status"],
        "messages": sess["messages"],
        "waiting": {"key": "approval"} if sess.get("waiting_for_approval") else None
    }

@app.post("/human-input")
async def human_input(req: HumanInputRequest):
    """Process human feedback and improve solution"""
    sess = sessions.get(req.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not sess.get("waiting_for_approval"):
        raise HTTPException(status_code=400, detail="Session is not waiting for feedback")

    try:
        print(f"Processing feedback for {req.session_id}: {req.feedback[:100]}...")
        
        sess["messages"].append({"role": "user","content": req.feedback})
        
        feedback_lower = req.feedback.strip().lower()
        current_solution = sess.get("current_solution", "")
        
        if any(word in feedback_lower for word in ["approve", "approved", "yes", "ok", "correct", "good", "looks good"]):

            # Solution approved
            final_response = f"""Solution Approved!
            Final Solution:
            {current_solution}"""
            
            sess["status"] = "completed"
            sess["waiting_for_approval"] = False
            sess["current_solution"] = None
            
        else:
            # Improve solution based on feedback
            sess["status"] = "improving"
            sess["messages"].append({
                "role": "assistant",
                "content": "Thank you for the feedback! Let me improve the solution..."
            })
            
            agent = sess["agent"]
            topic = sess["current_topic"]
            
            improved_solution = await agent.improve_solution(
                current_solution, req.feedback, topic
            )
            
            final_response = f"""Solution Improved Based on user Feedback
            Your Feedback: {req.feedback}

            Improved Solution:
            {improved_solution}

            ---
            Please Review Again: 
            - Type "approve" if this solution looks good
            - Or provide additional feedback for further refinements"""
            
            # Set up for another round of feedback
            sess["current_solution"] = improved_solution
            sess["status"] = "waiting_for_approval"
        
        sess["messages"].append({
            "role": "assistant",
            "content": final_response
        })
        
        return {"status": "success", "message": "Feedback processed successfully"}
        
    except Exception as e:
        print(f"Error processing feedback: {e}")
        sess["status"] = "error" 
        sess["messages"].append({
            "role": "assistant",
            "content": f"I encountered an error processing your feedback: {str(e)}"
        })
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.delete("/chat/{session_id}")
async def delete_session(session_id: str):
    """Clean up session"""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")