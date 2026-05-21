"""
Ollama LLM client for dbt test generation.
Uses qwen2.5-coder:3b via local Ollama REST API.
"""

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
