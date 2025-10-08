from llama_index.core.node_parser import SentenceSplitter
import os,requests,uuid
from pinecone import Pinecone
from llama_index.core import SimpleDirectoryReader
from dotenv import load_dotenv
load_dotenv()

base_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(base_dir,"data","mathbook.pdf")

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-large")

def encode_db(db_path):
    formatted_records = []
    splitter = SentenceSplitter(chunk_size=1000,chunk_overlap=200)
    documents= SimpleDirectoryReader(input_files=[db_path]).load_data()

    chunks = splitter.get_nodes_from_documents(documents,show_progress=True)
    for i,chunk in enumerate(chunks):
        text = chunk.get_content()
        embeddings = model.encode(text,normalize_embeddings=True)
        record = {
            "id": f"chunk-{i}-{uuid.uuid4()}",
            "values": embeddings.tolist(),
            "metadata": {"text":text}
        }
        formatted_records.append(record)

    return formatted_records

def add_db_records(records):
    index_name,namespace = "math-docs","engg-math-1"
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_client = Pinecone(api_key = pinecone_api_key)
    index= pinecone_client.Index(index_name)
    batch_size=80
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        index.upsert(vectors=batch, namespace=namespace)

records = encode_db(pdf_path)
add_db_records(records)