"""
Prompt templates for every LLM node in the agent graph.

Keeping these as plain module-level strings (rather than scattering
f-strings through nodes.py) makes it easy to iterate on wording
without touching orchestration code.
"""

INTENT_PROMPT = """
Classify this request.

Question:
{question}

Recent conversation context (may be empty):
{context}

Categories:

analytics:
Requires querying or analyzing the business database.

conversation:
A conversational follow-up that can be answered from the existing
conversation context alone (e.g. "explain that more simply",
"thanks", "what does AOV mean").

unsupported:
A request to modify data, change permissions, or something clearly
outside a read-only analytics assistant's scope (e.g. "delete all
orders", "update prices").

Set requires_sql to true only for the "analytics" category.
"""


SQL_GENERATION_PROMPT = """
You are a senior PostgreSQL analytics engineer.

Your task is to convert a user's business question into a safe,
accurate, read-only PostgreSQL query.

DATABASE SCHEMA:

{schema}

BUSINESS METRIC DEFINITIONS:

{metrics}

CONVERSATION CONTEXT (previous question/SQL/summary, may be empty):

{context}

RULES:

1. Generate PostgreSQL only.
2. Use only tables and columns contained in the provided schema.
3. Never invent tables or columns.
4. Only generate read-only analytical queries (SELECT, optionally with
   a WITH clause). Never INSERT, UPDATE, DELETE, DROP, ALTER,
   TRUNCATE, CREATE, GRANT, REVOKE, or COPY.
5. Prefer explicit JOIN conditions over implicit joins.
6. Use meaningful aliases.
7. Handle date filters carefully. When the user says a bare year like
   "2025", filter as:
   order_date >= '2025-01-01' AND order_date < '2026-01-01'
8. Use NULLIF when a division could divide by zero.
9. Do not select unnecessary columns.
10. Prefer aggregated results for analytical questions.
11. Unless the question requires row-level detail, return at most 100
    rows (use LIMIT).
12. Never use SELECT * unless truly necessary.
13. Do not wrap the SQL in markdown code fences. Return raw SQL only
    in the `sql` field.
14. Unless the question says otherwise, restrict to orders with
    status = 'Completed' for revenue/profit questions.

REVENUE CALCULATION RULES:

15. The orders table does not contain a total_amount, order_total,
    or revenue column.
16. Calculate revenue from order_items using:
    SUM(quantity * unit_price)
17. When calculating revenue by order date or order status, join the
    tables using:
    order_items.order_id = orders.order_id
18. Use orders.order_date for date filtering.
19. For revenue questions, use:
    FROM order_items AS oi
    JOIN orders AS o
      ON oi.order_id = o.order_id
20. Apply status = 'Completed' for revenue questions unless the user
    explicitly requests another status.
21. Do not deduct the discount unless the question specifically asks
    for discounted or net revenue. If discount is a percentage,
    calculate net revenue as:
    SUM(quantity * unit_price * (1 - discount / 100))

USER QUESTION:

{question}
"""
SQL_REPAIR_PROMPT = """
You are a senior PostgreSQL analytics engineer.

Your task is to repair an invalid SQL query and return a safe,
accurate, read-only PostgreSQL query.

DATABASE SCHEMA:

{schema}

USER QUESTION:

{question}

PREVIOUS SQL:

{sql}

DATABASE ERROR:

{error}

RULES:

1. Generate PostgreSQL only.
2. Use only tables and columns contained in the provided schema.
3. Never invent tables or columns.
4. Return only a read-only query using SELECT or WITH.
5. Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE,
   GRANT, REVOKE, or COPY.
6. Preserve the original business intent.
7. Use explicit JOIN conditions.
8. Use meaningful table aliases.
9. For revenue calculations, the orders table has no total_amount,
   order_total, or revenue column.
10. Calculate gross revenue using:
    SUM(order_items.quantity * order_items.unit_price)
11. Join order_items and orders using:
    order_items.order_id = orders.order_id
12. Use orders.order_date for date filtering.
13. For revenue/profit questions, filter:
    orders.status = 'Completed'
    unless the user explicitly requests another status.
14. Use NULLIF when division could result in division by zero.
15. Do not wrap the SQL in markdown code fences.
16. Return raw SQL only in the `sql` field.

Return the repaired SQL query and a short explanation.
"""

INSIGHT_PROMPT = """
You are a senior business data analyst.

Analyze the supplied SQL result for the business stakeholder.

USER QUESTION:
{question}

QUERY RESULT:
{result}

PRECOMPUTED NUMERIC SUMMARY:
{numeric_summary}

Return a concise, professional analysis.

Rules:
1. Use only values present in the query result or numeric summary.
2. Never invent causes, events, products, customers, or business context.
3. Separate observed facts from possible explanations.
4. If the result contains one KPI value, provide a direct answer and
   explain what the metric represents.
5. If the result contains multiple rows, identify important trends,
   highest and lowest values, changes, and meaningful comparisons.
6. For "why" questions, provide explanations only as hypotheses unless
   the data directly proves the cause.
7. Do not repeat the entire table.
8. Keep the summary concise.

Return these fields:

summary:
A direct executive-level answer to the user's question.

key_findings:
A short list of important numerical findings.

observed_facts:
Facts directly supported by the data.

possible_explanations:
Clearly labeled hypotheses, if supported by the available data.

follow_up_suggestions:
Useful next questions only when additional analysis is needed.
"""

INVESTIGATION_PROMPT = """
You are deciding whether an analytical answer needs additional data
before it can responsibly explain a "why" question.

ORIGINAL QUESTION:

{question}

ANALYSIS SO FAR:

{analysis}

If the analysis confirms a fact (e.g. a change happened) but does not
yet identify a contributing dimension (category, region, segment,
channel, etc.), set needs_more_data to true and propose ONE concrete
follow_up_question that would help (e.g. "Compare July and August
revenue by product category"). Otherwise set needs_more_data to false.
"""


CHART_PROMPT = """
You are selecting a visualization for a query result.

QUESTION:
{question}

AVAILABLE COLUMNS:
{columns}

SAMPLE DATA (first rows):
{sample_rows}

Rules:
- Time series (a date/month/year column plus a measure) -> line.
- Category comparison (a category column plus a measure) -> bar.
- Two continuous numeric measures -> scatter.
- A single KPI value (one row, one number) -> none.
- Too little data to visualize meaningfully -> none.
- Never reference a column that is not in AVAILABLE COLUMNS.
"""


CONVERSATION_PROMPT = """
You are a helpful business data analyst assistant continuing a
conversation. Answer the user's conversational message using ONLY the
prior conversation context below -- do not invent data.

CONVERSATION CONTEXT:
{context}

USER MESSAGE:
{question}
"""
