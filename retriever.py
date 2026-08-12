import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()


def get_vector_retriever():
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("GEMINI_API_KEY"),
    )
    vectorstore = Chroma(
        persist_directory="chroma_db",
        embedding_function=embeddings,
    )
    return vectorstore.as_retriever(search_kwargs={"k": 3})


def get_bm25_retriever():
    loader = DirectoryLoader("docs", glob="**/*.md", loader_cls=TextLoader)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)

    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 3
    return bm25_retriever


def hybrid_search(query, vector_weight=0.6, bm25_weight=0.4, top_k=3):
    """Manual hybrid retrieval: runs both retrievers, merges and deduplicates results."""
    vector_retriever = get_vector_retriever()
    bm25_retriever = get_bm25_retriever()

    vector_results = vector_retriever.invoke(query)
    bm25_results = bm25_retriever.invoke(query)

    # Score each result by rank position (simple reciprocal rank fusion)
    scores = {}
    docs_by_content = {}

    for rank, doc in enumerate(vector_results):
        key = doc.page_content
        docs_by_content[key] = doc
        scores[key] = scores.get(key, 0) + vector_weight * (1 / (rank + 1))

    for rank, doc in enumerate(bm25_results):
        key = doc.page_content
        docs_by_content[key] = doc
        scores[key] = scores.get(key, 0) + bm25_weight * (1 / (rank + 1))

    # Sort by combined score, return top_k unique documents
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [docs_by_content[key] for key, _ in ranked[:top_k]]


# Quick test when run directly
if __name__ == "__main__":
    query = "What's your refund policy?"
    results = hybrid_search(query)

    print(f"\nQuery: {query}\n")
    for i, doc in enumerate(results, 1):
        print(f"--- Result {i} ---")
        print(doc.page_content[:200])
        print(f"Source: {doc.metadata.get('source', 'unknown')}\n")