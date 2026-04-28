"""
Test script to demonstrate keyword extraction from PostgreSQL schemas.

Usage:
    python test_keyword_extraction.py
"""
from querygpt.models import TableSchema, ColumnInfo
from querygpt.keyword_extractor import extract_keywords, extract_keywords_batch

# Example 1: E-commerce orders table
orders_table = TableSchema(
    table_name="customer_orders",
    schema_name="public",
    description="Customer purchase orders and transactions",
    columns=[
        ColumnInfo(name="id", data_type="BIGINT", is_primary_key=True, nullable=False),
        ColumnInfo(name="customer_id", data_type="BIGINT", nullable=False),
        ColumnInfo(name="order_date", data_type="TIMESTAMPTZ", nullable=False),
        ColumnInfo(name="total_amount", data_type="NUMERIC", nullable=False),
        ColumnInfo(name="invoice_number", data_type="VARCHAR", nullable=True),
        ColumnInfo(name="payment_status", data_type="VARCHAR", nullable=False),
        ColumnInfo(name="created_at", data_type="TIMESTAMPTZ", nullable=False),
    ],
)

# Example 2: Inventory management
inventory_table = TableSchema(
    table_name="warehouse_stock",
    schema_name="public",
    description="Warehouse inventory and stock levels",
    columns=[
        ColumnInfo(name="id", data_type="BIGINT", is_primary_key=True, nullable=False),
        ColumnInfo(name="product_id", data_type="BIGINT", nullable=False),
        ColumnInfo(name="warehouse_location", data_type="VARCHAR", nullable=False),
        ColumnInfo(name="stock_quantity", data_type="INT", nullable=False),
        ColumnInfo(name="reorder_level", data_type="INT", nullable=False),
        ColumnInfo(name="last_updated", data_type="TIMESTAMPTZ", nullable=False),
    ],
)

# Example 3: User authentication
users_table = TableSchema(
    table_name="user_accounts",
    schema_name="public",
    description="User profiles and authentication records",
    columns=[
        ColumnInfo(name="id", data_type="UUID", is_primary_key=True, nullable=False),
        ColumnInfo(name="email", data_type="VARCHAR", nullable=False),
        ColumnInfo(name="password_hash", data_type="VARCHAR", nullable=False),
        ColumnInfo(name="full_name", data_type="VARCHAR", nullable=True),
        ColumnInfo(name="account_created", data_type="TIMESTAMPTZ", nullable=False),
        ColumnInfo(name="last_login", data_type="TIMESTAMPTZ", nullable=True),
        ColumnInfo(name="user_role", data_type="VARCHAR", nullable=False),
    ],
)

# Example 4: Analytics/metrics
metrics_table = TableSchema(
    table_name="daily_metrics",
    schema_name="analytics",
    description="Daily KPI and funnel metrics",
    columns=[
        ColumnInfo(name="date", data_type="DATE", is_primary_key=True, nullable=False),
        ColumnInfo(name="conversion_rate", data_type="NUMERIC", nullable=False),
        ColumnInfo(name="kpi_value", data_type="NUMERIC", nullable=False),
        ColumnInfo(name="funnel_step", data_type="VARCHAR", nullable=False),
        ColumnInfo(name="total_revenue", data_type="NUMERIC", nullable=False),
    ],
)

def main():
    tables = [orders_table, inventory_table, users_table, metrics_table]
    
    print("=" * 80)
    print("KEYWORD EXTRACTION TEST – Dynamic Database Schema Analysis")
    print("=" * 80)
    
    # Test individual extraction
    print("\n📊 INDIVIDUAL TABLE ANALYSIS:\n")
    for table in tables:
        result = extract_keywords(table)
        print(f"\n🔹 Table: {table.full_name}")
        print(f"   Description: {table.description}")
        print(f"   Extracted Keywords: {result['table_keywords']}")
        print(f"   Domain Keywords: {result['domain_keywords']}")
        print(f"   Suggested Workspaces: {result['suggested_workspaces']}")
    
    # Test batch extraction
    print("\n\n" + "=" * 80)
    print("📦 BATCH EXTRACTION RESULTS:\n")
    batch_results = extract_keywords_batch(tables)
    for table_name, keywords in batch_results.items():
        print(f"\n{table_name}:")
        print(f"  → Workspaces: {keywords['suggested_workspaces']}")
    
    print("\n" + "=" * 80)
    print("\n✅ Keyword extraction test completed!")
    print("\nHow it works:")
    print("  1. Splits table/column names (snake_case, camelCase)")
    print("  2. Removes DB prefixes (tbl_, dim_, fact_, stg_)")
    print("  3. Matches domain keywords (sales, inventory, users, analytics)")
    print("  4. Suggests workspaces dynamically based on extracted keywords")
    print("\nThis eliminates the need for hardcoded workspace assignments! 🎉")

if __name__ == "__main__":
    main()
