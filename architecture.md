# Architecture and design notes

1. **Ingestion:** Pandas loads `data/sales.csv`, parses dates in `DD-MM-YYYY`, coerces numeric fields, and calculates transaction revenue.
2. **Data quality:** Each source row is retained with an `is_valid_sale` flag. Analytics include only valid completed transactions. Missing price, zero quantity, and returned orders are excluded and reported.
3. **Storage:** SQLite stores the transactions in `sales`. Indexes are created on order date and product.
4. **Question interpretation:** An optional LLM classifies the question into a small supported intent list. Without an API key, deterministic rules interpret common phrasings.
5. **Query execution:** The application selects fixed, parameterized SQL templates based on the approved intent. The LLM never writes SQL. The database helper allows only a single read-only `SELECT` query.
6. **Response:** The backend returns JSON with `ok`, `answer`, `intent`, `data`, `sql`, and `interpreter`. Streamlit displays the answer, supporting table, and charts where appropriate.

## Why not unrestricted text-to-SQL?

An LLM-generated query can be syntactically wrong, use the wrong field, or attempt unsafe operations. This demo uses LLM classification rather than executable SQL generation. This keeps calculations deterministic and narrows the query surface area.
