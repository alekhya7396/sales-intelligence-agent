# Sales Intelligence Agent

A mini AI-assisted business intelligence app for asking natural-language questions about sales transactions. It uses Streamlit for the UI, FastAPI for the API, SQLite for storage, Pandas for CSV cleaning, and controlled SQL templates for deterministic analytics.

## Features

- Total revenue and transaction count
- Top products by revenue
- Monthly revenue trend
- Top region by revenue
- Revenue change between two named months
- Category and sales-channel breakdowns
- Data-quality reporting, API validation, safe read-only query helper, and automated tests
- Optional LLM intent classification using the OpenAI API; deterministic rules work without an API key

## Revenue and data-quality rules

Revenue is calculated as `Quantity * Unit_price - Discount_amount`. Only rows marked `Completed` are included. Rows are excluded from analytics when required fields are missing/invalid, the date cannot be parsed, quantity is zero or negative, price/discount/revenue is negative, or status is not `Completed`.

For the supplied dataset, expected excluded rows are:
- `TXN0033`: status is `Returned`
- `TXN0034`: quantity is zero
- `TXN0051`: unit price is missing

The original source records are retained in the SQLite `sales` table, with an `is_valid_sale` flag and a calculated `revenue` field. Invalid rows remain inspectable but do not contribute to analytics.

## Run locally

Requires Python 3.10 or later.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Run the Streamlit UI:

```bash
streamlit run app.py
```

Run the FastAPI backend in a separate terminal:

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to try the API. The `POST /ask` request body looks like:

```json
{"question": "Which product generated the highest revenue?"}
```

The database is initialized from `data/sales.csv` when the API starts and when the Streamlit app loads. For a demo, keep the CSV at that path.

## Optional LLM

Set `OPENAI_API_KEY` in your environment to enable LLM-based question classification. The LLM is not allowed to create or execute SQL. It returns only an intent label and month names; application-owned SQL templates calculate the results. Without a key or if the LLM call fails, deterministic intent matching is used.

Windows PowerShell example:

```powershell
$env:OPENAI_API_KEY="your-key-here"
streamlit run app.py
```

Never commit real API keys to Git.

## Tests

```bash
pytest -q
```

Tests cover total revenue, top product, monthly trend, top region, month comparison, unsupported questions, and blank input.

## Architecture

```text
CSV -> Pandas validation/cleaning -> SQLite sales table
                                      ^
User question -> Streamlit UI -> question interpreter -> approved SQL template
                                      |                       |
                                      +------ FastAPI /ask ---+
                                                              v
                                                structured answer + figures
```

## AI tools and development notes (edit this to reflect your actual work)

- AI tools used: [add the tools you actually used, e.g. ChatGPT for design/debugging and code review].
- How AI was used: [describe the parts where AI helped; do not claim work you did not perform].
- Problems encountered: CSV date parsing, missing numeric fields, ambiguous month comparisons, and avoiding untrusted SQL execution are useful issues to discuss if you encountered them while testing.
- Debugging: run `pytest -q`, inspect `/data-quality`, and test example questions in the UI/API.
- Improvements with another day: add a proper LLM tool-calling layer, month/year disambiguation, authentication, database migrations, richer visualizations, CI, and deployment.

## Known limitations

- The example dataset contains one year (2026); month comparisons compare month names within the dataset's year.
- The optional LLM requires an API key and network access. The rule-based fallback supports common question phrasings, not arbitrary language.
- The app is a demo, not a production deployment. It has no authentication, role-based access, or multi-user database management.
- The read-only SQL helper rejects common dangerous tokens; the application itself uses fixed SQL templates. For production, use a read-only database account and stronger SQL parsing/allow-listing.
