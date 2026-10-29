"""Question interpretation and safe analytics. LLM output never supplies executable SQL."""
import os
import re
from datetime import datetime
from database import query_df

SUPPORTED_INTENTS = {
    "total_revenue", "top_product", "monthly_trend", "top_region", "month_comparison", "top_category", "channel_sales"
}


def _month_from_text(text: str):
    months = {m.lower(): i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1)}
    found = []
    for name, number in months.items():
        if re.search(rf"\b{name}\b", text, re.I):
            found.append((number, name.title()))
    return found


def interpret_question(question: str) -> dict:
    """Optionally use an LLM to classify intent; safe deterministic routing is the fallback."""
    question = question.strip()
    if not question:
        raise ValueError("Please enter a question.")

    # Optional LLM interpretation. It can only choose an intent and month names;
    # the SQL templates below remain application-owned and parameterized.
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "Classify a sales analytics question. Return JSON only: {\"intent\": one of [total_revenue,top_product,monthly_trend,top_region,month_comparison,top_category,channel_sales,unsupported], \"months\": [month names in order]. Never create SQL. Only answer from the provided sales analytics intent list."},
                    {"role": "user", "content": question},
                ],
            )
            import json
            parsed = json.loads(response.choices[0].message.content)
            intent = parsed.get("intent")
            if intent in SUPPORTED_INTENTS:
                return {"intent": intent, "months": parsed.get("months", [])[:2], "interpreter": "llm"}
            if intent == "unsupported":
                return {"intent": "unsupported", "months": [], "interpreter": "llm"}
        except Exception:
            # LLM unavailable/malformed response: fall back without failing the app.
            pass

    q = question.lower()
    months = _month_from_text(question)
    if any(w in q for w in ["compare", "change between", "change from", "difference between", "growth between", "increase between", "decrease between"]) and len(months) >= 2:
        return {"intent": "month_comparison", "months": [m[1] for m in sorted(months, key=lambda x: q.find(x[1].lower()))[:2]], "interpreter": "rules"}
    if "month" in q and any(w in q for w in ["trend", "monthly", "over time", "each month"]):
        return {"intent": "monthly_trend", "months": [], "interpreter": "rules"}
    if any(w in q for w in ["total revenue", "total sales", "overall revenue", "revenue overall"]):
        return {"intent": "total_revenue", "months": [], "interpreter": "rules"}
    if any(w in q for w in ["highest revenue", "top product", "best selling product", "most revenue"]):
        return {"intent": "top_product", "months": [], "interpreter": "rules"}
    if any(w in q for w in ["region", "territory"]) and any(w in q for w in ["highest", "top", "most", "best", "sales", "revenue"]):
        return {"intent": "top_region", "months": [], "interpreter": "rules"}
    if "categor" in q and any(w in q for w in ["highest", "top", "most", "sales", "revenue"]):
        return {"intent": "top_category", "months": [], "interpreter": "rules"}
    if any(w in q for w in ["channel", "online vs retail", "sales channel"]):
        return {"intent": "channel_sales", "months": [], "interpreter": "rules"}
    return {"intent": "unsupported", "months": [], "interpreter": "rules"}


