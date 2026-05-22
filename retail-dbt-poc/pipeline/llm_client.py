"""
Ollama LLM client for dbt test generation.
Uses qwen2.5-coder:3b via local Ollama REST API.
"""

import json
from typing import Optional

import requests
import yaml


class OllamaClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        model: str = "qwen2.5-coder:3b",
    ):
        self.base_url = f"http://{host}:{port}"
        self.model = model

    def health(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str) -> str:
        """Call Ollama generate API. Returns raw text response."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 2048,
            },
        }
        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json().get("response", "")


def build_prompt(
    table_name: str, columns: list[dict], stats: dict, sample_rows: list[dict]
) -> str:
    """
    Build a prompt for dbt test generation.

    Args:
        table_name: PostgreSQL table name
        columns: list of {name, dataType, nullable}
        stats: dict of col_name -> {null_count, null_rate, distinct_count, uniqueness_score, zero_count, min_val, max_val, total_count}
        sample_rows: list of row dicts (up to 10)
    """
    # Build column info table
    col_lines = [
        "| column | type | nullable | null_rate | uniqueness | distinct | zero_count | min | max |",
        "|--------|------|----------|-----------|------------|----------|------------|-----|-----|",
    ]
    for col in columns:
        cname = col["name"]
        st = stats.get(cname, {})
        col_lines.append(
            f"| {cname} | {col['dataType']} | {col['nullable']} | "
            f"{st.get('null_rate', 0):.2%} | {st.get('uniqueness_score', 0):.4f} | "
            f"{st.get('distinct_count', '?')} | {st.get('zero_count', 'N/A')} | "
            f"{st.get('min_val', 'N/A')} | {st.get('max_val', 'N/A')} |"
        )

    # Build sample rows table
    if sample_rows:
        headers = list(sample_rows[0].keys())
        sample_header = "| " + " | ".join(str(h) for h in headers) + " |"
        sample_sep = "| " + " | ".join("---" for _ in headers) + " |"
        sample_data_lines = []
        for row in sample_rows[:10]:
            sample_data_lines.append(
                "| " + " | ".join(str(row.get(h, "")) for h in headers) + " |"
            )
        sample_table = "\n".join([sample_header, sample_sep] + sample_data_lines)
    else:
        sample_table = "(no sample rows)"

    prompt = f"""You are a dbt data quality expert. Generate a dbt schema.yml for the table below.

## Table: {table_name}

### Column Statistics:
{chr(10).join(col_lines)}

### Sample Rows (up to 10):
{sample_table}

## Instructions:
Generate a dbt schema.yml models section for table `stg_{table_name}`. Apply these rules:
1. Add `not_null` test for every column where null_rate is 0.0 and nullable is False
2. Add `unique` test for columns where uniqueness_score > 0.99 and the column name ends in '_id' or starts with 'id'
3. Add `accepted_values` test for columns with distinct count < 15 and non-numeric type — list the actual distinct values you see in sample rows
4. Add `dbt_utils.expression_is_true` test for numeric columns (amount, price, salary, quantity, balance, total, subtotal) that should be >= 0. Expression: "column_name >= 0"
5. Add `dbt_utils.expression_is_true` for rating columns: expression "rating >= 1 and rating <= 5"
6. Skip tests for columns with null_rate > 0 for not_null tests
7. For uniqueness: skip if uniqueness_score < 0.99

Output ONLY the YAML content below, starting with `models:`. No markdown fences, no explanation, no preamble.

Example output format:
models:
  - name: stg_{table_name}
    description: "Staging model for {table_name}"
    columns:
      - name: {table_name}_id
        description: "Primary key"
        tests:
          - unique
          - not_null
      - name: status
        tests:
          - not_null
          - accepted_values:
              values: ['active', 'inactive']
