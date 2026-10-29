"""Validate LLM-generated SQL before it is executed.

Checks, in order:
  1. The text parses as SQLite SQL.
  2. It is exactly one statement.
  3. The statement is a SELECT (CTEs and UNIONs of SELECTs are allowed).
  4. It contains no write/DDL nodes anywhere in the tree.
  5. It only reads from known tables.
A LIMIT is added if the query has none.
"""
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ALLOWED_TABLES = {"matches", "deliveries"}
DEFAULT_LIMIT = 1000

_FORBIDDEN_NODES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop,
    exp.Alter, exp.TruncateTable, exp.Command, exp.Pragma, exp.Attach,
    exp.Detach, exp.Transaction, exp.Commit, exp.Rollback, exp.Use,
)


class UnsafeSQLError(ValueError):
    """Raised when generated SQL fails validation."""


def validate_sql(sql: str, default_limit: int = DEFAULT_LIMIT) -> str:
    """Return the validated SQL (with a LIMIT added if missing) or raise UnsafeSQLError."""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise UnsafeSQLError("Empty query.")

    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except ParseError as e:
        raise UnsafeSQLError(f"Could not parse SQL: {e}") from e

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise UnsafeSQLError("Exactly one SQL statement is allowed.")
    tree = statements[0]

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise UnsafeSQLError("Only SELECT queries are allowed.")

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise UnsafeSQLError(f"Forbidden operation: {type(node).__name__}.")

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name not in ALLOWED_TABLES and name not in cte_names:
            raise UnsafeSQLError(f"Unknown or disallowed table: {table.name}.")

    if tree.args.get("limit") is None:
        tree = tree.limit(default_limit)

    return tree.sql(dialect="sqlite")
