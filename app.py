import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Try importing pipeline
try:
    from querygpt.factory import build_pipeline
    from querygpt.config import config
    from querygpt.models import QueryGPTRequest
    from querygpt.sql_validator import validate_sql
    pipeline = build_pipeline(config)
    
    if config.vector_store.backend == "memory":
        try:
            from main import demo_seed
            demo_seed(pipeline)
            logging.info("Seeded in-memory vector store with demo data.")
        except Exception as e:
            logging.warning(f"Could not seed demo data: {e}")
            
except Exception as e:
    pipeline = None
    logging.warning(f"Pipeline could not be built: {e}. Using mocked responses.")

app = FastAPI(title="QueryGPT UI")

connected_db_name = None

class ConnectDBRequest(BaseModel):
    host: str
    port: int
    name: str
    user: str
    password: str

class QueryRequest(BaseModel):
    question: str
    workspace: str | None = None

class QueryResponse(BaseModel):
    question: str
    enhanced_question: str | None = None
    matched_workspaces: list[str] = []
    selected_tables: list[str] = []
    generated_sql: str | None = None
    explanation: str | None = None
    error: str | None = None

@app.get("/api/status")
def get_status():
    return {"connected_db": connected_db_name}

@app.post("/api/connect_db")
def connect_db(req: ConnectDBRequest):
    global connected_db_name
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Backend pipeline is not initialized.")
    try:
        from querygpt.config import DatabaseConfig
        from querygpt.db.postgres import PostgresConnector
        from querygpt.db.schema_loader import SchemaLoader
        
        db_cfg = DatabaseConfig(
            host=req.host,
            port=req.port,
            name=req.name,
            user=req.user,
            password=req.password
        )
        connector = PostgresConnector(db_cfg)
        connector.connect()
        loader = SchemaLoader(connector)
        
        # Load tables from ALL available schemas
        all_tables = []
        schemas = connector.list_schemas()
        for schema_name in schemas:
            tables = loader.load_all_tables(schema_name)
            all_tables.extend(tables)
        
        # Add to pipeline
        pipeline.index_tables_batch(all_tables)
        
        connected_db_name = req.name
        return {"status": "success", "tables_loaded": len(all_tables), "db_name": req.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    if pipeline is None:
        # Mock response for UI testing
        return QueryResponse(
            question=req.question,
            enhanced_question=f"Enhanced: {req.question}",
            matched_workspaces=[req.workspace or "sales"],
            selected_tables=["public.orders", "public.customers"],
            generated_sql="SELECT * FROM public.orders LIMIT 10;\n-- Note: This is a mock response because the backend pipeline is missing.",
            explanation="The backend factory/pipeline files are currently incomplete. Once restored, this UI will serve actual LLM-generated SQL!"
        )
    
    try:
        from querygpt.models import QueryGPTRequest
        gpt_req = QueryGPTRequest(question=req.question, workspace_hint=req.workspace)
        resp = pipeline.run(gpt_req)
        
        # Secondary validation layer – validate generated SQL
        if resp.generated_sql:
            is_valid, error_msg = validate_sql(resp.generated_sql)
            if not is_valid:
                return QueryResponse(
                    question=resp.question,
                    enhanced_question=resp.enhanced_question,
                    matched_workspaces=resp.matched_workspaces,
                    selected_tables=resp.selected_tables,
                    generated_sql=None,
                    explanation=None,
                    error=error_msg
                )
        
        return QueryResponse(
            question=resp.question,
            enhanced_question=resp.enhanced_question,
            matched_workspaces=resp.matched_workspaces,
            selected_tables=resp.selected_tables,
            generated_sql=resp.generated_sql,
            explanation=resp.explanation,
            error=resp.error
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files for the frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    print("Starting QueryGPT UI Server at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