"""
    return prompt


def build_column_prompt(
    table: str,
    col: str,
    dtype: str,
    nullable: bool,
    stats: dict,
    is_primary_key: bool = False,
    is_foreign_key: bool = False,
    references=None,
    table_columns: list[dict] = None,
    samples: list = None,
) -> str:
    """
    Build per-column prompt for dbt-expectations + dbt-profiler test generation.
    Tests derive ONLY from stats/metrics — never from specific sample values.
    If samples provided, also requests data dictionary generation.
    """
    stats_json = json.dumps(stats or {}, default=str)
    table_cols_json = json.dumps(table_columns or [], default=str)

    has_samples = bool(samples)
    samples_section = (
        f"\nsample_values (use ONLY for data_dictionary — NOT for test conditions):\n{json.dumps(samples, default=str)}\n"
        if has_samples
        else ""
    )
    dict_key_doc = (
        '- "data_dictionary": object with "description" (semantic meaning, 1-2 sentences) '
        'and "value_semantics" (format/domain notes inferred from name, type, and samples)'
        if has_samples
        else '- "data_dictionary": null'
    )

    return f"""You are a dbt data-quality expert. Generate dbt-expectations tests for one column.

## Project packages in use
- **dbt_profiler** (data-mie/dbt_profiler): runs `dbt_profiler.profile('model_name')` on staging models
  to produce per-column metrics — not_null_proportion, distinct_proportion, is_unique, min, max, avg,
  std_deviation, median, distinct_count, null_count, row_count. Profiling is fully handled by this
  package; you do NOT need to generate any profiling SQL or profiling config.
- **dbt_expectations** (metaplane/dbt_expectations): the ONLY package to use for test generation.
  The column stats below come directly from dbt_profiler output.

## Column context
table: {table}
column: {col}
data_type: {dtype}
nullable: {nullable}
is_primary_key: {is_primary_key}
is_foreign_key: {is_foreign_key}
references: {references}
table_columns: {table_cols_json}

## Column statistics (source: dbt_profiler)
{stats_json}
{samples_section}
## Required output — valid JSON with exactly these keys:
- "tests": array of objects, each with:
  - "test": full dbt-expectations test name (e.g. "dbt_expectations.expect_column_values_to_not_be_null")
  - "config": dict of test parameters (empty dict {{}} if none needed)
  - "description": one line explaining why this test was chosen based on which metric triggered it
{dict_key_doc}
- "rationale": one sentence on overall test selection

## Strict rules
1. Base ALL tests on dbt_profiler metric values and column name/type semantics — NEVER on specific observed sample values
2. NEVER generate value-equality or value-in-list conditions derived from samples
3. Do NOT output profiling SQL, profiling config, or profiling metric lists — dbt_profiler handles that automatically
4. Use ONLY these dbt-expectations tests (pick applicable ones):
   - dbt_expectations.expect_column_values_to_not_be_null
     → when: not_null_proportion == 1.0 (or null_rate == 0) AND nullable is False
   - dbt_expectations.expect_column_values_to_be_unique
     → when: is_unique == True OR uniqueness_score > 0.99 (config: {{}})
   - dbt_expectations.expect_column_proportion_of_unique_values_to_be_between
     → when: 0.5 < uniqueness_score <= 0.99 (config: min_value=round-down-to-0.05)
   - dbt_expectations.expect_column_values_to_be_between
     → numeric cols only; min_value/max_value from dbt_profiler min/max with 10% outward buffer;
       force min_value=0 for amount/price/qty/balance/total columns
   - dbt_expectations.expect_column_mean_to_be_between
     → numeric metric cols (amount, price, salary, quantity, total, balance);
       derive bounds from avg ± 2*std_deviation when both are in stats
   - dbt_expectations.expect_column_stdev_to_be_between
     → numeric metric cols when std_deviation is available; config min_value=0
   - dbt_expectations.expect_column_values_to_match_regex
     → infer from column name: email→RFC5321, phone→digits+separators, postal_code→\\d{{5}}, date-string→ISO8601
   - dbt_expectations.expect_column_values_to_be_in_set
     → ONLY when distinct_count < 10 AND column name implies status/category/type/flag
       AND column is NOT a name/free-text/description column
     → infer the value set from column name semantics (e.g. status→['active','inactive','pending'])
       NOT from observed sample values
5. For primary keys: always add not_null + unique
6. For foreign keys: add not_null only; skip unique
7. Skip not_null if not_null_proportion < 1.0 (or null_rate > 0)
8. Skip unique if uniqueness_score < 0.99

