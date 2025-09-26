import faiss,os
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, StorageContext,Settings, load_index_from_storage
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.readers.file import PyMuPDFReader

embedding_model = HuggingFaceEmbedding(model="nomic-ai/nomic-embed-text-v1")
Settings.embed_model = embedding_model

base_dir = os.path.dirname(os.path.abspath(__file__))

persist_dir_path = os.path.join(base_dir,"db","VectorStore")
pdf_path = os.path.join(base_dir,"..","data","mathbook.pdf")

def encode_db(db_path):
    documents = PyMuPDFReader().load(db_path)
    
    dimensions = 768
    faiss_index = faiss.IndexFlatL2(dimensions)
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Store in Faiss
    index = VectorStoreIndex.from_documents(documents,storage_context=storage_context)
    vector_store.persist(persist_path=persist_dir_path)
    index.storage_context.persist(persist_dir=persist_dir_path)
    return index

if os.path.exists(os.path.join(persist_dir_path,"docstore.json")):
    storage_context = StorageContext.from_defaults(persist_dir=persist_dir_path)
    index = load_index_from_storage(storage_context=storage_context)
else:
    index = encode_db(pdf_path)

queryEngine = index.as_query_engine

rag_tool = QueryEngineTool(
    query_engine=queryEngine,
    metadata=ToolMetadata(
        name="RAG-Tool",
        description="RAG tool for answering mathematical questions from the pdf vector store."
    ),
)