import faiss
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.readers.file import PyMuPDFReader
from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import OllamaEmbeddings
from llama_index.core import Settings
Settings.embed_model = OllamaEmbeddings(model="nomic-embed-text:latest")
documents = PyMuPDFReader().load(r'C:\Users\Atharva\Desktop\MathAgent\backend\data\mathbook.pdf')

def encode_db():
    dimensions = 768
    faiss_index = faiss.IndexFlatL2(dimensions)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    vector_store.persist(persist_path="../VectorDB")

    # Store in Faiss
    index = VectorStoreIndex.from_documents(documents,storage_context=storage_context)
    return index

index = encode_db()
query_engine = index.as_query_engine()

rag_tool = QueryEngineTool(
    query_engine=query_engine,
    metadata=ToolMetadata(
        name="RAG-Tool",
        description="RAG tool for answering mathematical questions from the pdf vector store."
    ),
)