# Math Agent

An intelligent mathematical problem-solving assistant powered by Gemini, designed to solve, and refine solutions through interactive feedback.

## Overview
Math Agent is a multi agent system that tackles mathematical problems systematically:

1. **Research** - Leverages web search and knowledge bases for relevant mathematical insights
2. **Solve** - Produces detailed, step by step solutions with clear explanations
3. **Refine** - Enhances solutions based on user input and feedback

Built with FastAPI, React, and integrated with Gemini models for advanced reasoning.

## Key Features

- **Research-enhanced solutions** using (RAG) and real time web search (MCP based tool)
- **Step-by-step breakdowns** with precise mathematical notation
- **Human-in-the-loop refinement** for iterative improvements
- **Input validation** to focus on mathematical queries
- **LaTeX support** for professional rendering of equations

## Tech Stack

**Backend**
- FastAPI
- LlamaIndex (for agent orchestration)
- Gemini model (for LLMs)
- Pinecone (vector database)
- Tavily (web search integration)
- MCP (Model Context Protocol)

**Frontend**
- React
- MathJax (for LaTeX rendering)

## Installation

### Prerequisites

- Python 3.9+
- Node.js 16+
- API keys for: Gemini, Tavily, HuggingFace, Pinecone

### Backend

```bash
cd backend
# Install dependencies
pip install -r requirements.txt
# Start server
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend/math-agent
# Install dependencies
npm install
# Start the app
npm start
```
