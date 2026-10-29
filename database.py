from pathlib import Path
import sqlite3
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "sales.csv"
DB_PATH = BASE_DIR / "sales.db"


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(csv_path: str | Path = CSV_PATH, db_path: str | Path = DB_PATH) -> dict:
    """Load source rows, preserve them, and mark valid completed sales for analytics."""
    df = pd.read_csv(csv_path, dtype={"Transaction_Id": "string"})
    required = ["Transaction_Id", "Order_date", "Product", "Category", "Region", "Sales_channel", "Quantity", "Unit_price", "Discount_amount", "Status"]
    missing_columns = sorted(set(required) - set(df.columns))
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_columns)}")

    df["Order_date"] = pd.to_datetime(df["Order_date"], format="%d-%m-%Y", errors="coerce")
    for col in ["Quantity", "Unit_price", "Discount_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Status"] = df["Status"].fillna("").astype(str).str.strip().str.title()
    df["Product"] = df["Product"].fillna("").astype(str).str.strip()
    df["Region"] = df["Region"].fillna("").astype(str).str.strip()
    df["revenue"] = (df["Quantity"] * df["Unit_price"] - df["Discount_amount"]).round(2)

    # Exclude rows with invalid identifiers/dates/numbers, non-completed status,
    # missing price, non-positive quantity, or negative computed revenue.
    valid = (
        df["Transaction_Id"].notna() & df["Transaction_Id"].astype(str).str.strip().ne("") &
        df["Order_date"].notna() & df["Product"].ne("") & df["Region"].ne("") &
        df["Quantity"].notna() & df["Unit_price"].notna() & df["Discount_amount"].notna() &
        df["Quantity"].gt(0) & df["Unit_price"].ge(0) & df["Discount_amount"].ge(0) &
        df["revenue"].ge(0) & df["Status"].eq("Completed")
    )
    df["is_valid_sale"] = valid.astype(int)
    df["Order_date"] = df["Order_date"].dt.strftime("%Y-%m-%d")
    df["revenue"] = df["revenue"].where(df["is_valid_sale"].eq(1), None)

    conn = get_connection(db_path)
    try:
        df.to_sql("sales", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(Order_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(Product)")
        conn.commit()
    finally:
        conn.close()

    return {
        "source_rows": int(len(df)),
        "valid_sales": int(valid.sum()),
        "excluded_rows": int((~valid).sum()),
        "excluded_transaction_ids": df.loc[~valid, "Transaction_Id"].astype(str).tolist(),
    }


def query_df(sql: str, params: tuple = (), db_path: str | Path = DB_PATH) -> pd.DataFrame:
    """Execute SELECT-only SQL. No arbitrary write queries are exposed."""
    normalized = sql.strip().lower()
    if not normalized.startswith("select") or any(token in normalized for token in [";", "--", "/*", "insert ", "update ", "delete ", "drop ", "alter ", "attach ", "pragma "]):
        raise ValueError("Only a single read-only SELECT query is allowed.")
    conn = get_connection(db_path)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