Output ONLY the JSON object. No markdown fences, no explanation outside the JSON.
"""


def build_table_dict_prompt(
    table: str,
    columns: list[dict],
    samples_by_col: dict,
) -> str:
    """
    Build a single prompt to generate a data dictionary for ALL columns of a table at once.
    One LLM call per table → one JSON file, no cross-column bleeding.

    columns: list of {name, dtype, nullable, is_primary_key, is_foreign_key, references}
    samples_by_col: {col_name: [sample_val, ...]}  (may be empty per col)
    """
    col_lines = []
    for col in columns:
        name = col["name"]
        samples = samples_by_col.get(name, [])
        sample_str = ", ".join(str(v) for v in samples[:5]) if samples else "n/a"
        col_lines.append(
            f"  - name: {name}\n"
            f"    dtype: {col.get('dtype', col.get('data_type', 'unknown'))}\n"
            f"    nullable: {col.get('nullable', True)}\n"
            f"    is_primary_key: {col.get('is_primary_key', False)}\n"
            f"    is_foreign_key: {col.get('is_foreign_key', False)}\n"
            f"    references: {col.get('references')}\n"
            f"    sample_values: [{sample_str}]"
        )
    col_block = "\n".join(col_lines)

    return f"""You are a data dictionary expert. Generate a concise data dictionary for the table below.

## Table: {table}

### Columns:
{col_block}

## Output format
Return a JSON object with exactly this structure:
{{
  "table": "{table}",
  "description": "one sentence describing what this table represents",
  "columns": {{
    "<column_name>": {{
      "description": "what this specific column represents (1 sentence, no other columns mentioned)",
      "semantics": "value format/domain: e.g. 'ISO 8601 timestamp', 'US phone number', 'enum: active|inactive|pending', 'auto-increment PK', 'free text name'"
    }}
  }}
}}

## Rules
1. Each column entry MUST describe ONLY that column — do not mention other columns
2. Derive description from column name, dtype, nullable, PK/FK flags, and sample values
3. For FK columns: note what entity it references (from the references field)
4. For enum-like columns (low distinct_count, status/type/tier names): list inferred values in semantics
5. Do NOT invent data that contradicts sample values or dtype
6. Output ONLY the JSON object — no markdown fences, no explanation

Output ONLY the JSON object.
"""


def _clean_json_escapes(text: str) -> str:
    """
    Fix common LLM JSON errors: unescaped backslashes in string values
    (e.g. regex patterns like \\d{5} that LLMs emit unescaped).
    Only fixes inside JSON string values, not structural characters.
    """
    import re
    # Replace lone backslashes not followed by valid JSON escape chars
    # Valid: \" \\ \/ \b \f \n \r \t \uXXXX
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def parse_column_output(raw: str) -> Optional[dict]:
    """
    Parse JSON from per-column LLM response.
    Strips markdown fences and fixes invalid backslash escapes.
    Returns dict or None.
    """
    import re
    text = raw.strip()

    # Strip markdown fences (handles ```json, ```yaml, ``` with optional trailing whitespace)
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        while lines and lines[-1].strip() in ("```", ""):
            lines.pop()
        text = "\n".join(lines).strip()

    # Try parse as-is, then with escape fix, then with regex extraction
    for candidate in [text, _clean_json_escapes(text)]:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Regex extract outermost JSON object
    m = re.search(r"(\{.*\})", text, re.S)
    if m:
        for candidate in [m.group(1), _clean_json_escapes(m.group(1))]:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    return None


def parse_yaml_output(raw: str) -> Optional[dict]:
    """
    Parse YAML from LLM response. Strips markdown fences if present.
    Returns parsed dict or None if parsing fails.
    """
    # Strip markdown code fences
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```yaml or ```) and last ```
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Find the models: section
    if "models:" not in text:
        # Try to find it
        idx = text.find("- name:")
        if idx > 0:
            text = "models:\n  " + text[idx:]

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as e:
        print(f"  Warning: YAML parse error: {e}")
        return None
