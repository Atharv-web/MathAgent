import asyncio, os, uuid, json, re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any,Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from tools.kb_tool import rag_tool

load_dotenv()

# ---- Config ----
llm = OpenAI(model="gpt-4o", temperature=0.1)
origins = ["http://localhost:3000"]

app = FastAPI(title="Math Agent", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- In-memory session store ----
sessions: Dict[str, Any] = {}

# ---- Math I/O Guardrails ----
class MathGuardrails:
    @staticmethod
    def validate_math_input(topic: str) -> tuple[bool, str]:
        """Validate if the input is maths related"""
        if not topic or not topic.strip():
            return False, "Please provide a mathematical question or problem."
        
        topic_lower = topic.lower().strip()
        
        # Math keywords and patterns
        math_keywords = [
            'solve', 'equation', 'derivative', 'integral', 'function', 'graph', 'plot',
            'algebra', 'calculus', 'geometry', 'trigonometry', 'statistics', 'probability',
            'matrix', 'vector', 'limit', 'series', 'theorem', 'proof', 'formula',
            'calculate', 'compute', 'simplify', 'factor', 'expand', 'evaluate',
            'polynomial', 'exponential', 'logarithm', 'sine', 'cosine', 'tangent',
            'differential', 'optimization', 'minimum', 'maximum', 'area', 'volume',
            'perimeter', 'distance', 'slope', 'intercept', 'quadratic', 'linear',
            'parabola', 'circle', 'triangle', 'rectangle', 'sphere', 'cylinder',
            'binomial', 'factorial', 'permutation', 'combination', 'variance', 'deviation'
        ]
        
        # Math symbols and patterns
        math_patterns = [
            r'[+\-*/=<>≤≥≠±∞]',           # Basic math operators
            r'[xy]\^?\d*',                # Variables with powers
            r'\d+[xy]',                   # Coefficients with variables  
            r'sin|cos|tan|log|ln|sqrt',   # Math functions
            r'∫|∑|∏|∂|∆|π|θ|α|β|γ|λ|μ|σ', # Math symbols
            r'\b\d+\.\d+\b',              # Decimal numbers
            r'\b\d+/\d+\b',               # Fractions
            r'\([^)]*[xy][^)]*\)',        # Expressions with variables
            r'[a-z]\s*²|[a-z]\s*³',       # Squared/cubed variables
        ]
        
        # Check for math keywords
        has_math_keywords = any(keyword in topic_lower for keyword in math_keywords)
        
        # Check for math patterns
        has_math_patterns = any(re.search(pattern, topic_lower) for pattern in math_patterns)
        
        # Check for explicit non-math content
        non_math_indicators = [
            'write a story', 'tell me a joke', 'weather', 'news', 'recipe',
            'movie', 'book recommendation', 'health advice', 'relationship',
            'what is your opinion', 'how do you feel', 'personal experience'
        ]
        
        has_non_math = any(indicator in topic_lower for indicator in non_math_indicators)
        
        if has_non_math:
            return False, "I'm designed specifically for mathematical problems. Please ask a maths related question."
        
        if has_math_keywords or has_math_patterns:
            return True, "Valid mathematical input"
        
        # Edge case: might be math but unclear
        if any(word in topic_lower for word in ['find', 'what is', 'how much', 'calculate']):
            return True, "Potentially maths problem, so proceed with caution"
        
        return False, "This doesn't appear to be a mathematical question. I specialize in solving math problems. Please ask about equations, calculations, or mathematical concepts."
    
    @staticmethod
    def format_math_output(text: str) -> str:
        """Enhanced mathematical formatting for better display"""
        if not text:
            return text   
        formatted = text
        # Format common mathematical expressions
        replacements = [
            # Fractions - simple cases
            (r'(\d+)/(\d+)', r'\\frac{\\1}{\\2}'),
            # Powers
            (r'\^(\d+)', r'^{\\1}'),
            (r'\^([a-zA-Z]+)', r'^{\\1}'),
            # Square roots
            (r'sqrt\(([^)]+)\)', r'\\sqrt{\\1}'),
            (r'√\(([^)]+)\)', r'\\sqrt{\\1}'),
            # Greek letters and symbols
            (r'pi', r'π'),
            (r'infinity', r'∞'),
            (r'theta', r'θ'),
            (r'alpha', r'α'),
            (r'beta', r'β'),
            (r'gamma', r'γ'),
            # Derivatives
            (r'd/dx', r'\\frac{d}{dx}'),
            # Integrals  
            (r'integral', r'∫'),
        ]
        for pattern, replacement in replacements:
            formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        
        return formatted


class ChatRequest(BaseModel):
    topic: str
    session_id: Optional[str] = None
    
    # @validator('topic')
    def validate_math_topic(cls, v):
        is_valid, message = MathGuardrails.validate_math_input(v)
        if not is_valid:
            raise ValueError(message)
        return v.strip()
    
    class Config:
        extra = "ignore"

class HumanInputRequest(BaseModel):
    session_id: str
    feedback: str
    
    # @validator('feedback')
    def validate_feedback(cls, v):
        if not v or not v.strip():
            raise ValueError('Feedback cannot be empty')
        if len(v.strip()) > 2000:
            raise ValueError('Feedback is too long')
        return v.strip()
    
    class Config:
        extra = "ignore"

# ---- Tool setup ----
async def get_mcp_tools():
    try:
        mcp_client = BasicMCPClient("python", args=["mcp_server.py"])
        mcp_tool_spec = McpToolSpec(client=mcp_client)
        tools = await mcp_tool_spec.to_tool_list_async()
        print(f"MCP tools loaded: {len(tools)}")
        return tools
    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        return []

# Enhanced Math Agent with I/O Guardrails
class MathAgent:
    def __init__(self):
        self.research_agent = None
        self.math_agent = None
        self.tools_initialized = False
        
    async def _create_agents(self):
        if self.research_agent and self.math_agent and self.tools_initialized:
            return

        try:
            # Get tools
            mcp_tools = await get_mcp_tools()
            tools = [rag_tool] + mcp_tools
            print(f"Total tools available: {len(tools)}")

            # Research Agent with math focus
            self.research_agent = FunctionAgent(
                name="MathResearchAgent",
                description="Mathematics researcher specializing in providing context for math problems.",
                system_prompt="""You are a Senior Mathematics Researcher.
                STRICT GUIDELINES:
                    - ONLY respond to mathematics-related queries
                    - If asked about non math topics, respond: "I only help with mathematical problems"
                    - Use RAG tool first to search mathematical knowledge base
                    - Use web search only if RAG results are insufficient
                    - Provide comprehensive mathematical context including:
                        1.Relevant definitions and concepts
                        2.Applicable formulas and theorems
                        3.Common solution approaches
                        4.Mathematical background

                        Focus on accuracy and mathematical rigor.""",
                llm=llm,
                tools=tools,
            )
            print("Research agent created successfully")

        except Exception as e:
            print(f"Research agent creation failed: {e}")
            self.research_agent = None

        try:
            # Math Solver Agent
            self.math_agent = FunctionAgent(
                name="MathSolverAgent", 
                description="Expert mathematical problem solver providing step-by-step solutions.",
                system_prompt="""You are an Expert Mathematics Solver.
                STRICT GUIDELINES:
                    - ONLY solve mathematical problems
                    - Provide complete step-by-step solutions
                    - Explain reasoning for each step clearly
                    - Show all calculations and work
                    - Use proper mathematical notation
                    - Verify solutions when possible
                    - Include final answers clearly marked

                SOLUTION FORMAT:
                    1. State the problem clearly
                    2. Identify the mathematical approach
                    3. Show step-by-step work with explanations
                    4. Verify the solution if possible
                    5. State the final answer prominently
                Maintain mathematical accuracy and clarity throughout.""",
                llm=llm,
            )
            print("Math solver agent created successfully")
            
        except Exception as e:
            print(f"Math agent creation failed: {e}")
            self.math_agent = None
        
        self.tools_initialized = True

    async def research_topic(self, topic: str) -> str:
        """Research mathematical context for the topic"""
        # Input validation
        is_valid, message = MathGuardrails.validate_math_input(topic)
        if not is_valid:
            return message
            
        await self._create_agents()
        
        print(f"Researching: {topic}")
        
        try:
            if self.research_agent:
                result = await self.research_agent.run(
                    f"Provide comprehensive mathematical research and context for: {topic}\n\n"
                    f"Include relevant definitions, formulas, theorems, and solution approaches."
                )
                return str(result)
        except Exception as e:
            print(f"Research agent error: {e}")
        
        # Fallback research using direct LLM
        try:
            fallback_prompt = f"""Research mathematical context for: {topic}
                            Provide:
                            1. Relevant mathematical concepts and definitions
                            2. Applicable formulas and theorems  
                            3. Common solution methods
                            4. Mathematical background and theory
                            Focus on information needed to solve this type of problem."""
            
            result = await llm.acomplete(fallback_prompt)
            return str(result)
            
        except Exception as e:
            print(f"Fallback research error: {e}")
            return f"I'll solve this mathematical problem using fundamental principles."

    async def solve_problem(self, topic: str, research_context: str) -> str:
        """Solve the mathematical problem step by step"""
        # Input validation
        is_valid, message = MathGuardrails.validate_math_input(topic)
        if not is_valid:
            return message
            
        await self._create_agents()
        
        print(f"Solving: {topic}")
        
        try:
            if self.math_agent:
                prompt = (
                    f"RESEARCH CONTEXT:\n{research_context}\n\n"
                    f"PROBLEM TO SOLVE:\n{topic}\n\n"
                    f"Provide a complete step-by-step solution with clear explanations for each step."
                )
                result = await self.math_agent.run(prompt)
                solution = str(result)
                
                # Apply math formatting
                formatted_solution = MathGuardrails.format_math_output(solution)
                return formatted_solution
                
        except Exception as e:
            print(f"Math agent error: {e}")
        
        # Fallback to direct LLM
        try:
            fallback_prompt = f"""Solve this mathematical problem step by step:
            PROBLEM: {topic}

            CONTEXT: {research_context}

            Requirements:
            - Provide complete step-by-step solution
            - Explain mathematical reasoning for each step
            - Show all calculations clearly
            - Use proper mathematical notation
            - State the final answer prominently

            Solve systematically and thoroughly."""
            
            result = await llm.acomplete(fallback_prompt)
            solution = str(result)
            formatted_solution = MathGuardrails.format_math_output(solution)
            return formatted_solution
            
        except Exception as e:
            return f"I encountered an error solving this problem: {str(e)}"

    async def improve_solution(self, original_solution: str, feedback: str, topic: str) -> str:
        """Improve solution based on human feedback"""
        await self._create_agents()
        
        print(f"Improving solution based on feedback")
        
        try:
            if self.math_agent:
                prompt = f"""ORIGINAL PROBLEM: {topic}
                ORIGINAL SOLUTION:
                {original_solution}

                HUMAN FEEDBACK: {feedback}

                Based on the feedback, improve the solution by:
                - Addressing specific concerns or questions
                - Providing additional explanations where needed
                - Correcting any errors identified
                - Adding more detail or alternative approaches
                - Maintaining mathematical accuracy
                Provide an improved, comprehensive solution that addresses the feedback."""
                
                result = await self.math_agent.run(prompt)
                improved = str(result)
                formatted_improved = MathGuardrails.format_math_output(improved)
                return formatted_improved
                
        except Exception as e:
            print(f"Math agent improvement error: {e}")
        
        # Fallback improvement
        try:
            fallback_prompt = f"""Improve this mathematical solution based on feedback:
            PROBLEM: {topic}
            ORIGINAL SOLUTION: {original_solution}
            FEEDBACK: {feedback}

            Provide an improved solution that addresses the feedback while maintaining accuracy."""
            
            result = await llm.acomplete(fallback_prompt)
            improved = str(result)
            formatted_improved = MathGuardrails.format_math_output(improved)
            return formatted_improved
            
        except Exception as e:
            return f"I encountered an error improving the solution: {str(e)}"

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
        agent = MathAgent()
        
        sessions[session_id] = {
            "agent": agent,
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
        # Input validation error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f" Error starting chat: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def process_math_question(session_id: str, topic: str):
    """Process a math question: research -> solve -> await feedback"""
    try:
        if session_id not in sessions:
            return
            
        sess = sessions[session_id]
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

@app.get("/chat/{session_id}")
async def get_chat(session_id: str):
    """Get current session state"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
        
    sess = sessions[session_id]
    
    return {
        "session_id": session_id,
        "status": sess["status"],
        "messages": sess["messages"],
        "waiting": {"key": "approval"} if sess.get("waiting_for_approval") else None
    }

@app.post("/human-input")
async def human_input(req: HumanInputRequest):
    """Process human feedback and improve solution"""
    if req.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = sessions[req.session_id]
    
    if not sess.get("waiting_for_approval"):
        raise HTTPException(status_code=400, detail="Session is not waiting for feedback")

    try:
        print(f"Processing feedback for {req.session_id}: {req.feedback[:100]}...")
        
        sess["messages"].append({
            "role": "user",
            "content": req.feedback
        })
        
        feedback_lower = req.feedback.strip().lower()
        current_solution = sess.get("current_solution", "")
        
        if feedback_lower in ["approve", "approved", "yes", "ok", "looks good", "good", "correct", "accept"]:
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