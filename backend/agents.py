from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.gemini import Gemini
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
import re, os
from kb_tool import rag_tool


llm = Gemini(model="gemini-2.5-flash",api_key=os.getenv('GEMINI_API_KEY'))

# ---- I/O Guardrails ----
class MathGuardrails:
        
    MATH_KEYWORDS = [
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
        
    MATH_PATTERNS = [
        re.compile(r'[+\-*/=<>≤≥≠±∞]'),
        re.compile(r'[xy]\^?\d*'),
        re.compile(r'\d+[xy]'),
        re.compile(r'sin|cos|tan|log|ln|sqrt', re.IGNORECASE),
        re.compile(r'∫|∑|∏|∂|∆|π|θ|α|β|γ|λ|μ|σ'),
        re.compile(r'\b\d+\.\d+\b'),
        re.compile(r'\b\d+/\d+\b'),
        re.compile(r'\([^)]*[xy][^)]*\)'),
        re.compile(r'[a-z]\s*²|[a-z]\s*³'),
    ]

    NON_MATH_INDICATORS = [
        'write a story', 'tell me a joke', 'weather', 'news', 'recipe',
        'movie', 'book recommendation', 'health advice', 'relationship',
        'what is your opinion', 'how do you feel', 'personal experience'
    ]
    EDGE_CASE_WORDS = ['find', 'what is', 'how much', 'calculate']
    
    REPLACEMENTS = [
        (re.compile(r'(\d+)/(\d+)'), r'\\frac{\1}{\2}'),
        (re.compile(r'\^(\d+)'), r'^{\1}'),
        (re.compile(r'\^([a-zA-Z]+)'), r'^{\1}'),
        (re.compile(r'sqrt\(([^)]+)\)'), r'\\sqrt{\1}'),
        (re.compile(r'√\(([^)]+)\)'), r'\\sqrt{\1}'),
        (re.compile(r'\bpi\b', re.IGNORECASE), 'π'),
        (re.compile(r'\binfinity\b', re.IGNORECASE), '∞'),
        (re.compile(r'\btheta\b', re.IGNORECASE), 'θ'),
        (re.compile(r'\balpha\b', re.IGNORECASE), 'α'),
        (re.compile(r'\bbeta\b', re.IGNORECASE), 'β'),
        (re.compile(r'\bgamma\b', re.IGNORECASE), 'γ'),
        (re.compile(r'd/dx'), r'\\frac{d}{dx}'),
        (re.compile(r'\bintegral\b', re.IGNORECASE), '∫'),
    ]

    @staticmethod
    def validate_math_input(topic: str) -> tuple[bool, str]:
            """Validate if the input is maths related"""
            if not topic or not topic.strip():
                return False, "Please provide a mathematical question or problem."
            
            topic_lower = topic.lower().strip()
            
            # Quick reject for non-math content
            if any(indicator in topic_lower for indicator in MathGuardrails.NON_MATH_INDICATORS):
                return False, "I'm designed specifically for mathematical problems. Please ask a maths related question."
            
            # Check for math keywords (fast set lookup)
            has_math_keywords = any(keyword in topic_lower for keyword in MathGuardrails.MATH_KEYWORDS)
            
            # Check for math patterns (use compiled patterns)
            has_math_patterns = any(pattern.search(topic_lower) for pattern in MathGuardrails.MATH_PATTERNS)
            
            if has_math_keywords or has_math_patterns:
                return True, "Valid mathematical input"
            
            # Edge case check
            if any(word in topic_lower for word in MathGuardrails.EDGE_CASE_WORDS):
                return True, "Potentially maths problem, so proceed with caution"
            
            return False, "This doesn't appear to be a mathematical question. I specialize in solving math problems. Please ask about equations, calculations, or mathematical concepts."

    @staticmethod
    def format_math_output(text: str) -> str:
        """Enhanced mathematical formatting for better display"""
        if not text:
            return text
        
        formatted = text
        for pattern, replacement in MathGuardrails.REPLACEMENTS:
            formatted = pattern.sub(replacement, formatted)
        
        return formatted

# def validate_math_topic(cls, v):
#     is_valid, message = MathGuardrails.validate_math_input(v)
#     if not is_valid:
#         raise ValueError(message)
#     return v.strip()

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
    
class MathematicalAgent:
    def __init__(self):
        self.research_agent = None
        self.math_agent = None
        self.tools_initialized = False
        
    async def _create_agents(self):
        if self.tools_initialized:
            return

        try:
            mcp_tools = await get_mcp_tools()
            tools = [rag_tool] + mcp_tools
            print(f"Total tools available: {len(tools)}")

            # Research Agent
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
            # MathAgent
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
                llm=llm
            )
            print("Math agent created successfully")    
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
        
        if self.research_agent:
            try:
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
        
        if self.math_agent:
            try:
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

        if self.math_agent:
            try:
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
                return MathGuardrails.format_math_output(str(result))
                
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