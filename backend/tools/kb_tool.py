import faiss, os
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import VectorStoreIndex, StorageContext,Settings, load_index_from_storage
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.readers.file import PyMuPDFReader
from dotenv import load_dotenv
load_dotenv()

# ollama_embedding = OllamaEmbedding(
#     model_name="nomic-embed-text:latest",
#     base_url="http://localhost:11434",
# )

# Settings.embed_model = ollama_embedding

# base_dir = os.path.dirname(os.path.abspath(__file__))
# persist_dir = os.path.join(os.path.dirname(__file__), "db", "VectorDB")
# faiss_index_file = os.path.join(persist_dir, "faiss.index")

# def encode_db():
#     # pdf_path = os.path.join(base_dir,"../data/mathbook.pdf")
#     os.makedirs(persist_dir, exist_ok=True)
#     pdf_path = os.path.join(base_dir,"../data/mathbook.pdf")
#     documents = PyMuPDFReader().load(pdf_path)
    
#     dimensions = 768
#     faiss_index = faiss.IndexFlatL2(dimensions)
#     vector_store = FaissVectorStore(faiss_index=faiss_index)
#     storage_context = StorageContext.from_defaults(vector_store=vector_store)

#     # Store in Faiss
#     index = VectorStoreIndex.from_documents(documents,storage_context=storage_context)
#     vector_store.persist(persist_path=persist_dir)
#     index.storage_context.persist(persist_dir=persist_dir)
#     return index

# if os.path.exists(os.path.join(persist_dir,"docstore.json")):
#     storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
#     index = load_index_from_storage(storage_context=storage_context)
# else:
#     index = encode_db()

# queryEngine = index.as_query_engine

# rag_tool = QueryEngineTool(
#     query_engine=queryEngine,
#     metadata=ToolMetadata(
#         name="RAG-Tool",
#         description="RAG tool for answering mathematical questions from the pdf vector store."
#     ),
# )

storage_context = StorageContext.from_defaults(persist_dir="../VectorDB")
index = load_index_from_storage(storage_context=storage_context)
query_engine = index.as_query_engine()

rag_tool = QueryEngineTool(
    query_engine=query_engine,
    metadata=ToolMetadata(
        name="RAG-Tool",
        description="RAG tool for answering mathematical questions from the pdf vector store."
    ),
)