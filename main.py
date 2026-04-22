"""
QueryGPT CLI entry point.

Usage:
    # Index schemas from the DB, then ask a question
    python main.py --index --workspace sales
    python main.py --question "How many orders were placed last week?"

    # Interactive REPL
    python main.py --interactive
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from querygpt.config import config
from querygpt.factory import build_pipeline
from querygpt.models import QueryGPTRequest, SQLSample, TableSchema, ColumnInfo

logging.basicConfig(
    level=getattr(logging, config.log_level, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("querygpt.main")


def demo_seed(pipeline) -> None:
    """
    Seed the pipeline with a minimal demo schema + SQL samples.
    Replace with real tables from your DB using pipeline.index_tables_batch().
    """
    orders = TableSchema(
        table_name="orders",
        schema_name="public",
        description="Customer purchase orders",
        columns=[
            ColumnInfo(name="id",          data_type="BIGINT",    is_primary_key=True, nullable=False),
            ColumnInfo(name="customer_id", data_type="BIGINT",    nullable=False),
            ColumnInfo(name="status",      data_type="VARCHAR",   nullable=False),
            ColumnInfo(name="total_amount",data_type="NUMERIC",   nullable=False),
            ColumnInfo(name="created_at",  data_type="TIMESTAMPTZ",nullable=False),
        ],
    )
    customers = TableSchema(
        table_name="customers",
        schema_name="public",
        description="Registered customer accounts",
        columns=[
            ColumnInfo(name="id",         data_type="BIGINT",  is_primary_key=True, nullable=False),
            ColumnInfo(name="email",      data_type="VARCHAR", nullable=False),
            ColumnInfo(name="full_name",  data_type="VARCHAR", nullable=True),
            ColumnInfo(name="created_at", data_type="TIMESTAMPTZ", nullable=False),
            ColumnInfo(name="country",    data_type="VARCHAR", nullable=True),
        ],
    )
    products = TableSchema(
        table_name="products",
        schema_name="public",
        description="Product catalogue",
        columns=[
            ColumnInfo(name="id",       data_type="BIGINT",  is_primary_key=True, nullable=False),
            ColumnInfo(name="name",     data_type="VARCHAR", nullable=False),
            ColumnInfo(name="category", data_type="VARCHAR", nullable=True),
            ColumnInfo(name="price",    data_type="NUMERIC", nullable=False),
            ColumnInfo(name="stock",    data_type="INT",     nullable=False),
        ],
    )

    pipeline.index_tables_batch([orders, customers, products], workspace="sales")

    samples = [
        SQLSample(
            question="Total revenue for last month",
            sql="""
SELECT SUM(o.total_amount) AS total_revenue
FROM   public.orders o
WHERE  o.status = 'completed'
  AND  o.created_at >= date_trunc('month', NOW() - INTERVAL '1 month')
  AND  o.created_at <  date_trunc('month', NOW());
""".strip(),
            tables_used=["public.orders"],
            workspace="sales",
        ),
        SQLSample(
            question="Top 10 customers by order count in the last 90 days",
            sql="""
SELECT c.full_name, c.email, COUNT(o.id) AS order_count
FROM   public.customers c
JOIN   public.orders    o ON o.customer_id = c.id
WHERE  o.created_at >= NOW() - INTERVAL '90 days'
GROUP  BY c.id, c.full_name, c.email
ORDER  BY order_count DESC
LIMIT  10;
""".strip(),
            tables_used=["public.customers", "public.orders"],
            workspace="sales",
        ),
        SQLSample(
            question="Number of new signups per country this year",
            sql="""
SELECT c.country, COUNT(*) AS signups
FROM   public.customers c
WHERE  c.created_at >= date_trunc('year', NOW())
GROUP  BY c.country
ORDER  BY signups DESC;
""".strip(),
            tables_used=["public.customers"],
            workspace="sales",
        ),
    ]
    pipeline.index_samples_batch(samples)
    print("✅  Demo schemas and samples indexed.")


def run_question(pipeline, question: str, workspace: str | None = None) -> None:
    req = QueryGPTRequest(question=question, workspace_hint=workspace)
    resp = pipeline.run(req)

    print("\n" + "═" * 70)
    print(f"❓  Question      : {resp.question}")
    print(f"🔍  Enhanced      : {resp.enhanced_question}")
    print(f"📂  Workspaces    : {resp.matched_workspaces}")
    print(f"📋  Tables used   : {resp.selected_tables}")
    print("─" * 70)
    if resp.generated_sql:
        print("🟢  Generated SQL :\n")
        print(resp.generated_sql)
        print("\n📝  Explanation   :")
        print(resp.explanation or "(none)")
    else:
        print(f"🔴  Error: {resp.error}")
    print("═" * 70 + "\n")


def interactive_mode(pipeline) -> None:
    print("\n🤖  QueryGPT – Interactive Mode  (type 'exit' to quit)\n")
    while True:
        try:
            question = input("Your question: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if question.lower() in {"exit", "quit", "q"}:
            break
        if not question:
            continue
        run_question(pipeline, question)


def index_from_db(pipeline, schema: str = "public", workspace: str | None = None) -> None:
    from querygpt.db.schema_loader import SchemaLoader
    from querygpt.db.postgres import PostgresConnector

    connector = PostgresConnector(config.db)
    connector.connect()
    loader = SchemaLoader(connector)
    tables = loader.load_all_tables(schema)
    pipeline.index_tables_batch(tables, workspace=workspace)
    connector.disconnect()
    print(f"✅  Indexed {len(tables)} tables from schema '{schema}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="QueryGPT – Natural Language to SQL")
    parser.add_argument("--question",    "-q", help="Natural language question")
    parser.add_argument("--workspace",   "-w", help="Workspace hint")
    parser.add_argument("--index",       "-i", action="store_true",
                        help="Index tables from PostgreSQL before querying")
    parser.add_argument("--db-schema",   default="public",
                        help="DB schema to index (default: public)")
    parser.add_argument("--demo",        action="store_true",
                        help="Seed demo tables and samples, then run an example query")
    parser.add_argument("--interactive", action="store_true",
                        help="Start interactive REPL mode")

    args = parser.parse_args()

    pipeline = build_pipeline(config)

    if args.index:
        index_from_db(pipeline, schema=args.db_schema, workspace=args.workspace)

    if args.demo:
        demo_seed(pipeline)
        run_question(pipeline, "How many orders were placed last week?", workspace="sales")
        run_question(pipeline, "Who are the top 5 customers by revenue this year?", workspace="sales")
        return

    if args.interactive:
        interactive_mode(pipeline)
        return

    if args.question:
        run_question(pipeline, args.question, workspace=args.workspace)
        return

    parser.print_help()


if __name__ == "__main__":
    main()