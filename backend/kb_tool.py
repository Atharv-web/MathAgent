import os,requests
from pinecone import Pinecone
from llama_index.core.tools import FunctionTool

HF_API_KEY = os.getenv('HF_TOKEN')
HF_API_URL = "https://router.huggingface.co/hf-inference/models/intfloat/multilingual-e5-large/pipeline/feature-extraction"
HF_HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

def get_embeddings(query:str):
    payload = {"inputs": query}
    response = requests.post(HF_API_URL, headers=HF_HEADERS, json=payload)
    response.raise_for_status()
    embeddings = response.json()
    return embeddings[0] if isinstance(embeddings[0], list) else embeddings

def get_pinecone_index():
    pinecone_key = os.getenv("PINECONE_API_KEY")
    pinecone_client = Pinecone(api_key=pinecone_key)
    index = pinecone_client.Index("math-docs")
    return index

def retrieve_data_from_db(query):
    try:
        vectorized_query = get_embeddings(query)

        index = get_pinecone_index()
        namespace = "engg-math-1"
        search_result = index.query(
            namespace=namespace,
            vector=vectorized_query,
            top_k=3,
            include_metadata=True
        )
        
        return [res["metadata"]["text"] for res in search_result["matches"]]
    except Exception as e:
        print(f"Rag retrieval error -> {e}")
        return []

rag_tool = FunctionTool.from_defaults(
    fn=retrieve_data_from_db,
    name="rag_knowledge_search",
    description=(
        """Search the mathematical knowledge base for relevant information. Use this tool to find definitions, theorems, formulas, and examples
        related to mathematical concepts. Input should be a clear query about a mathematical topic or problem type. Returns the most relevant text chunks."""
    ),
)