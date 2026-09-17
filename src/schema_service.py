"""
Database schema discovery.

Uses SQLAlchemy's inspector so we never hand-maintain a copy of the
schema that can drift from reality. Restricted to ALLOWED_TABLES so the
LLM (and therefore the SQL it writes) never even learns that other
tables exist.
"""

from sqlalchemy import inspect
from src.database import engine

# Only these tables are ever exposed to the model. Extend this set
# deliberately -- never expose auth/credential/PII tables here.
ALLOWED_TABLES = {
    "customers",
    "categories",
    "products",
    "orders",
    "order_items",
}


def get_database_schema() -> dict:
    inspector = inspect(engine)

    schema = {}

    for table_name in inspector.get_table_names():
        if table_name not in ALLOWED_TABLES:
            continue

        columns = inspector.get_columns(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)

        schema[table_name] = {
            "columns": [
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": column["nullable"],
                }
                for column in columns
            ],
            "foreign_keys": foreign_keys,
        }

    return schema


def schema_to_text(schema: dict) -> str:
    output = []

    for table, metadata in schema.items():
        output.append(f"TABLE: {table}")

        for column in metadata["columns"]:
            output.append(f"- {column['name']}: {column['type']}")

        for fk in metadata["foreign_keys"]:
            output.append(
                f"FOREIGN KEY: "
                f"{fk['constrained_columns']} -> "
                f"{fk['referred_table']}.{fk['referred_columns']}"
            )

        output.append("")

    return "\n".join(output)
