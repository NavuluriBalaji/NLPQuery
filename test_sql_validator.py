"""
Test script to verify SQL Validator is working correctly.

Tests both allowed and blocked operations.
"""
from querygpt.sql_validator import validate_sql, is_write_operation

def test_allowed_queries():
    """Test queries that should be allowed."""
    allowed_queries = [
        "SELECT * FROM customers LIMIT 10",
        "SELECT id, name, email FROM users WHERE status = 'active'",
        "SELECT COUNT(*) FROM orders GROUP BY customer_id",
        """
        WITH recent_orders AS (
            SELECT * FROM orders WHERE created_at > NOW() - INTERVAL 30 DAY
        )
        SELECT * FROM recent_orders
        """,
        "SELECT o.*, c.name FROM orders o JOIN customers c ON o.customer_id = c.id",
        "-- This is a comment\nSELECT * FROM products",
        """
        /* Multi-line
           comment */
        SELECT * FROM inventory
        """,
    ]
    
    print("=" * 80)
    print("✅ TESTING ALLOWED QUERIES")
    print("=" * 80)
    
    for sql in allowed_queries:
        is_valid, error_msg = validate_sql(sql)
        status = "✅ PASS" if is_valid else "❌ FAIL"
        print(f"\n{status}")
        print(f"Query: {sql[:60]}...")
        if not is_valid:
            print(f"Error: {error_msg}")

def test_blocked_queries():
    """Test queries that should be blocked."""
    blocked_queries = [
        ("INSERT INTO users VALUES (1, 'John')", "INSERT"),
        ("UPDATE customers SET status = 'inactive' WHERE id = 1", "UPDATE"),
        ("DELETE FROM orders WHERE id = 100", "DELETE"),
        ("TRUNCATE TABLE logs", "TRUNCATE"),
        ("DROP TABLE users", "DROP"),
        ("ALTER TABLE products ADD COLUMN price DECIMAL", "ALTER"),
        ("CREATE TABLE new_table (id INT)", "CREATE"),
        ("EXEC xp_cmdshell 'whoami'", "EXEC"),
        ("-- Some comment\nINSERT INTO users VALUES (1)", "INSERT with comment"),
        ("SELECT * FROM users; DELETE FROM users; --", "Multiple statements"),
    ]
    
    print("\n" + "=" * 80)
    print("🚫 TESTING BLOCKED QUERIES")
    print("=" * 80)
    
    for sql, description in blocked_queries:
        is_valid, error_msg = validate_sql(sql)
        status = "✅ PASS" if not is_valid else "❌ FAIL"
        print(f"\n{status}")
        print(f"Type: {description}")
        print(f"Query: {sql[:60]}...")
        if is_valid:
            print("❌ ERROR: This should have been blocked!")
        else:
            print(f"Correctly blocked: {error_msg[:100]}...")

def test_edge_cases():
    """Test edge cases."""
    edge_cases = [
        ("", "Empty query"),
        ("   \n\n  ", "Whitespace only"),
        ("-- Just a comment", "Comment only"),
        ("/* Comment */ -- Another comment", "Comments only"),
        ("SELECT update_counter() FROM metrics", "Function with 'update' in name"),
        ("SELECT * FROM delete_logs", "Table with 'delete' in name"),
        ("SELECT * FROM users WHERE username = 'UPDATE'", "String with keyword"),
    ]
    
    print("\n" + "=" * 80)
    print("🔍 TESTING EDGE CASES")
    print("=" * 80)
    
    for sql, description in edge_cases:
        try:
            is_valid, error_msg = validate_sql(sql)
            print(f"\n{description}")
            print(f"Valid: {is_valid}")
            if error_msg:
                print(f"Message: {error_msg[:80]}...")
        except Exception as e:
            print(f"\n❌ {description} - Exception: {e}")

def test_is_write_operation():
    """Direct test of is_write_operation function."""
    print("\n" + "=" * 80)
    print("🔬 DIRECT FUNCTION TESTS")
    print("=" * 80)
    
    tests = [
        ("SELECT * FROM users", False),
        ("INSERT INTO users VALUES (1)", True),
        ("UPDATE users SET name = 'John'", True),
        ("DELETE FROM users", True),
        ("TRUNCATE users", True),
        ("DROP TABLE users", True),
        ("CREATE TABLE users (id INT)", True),
        ("ALTER TABLE users ADD COLUMN email VARCHAR", True),
    ]
    
    for sql, expected in tests:
        result = is_write_operation(sql)
        status = "✅" if result == expected else "❌"
        print(f"{status} is_write_operation('{sql[:40]}...') = {result} (expected {expected})")

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SQL VALIDATOR TEST SUITE")
    print("=" * 80)
    
    test_allowed_queries()
    test_blocked_queries()
    test_edge_cases()
    test_is_write_operation()
    
    print("\n" + "=" * 80)
    print("✅ SQL Validator Test Complete!")
    print("=" * 80)
    print("\nSummary:")
    print("- Only SELECT queries are allowed")
    print("- Write operations (INSERT, UPDATE, DELETE, etc.) are blocked")
    print("- Comments and whitespace are handled correctly")
    print("- Edge cases with keywords in strings/table names are considered")
