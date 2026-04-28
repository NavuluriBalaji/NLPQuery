# Text2Query (AskYourDatabase Clone)

Text2Query is a privacy-first, locally-hostable application that allows you to chat directly with your PostgreSQL database. Instead of writing complex SQL manually, you can ask questions in natural language, and NLPQuery will intelligently analyze your database schema, determine the intent, select the necessary tables, prune irrelevant columns, and generate the perfect SQL query.

## 🚀 Features

- **Dynamic Database Connections**: Connect to any PostgreSQL database directly from the beautiful, modern UI.
- **Multi-Agent Pipeline**: 
  - **Intent Agent**: Understands what the user is asking and targets the right domain/workspace.
  - **Table Agent**: Uses vector similarity (RAG) to find and select the most relevant tables for the query.
  - **Column Prune Agent**: Strips out irrelevant columns from the selected schemas to save LLM context tokens and improve accuracy.
  - **SQL Generator Agent**: Takes the optimized schema and few-shot examples to write highly accurate, production-ready SQL.
- **Read-Only Safe Mode**: Only SELECT queries are allowed. Write operations (INSERT, UPDATE, DELETE, TRUNCATE, DROP, ALTER, CREATE) are blocked for security. 🔒
- **Local & Cloud LLMs**: 
  - Full support for local, privacy-first execution. Highly optimized and tested with **NVIDIA** lightweight models (e.g. `nvidia/nemotron-3-nano-4b`) via **LM Studio**.
  - Drop-in support for cloud models like **OpenAI (GPT-4o)**, **Google Gemini**, or **Anthropic (Claude-3.5)**.
- **RAG & Vector Stores**: Features a local, in-memory vector store fallback with native support for `pgvector`.
- **Beautiful UI**: An AskYourDatabase-inspired frontend built with Vanilla HTML/JS/CSS featuring smooth transitions, dynamic chatting, and responsive feedback.
- **Dynamic Keyword Extraction**: Automatically learns table purposes from schema names and descriptions – no hardcoded workspace mappings needed. 🎯

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

## � Security – Read-Only Mode

Text2Query runs in **read-only mode by design**. Only SELECT queries are allowed. All write operations are blocked:

### Blocked Operations ❌
- `INSERT` – Cannot add new data
- `UPDATE` – Cannot modify existing data
- `DELETE` – Cannot remove data
- `TRUNCATE` – Cannot clear tables
- `DROP` – Cannot delete tables
- `ALTER` – Cannot modify schema
- `CREATE` – Cannot create new tables
- `EXEC` / `EXECUTE` – Cannot run procedures

### Why? 🛡️
- **Safety**: Prevents accidental data modifications
- **Auditability**: Only reads data, never writes
- **Peace of Mind**: Perfect for sharing with team members or AI models

### How It Works
1. **LLM Constraint**: The SQL Generator Agent has explicit instructions to ONLY generate SELECT queries
2. **Runtime Validation**: Generated SQL is validated before execution
3. **Dual Layer**: Both agent-level and API-level validation ensure no write operations slip through

### Allowed Operations ✅
- `SELECT` – Query data
- `WITH ... SELECT` – Use Common Table Expressions (CTEs)
- `JOIN` – Combine multiple tables
- `GROUP BY` / `HAVING` – Aggregate data
- `ORDER BY` – Sort results
- Date functions, aggregates, and any read-only SQL feature

**Example:** User asks *"Can you update the order status?"*  
Response: *"❌ Write operations are not allowed. Only SELECT queries are permitted. Would you like me to show you which orders have this status instead?"*

## �📦 Installation & Setup

1. **Clone the repository**
2. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: This project requires Python 3.10+ and the latest versions of dependencies)*

3. **Configure the Environment:**
   Create a `.env` file in the root directory (copy from `.env.example`):
   
   **Option A: Google Gemini (Free, Recommended)**
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_api_key_here
   LLM_MODEL_GEMINI=gemini-2.0-flash
   VECTOR_STORE=memory
   ```
   Get your free API key: https://ai.google.dev/
   
   **Option B: LM Studio (Local, Completely Private)**
   ```env
   LLM_PROVIDER=lmstudio
   LLM_MODEL_LMSTUDIO=nvidia/nemotron-3-nano-4b
   VECTOR_STORE=memory
   ```
   Download LM Studio: https://lmstudio.ai/
   
   **Option C: OpenAI (Cloud, Paid)**
   ```env
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   LLM_MODEL_OPENAI=gpt-4o-mini
   VECTOR_STORE=memory
   ```
   
   **Option D: Anthropic Claude (Cloud, Paid)**
   ```env
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   LLM_MODEL_ANTHROPIC=claude-3-5-haiku-20241022
   VECTOR_STORE=memory
   ```

4. **Run the Application:**
   ```bash
   python app.py
   ```
5. **Connect**: Open your browser to `http://127.0.0.1:8000`. Enter your PostgreSQL credentials in the left sidebar and start chatting with your database!

## 🤖 LLM Provider Guide

### **Google Gemini (Recommended for Most Users)**
- ✅ **Free tier**: 15 requests/minute for `gemini-2.0-flash`
- ✅ **No credit card required**
- ✅ **Fast and accurate** for SQL generation
- ✅ **Latest model**: Gemini 2.0 Flash

**Setup:**
1. Get free API key: https://ai.google.dev/
2. Set in `.env`:
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_key_here
   ```

### **LM Studio (Recommended for Privacy)**
- ✅ **Completely local and private** — no internet needed
- ✅ **Optimized NVIDIA models** (nemotron-3-nano-4b)
- ✅ **Works offline** on consumer hardware
- ⚠️ **Requires LM Studio running** on `http://localhost:1234`

**Setup:**
1. Download [LM Studio](https://lmstudio.ai/)
2. Search for and download `nvidia/nemotron-3-nano-4b`
3. Start Local Server (default: port 1234)
4. Set in `.env`:
   ```env
   LLM_PROVIDER=lmstudio
   LLM_MODEL_LMSTUDIO=nvidia/nemotron-3-nano-4b
   ```

### **OpenAI (Most Capable)**
- ✅ **Best performance** for complex SQL
- ✅ **Supports GPT-4o**
- ⚠️ **Requires paid API key**

**Setup:**
1. Get API key: https://platform.openai.com/api-keys
2. Set in `.env`:
   ```env
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   ```

### **Anthropic Claude (Privacy-Focused)**
- ✅ **Privacy-conscious design**
- ✅ **Long context window**
- ⚠️ **Requires paid API key**

**Setup:**
1. Get API key: https://console.anthropic.com/
2. Set in `.env`:
   ```env
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### **Ollama (Local, Any Model)**
- ✅ **Local execution**
- ✅ **Any Ollama model** (Llama, Mistral, etc.)
- ⚠️ **Requires Ollama installed** on `http://localhost:11434`

**Setup:**
1. Install [Ollama](https://ollama.ai/)
2. Run: `ollama pull llama3`
3. Set in `.env`:
   ```env
   LLM_PROVIDER=ollama
   LLM_MODEL_OLLAMA=llama3
   ```

## 📄 License
MIT License
