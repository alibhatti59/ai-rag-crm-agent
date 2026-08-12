import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

# 1. Load all markdown docs from /docs
loader = DirectoryLoader("docs", glob="**/*.md", loader_cls=TextLoader)
documents = loader.load()

print(f"Loaded {len(documents)} documents")

# 2. Split into chunks
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
)
chunks = text_splitter.split_documents(documents)

print(f"Split into {len(chunks)} chunks")

# 3. Embed and store in ChromaDB
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="chroma_db",
)

vectorstore.persist()

print("✅ Knowledge base successfully embedded and saved to chroma_db/")