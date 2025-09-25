import faiss, os
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import VectorStoreIndex, StorageContext,Settings, load_index_from_storage
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.readers.file import PyMuPDFReader

# ollama_embedding = OllamaEmbedding(
#     model_name="nomic-embed-text:latest",
#     base_url="http://localhost:11434",
# )

# Settings.embed_model = ollama_embedding

# def encode_db():
#     base_dir = os.path.dirname(os.path.abspath(__file__))
#     pdf_path = os.path.join(base_dir,"../data/mathbook.pdf")

#     documents = PyMuPDFReader().load(pdf_path)
    
#     dimensions = 768
#     faiss_index = faiss.IndexFlatL2(dimensions)
#     vector_store = FaissVectorStore(faiss_index=faiss_index)
#     storage_context = StorageContext.from_defaults(vector_store=vector_store)
#     vector_store.persist(persist_path="./VectorDB")

#     # Store in Faiss
#     index = VectorStoreIndex.from_documents(documents,storage_context=storage_context)
#     index.storage_context.persist(persist_dir="./VectorDB")
    # return index

storage_context = StorageContext.from_defaults(persist_dir="./VectorDB")
index = load_index_from_storage(storage_context=storage_context)
query_engine = index.as_query_engine()

rag_tool = QueryEngineTool(
    query_engine=query_engine,
    metadata=ToolMetadata(
        name="RAG-Tool",
        description="RAG tool for answering mathematical questions from the pdf vector store."
    ),
)