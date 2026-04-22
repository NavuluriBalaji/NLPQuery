# NLPQuery (AskYourDatabase Clone)

NLPQuery is a privacy-first, locally-hostable application that allows you to chat directly with your PostgreSQL database. Instead of writing complex SQL manually, you can ask questions in natural language, and NLPQuery will intelligently analyze your database schema, determine the intent, select the necessary tables, prune irrelevant columns, and generate the perfect SQL query.

![AskYourDatabase Style UI](./static/style.css) 

## 🚀 Features

- **Dynamic Database Connections**: Connect to any PostgreSQL database directly from the beautiful, modern UI.
- **Multi-Agent Pipeline**: 
  - **Intent Agent**: Understands what the user is asking and targets the right domain/workspace.
  - **Table Agent**: Uses vector similarity (RAG) to find and select the most relevant tables for the query.
  - **Column Prune Agent**: Strips out irrelevant columns from the selected schemas to save LLM context tokens and improve accuracy.
  - **SQL Generator Agent**: Takes the optimized schema and few-shot examples to write highly accurate, production-ready SQL.
- **Local & Cloud LLMs**: 
  - Full support for local, privacy-first execution. Highly optimized and tested with **NVIDIA** lightweight models (e.g. `nvidia/nemotron-3-nano-4b`) via **LM Studio**.
  - Drop-in support for cloud models like **OpenAI (GPT-4o)** or **Anthropic (Claude-3.5)**.
- **RAG & Vector Stores**: Features a local, in-memory vector store fallback with native support for `pgvector`.
- **Beautiful UI**: An AskYourDatabase-inspired frontend built with Vanilla HTML/JS/CSS featuring smooth transitions, dynamic chatting, and responsive feedback.

## 🛠️ Architecture

NLPQuery uses the **Open/Closed Principle** heavily. You can easily plug in new vector stores (Pinecone, Qdrant) or new LLM providers (Google Gemini) by simply adding a new class without modifying the core orchestrator.

- **Frontend**: Lightweight HTML/CSS/JS interface.
- **Backend**: FastAPI (`app.py`) for serving the API.
- **Core Orchestrator**: Custom-built Python agentic framework inside `/querygpt`.

## 🧠 How It Works (The Pipeline Flow)

When a user asks a question, it goes through a strict, multi-step pipeline to ensure high accuracy and low token usage:

1. **Input**: User asks a question (e.g., *"Show me the top 5 customers by revenue"*).
2. **Intent Analysis**: The **Intent Agent** analyzes the question to understand the goal and determines which logical workspace (e.g., *Sales*, *Users*) to search in.
3. **RAG Retrieval**: The **Vector Store** performs a semantic search across your entire database schema and fetches the Top 5 most relevant tables. If it can't find anything in the targeted workspace, it gracefully falls back to a global database search.
4. **Table Selection**: The **Table Agent** reviews the retrieved tables and strictly selects only the ones actually required to answer the question.
5. **Schema Pruning**: To save tokens and avoid confusing the AI, the **Column Prune Agent** strips out irrelevant columns from the selected tables, leaving only what is absolutely necessary.
6. **Generation**: The **SQL Generator Agent** combines the heavily optimized schema with retrieved few-shot examples to write a precise, executable PostgreSQL query.

## 📦 Installation & Setup

1. **Clone the repository**
2. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: This project requires Python 3.10+ and the latest versions of `openai` and `httpx`)*

3. **Configure the Environment:**
   Create a `.env` file in the root directory:
   ```env
   # Set your preferred LLM provider (openai, anthropic, lmstudio, ollama)
   LLM_PROVIDER=lmstudio
   
   # If using Cloud LLMs, provide the keys:
   # OPENAI_API_KEY=sk-...
   # ANTHROPIC_API_KEY=sk-...
   
   # Vector Store (memory or pgvector)
   VECTOR_STORE=memory
   ```

4. **Run the Application:**
   ```bash
   python app.py
   ```
5. **Connect**: Open your browser to `http://127.0.0.1:8000`. Enter your PostgreSQL credentials in the left sidebar and start chatting with your database!

## 🤖 Using Local NVIDIA Models (LM Studio)

NLPQuery is designed to work completely offline, and is specifically optimized to perform complex SQL generation on consumer-grade hardware using NVIDIA's edge models!

- **LM Studio (Recommended)**: 
  1. Download and open [LM Studio](https://lmstudio.ai/).
  2. Search for and download an NVIDIA model, such as `nvidia/nemotron-3-nano-4b`.
  3. Start the Local Server on port `312`.
  4. NLPQuery automatically handles the specific prompt formatting and strict JSON disables required to keep these smaller NVIDIA models from crashing, ensuring high-quality, fully local SQL generation.
- **Ollama**: Run your model and the application will hook into `http://localhost:11434/v1`.

## 📄 License
MIT License