def answer_question(question: str) -> dict:
    parsed = interpret_question(question)
    intent = parsed["intent"]
    if intent == "unsupported":
        return {"ok": False, "answer": "I couldn't match that to a supported sales question. Try total revenue, top product, monthly trend, top region, month comparison, category sales, or sales channel.", "intent": intent, "data": [], "sql": None, "interpreter": parsed["interpreter"]}

    base = "WHERE is_valid_sale = 1"
    if intent == "total_revenue":
        sql = f"SELECT ROUND(SUM(revenue), 2) AS total_revenue, COUNT(*) AS valid_transactions, SUM(Quantity) AS total_quantity FROM sales WHERE is_valid_sale = 1"
        data = query_df(sql).to_dict(orient="records")
        row = data[0]
        answer = f"Total revenue is ₹{row['total_revenue']:,.2f} across {row['valid_transactions']} valid completed transactions."
    elif intent == "top_product":
        sql = f"SELECT Product, ROUND(SUM(revenue), 2) AS total_revenue, SUM(Quantity) AS total_quantity, COUNT(*) AS transactions FROM sales {base} GROUP BY Product ORDER BY total_revenue DESC LIMIT 5"
        data = query_df(sql).to_dict(orient="records")
        answer = f"{data[0]['Product']} generated the highest revenue: ₹{data[0]['total_revenue']:,.2f}."
    elif intent == "monthly_trend":
        sql = f"SELECT strftime('%Y-%m', Order_date) AS month, ROUND(SUM(revenue), 2) AS revenue, COUNT(*) AS transactions FROM sales {base} GROUP BY month ORDER BY month"
        data = query_df(sql).to_dict(orient="records")
        answer = "Here is the monthly revenue trend for valid completed transactions."
    elif intent == "top_region":
        sql = f"SELECT Region, ROUND(SUM(revenue), 2) AS total_revenue, SUM(Quantity) AS total_quantity, COUNT(*) AS transactions FROM sales {base} GROUP BY Region ORDER BY total_revenue DESC"
        data = query_df(sql).to_dict(orient="records")
        answer = f"{data[0]['Region']} generated the highest sales revenue: ₹{data[0]['total_revenue']:,.2f}."
    elif intent == "month_comparison":
        names = parsed.get("months", [])
        if len(names) < 2:
            return {"ok": False, "answer": "Please name two months, for example: How did revenue change between March and April?", "intent": intent, "data": [], "sql": None, "interpreter": parsed["interpreter"]}
        def month_num(name):
            try: return datetime.strptime(name[:3].title(), "%b").month
            except ValueError: return None
        nums = [month_num(n) for n in names]
        if any(n is None for n in nums):
            return {"ok": False, "answer": "I couldn't identify both months. Please use month names such as March and April.", "intent": intent, "data": [], "sql": None, "interpreter": parsed["interpreter"]}
        sql = "SELECT strftime('%Y-%m', Order_date) AS month, ROUND(SUM(revenue), 2) AS revenue FROM sales WHERE is_valid_sale = 1 AND CAST(strftime('%m', Order_date) AS INTEGER) IN (?, ?) GROUP BY month ORDER BY month"
        data = query_df(sql, (nums[0], nums[1])).to_dict(orient="records")
        # Dataset has one year; ensure the requested months both exist and compare by month number.
        by_month = {int(row["month"].split("-")[1]): row["revenue"] for row in data}
        if nums[0] not in by_month or nums[1] not in by_month:
            return {"ok": False, "answer": "I couldn't find data for both requested months in the dataset.", "intent": intent, "data": data, "sql": sql, "interpreter": parsed["interpreter"]}
        first, second = by_month[nums[0]], by_month[nums[1]]
        change = second - first
        pct = (change / first * 100) if first else None
        direction = "increased" if change > 0 else "decreased" if change < 0 else "did not change"
        pct_text = f" ({pct:+.2f}%)" if pct is not None else ""
        answer = f"Revenue {direction} from {names[0]} (₹{first:,.2f}) to {names[1]} (₹{second:,.2f}) by ₹{abs(change):,.2f}{pct_text}."
        data = [{"month": names[0], "revenue": first}, {"month": names[1], "revenue": second}, {"change": round(change, 2), "percentage_change": round(pct, 2) if pct is not None else None}]
    elif intent == "top_category":
        sql = f"SELECT Category, ROUND(SUM(revenue), 2) AS total_revenue, SUM(Quantity) AS total_quantity FROM sales {base} GROUP BY Category ORDER BY total_revenue DESC"
        data = query_df(sql).to_dict(orient="records")
        answer = f"{data[0]['Category']} generated the highest category revenue: ₹{data[0]['total_revenue']:,.2f}."
    else:  # channel_sales
        sql = f"SELECT Sales_channel, ROUND(SUM(revenue), 2) AS total_revenue, SUM(Quantity) AS total_quantity, COUNT(*) AS transactions FROM sales {base} GROUP BY Sales_channel ORDER BY total_revenue DESC"
        data = query_df(sql).to_dict(orient="records")
        answer = "Here is the revenue breakdown by sales channel."

    return {"ok": True, "answer": answer, "intent": intent, "data": data, "sql": sql, "interpreter": parsed["interpreter"]}
