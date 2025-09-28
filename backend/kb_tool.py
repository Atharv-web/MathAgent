import os
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import VectorStoreIndex, StorageContext,load_index_from_storage,SimpleDirectoryReader
from llama_index.core.tools import QueryEngineTool, ToolMetadata

embedding_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

base_dir = os.path.dirname(os.path.abspath(__file__))

persist_dir_path = os.path.join(base_dir,"db","VectorStore")
pdf_path = os.path.join(base_dir,"data","mathbook.pdf")

def encode_db(db_path):
    documents= SimpleDirectoryReader(input_files=[db_path]).load_data()
    index = VectorStoreIndex.from_documents(documents,embed_model=embedding_model)
    index.storage_context.persist(persist_dir=persist_dir_path)
    return index

if os.path.exists(os.path.join(persist_dir_path,"docstore.json")):
    storage_context = StorageContext.from_defaults(persist_dir=persist_dir_path)
    index = load_index_from_storage(storage_context=storage_context)
else:
    index = encode_db(pdf_path)

queryEngine = index.as_query_engine()

rag_tool = QueryEngineTool(
    query_engine=queryEngine,
    metadata=ToolMetadata(
        name="RAG-Tool",
        description="RAG tool for answering mathematical questions from the pdf vector store."
    ),
)