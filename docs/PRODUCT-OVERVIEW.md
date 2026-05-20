# DataLens — Product Overview

## The Problem

Every large organisation has the same conversation. The finance team says revenue last quarter was $4.2 million. The sales team says $4.6 million. The marketing team says $4.1 million. Everyone is looking at data, and everyone has a different number.

This happens because data lives in silos. Finance pulls from the billing system. Sales pulls from the CRM. Marketing pulls from the ad platform. Each system was built at a different time, by a different team, with different rules about what counts as a "completed sale." The data is not wrong exactly — it is just fragmented and unchecked.

The result: analysts spend up to 80% of their time reconciling data instead of acting on it. Decisions are delayed. Trust in data erodes. When the CEO asks for a definitive number, nobody can confidently give one.

## What DataLens Does

DataLens is a data platform that connects all of a retail organisation's data sources into a single, governed, trustworthy layer — without physically moving the data.

Think of it like a universal translator sitting on top of all your existing systems. Instead of copying everything into one giant database (slow, expensive, and duplicated), DataLens asks each source for the information it needs and assembles the answer in real time. Each department continues to own its data. DataLens simply makes those sources speak the same language and applies consistent quality rules across all of them.

In plain terms, DataLens:

- **Connects** — links PostgreSQL databases, cloud storage, and analytical systems into a single query layer
- **Cleans** — applies standardised business rules (consistent date formats, currency codes, customer segments) so every team uses the same definitions
- **Checks** — runs automatic quality tests every day and flags anything that looks wrong before it reaches a dashboard
- **Shows** — presents all of this through a simple web interface where analysts can explore data, inspect quality scores, and trace where any number came from

## Who Uses It and How

| Role | What they see | What they can do |
|------|--------------|-----------------|
| Business Analyst | Dashboards, data tables, quality scores | Run ad-hoc queries, export clean data, investigate data quality alerts |
| Data Engineer | Pipeline status, test results, lineage diagrams | Monitor ETL jobs, fix failing data tests, add new data sources |
| Data Scientist | Profiled datasets with completeness statistics | Assess whether a dataset is fit for a machine learning model before spending weeks training on bad data |
| CTO / CDO | Executive health dashboard, SLA compliance | See at a glance which data assets are certified, which pipelines are healthy, and where gaps exist |

## Why It Matters in the Age of AI

Every organisation is investing in AI. Chatbots, demand forecasting, customer personalisation, fraud detection — the list grows every month.

Here is the uncomfortable truth: AI systems are only as good as the data they learn from. Feed a demand-forecasting model with sales figures that contain duplicates, missing store codes, and inconsistent date formats, and the model will learn those errors as facts. The predictions will be wrong in ways that are difficult to detect until the damage is done.

A widely cited analysis of AI project failures found that data quality problems — not model complexity or compute budget — are the leading cause of AI initiatives that fail to reach production. Teams spend months building a model, only to discover at the end that 30% of their training data was corrupted or mislabelled.

DataLens addresses this at the foundation:

- **Lineage** — every number can be traced back to its original source. When an AI model produces a surprising output, engineers can follow the data trail and find exactly where a problem was introduced.
- **Quality scores** — every data asset has a machine-readable quality score. A model training pipeline can check this score before starting a training run and refuse to proceed if the underlying data has failed its quality checks.
- **Catalogued context** — every table and column is documented with business definitions. Data scientists stop guessing what a field means and start spending that time on modelling.

DataLens does not build AI. It builds the foundation that AI needs to succeed.

## The Technology Stack (simplified)

```
Your existing databases
  (PostgreSQL, files, cloud storage)
           |
           v
    [ Trino Query Layer ]
    Reads all sources without
    copying the data
           |
           v
    [ dbt Transform Layer ]
    Applies business rules,
    cleans, joins, tests
           |
           v
  [ OpenMetadata Catalog ]
  Documents every asset,
  tracks quality scores,
  shows data lineage
           |
           v
  [ DataLens Web Interface ]
  Dashboards, quality reports,
  pipeline status — for everyone
```

Nothing leaves the organisation. Nothing is duplicated unnecessarily. The process runs on a schedule, so by the time analysts arrive in the morning, the previous night's data has already been cleaned, tested, and catalogued.

## What "Data Quality" Means in DataLens

Data quality in DataLens is not a feeling — it is a daily automated checklist.

Every night, the platform runs a series of tests against every core data table. These tests fall into two categories:

**Hard blocks (errors):** Tests that must pass for the pipeline to continue. Examples include confirming that every order has a customer attached, that dates fall within a plausible range (not 1970 or 2099), and that product references are valid. If these fail, the pipeline stops and an alert is raised. Analysts are never shown data that has failed a hard block.

**Soft warnings:** Statistical tests that flag unusual patterns without stopping the pipeline. Examples include checking that the average order value stays within a historically normal range, that the email address field is at least 95% populated, and that inventory records are not returning negative stock quantities. These appear as warnings in the quality dashboard so engineers can investigate before they become hard blocks.

When a test fails, the result is recorded in the OpenMetadata catalog with a timestamp, a description of what failed, and a count of affected rows. Nothing disappears silently. Every failure is visible, traceable, and actionable.

## The Foundation That Makes AI Trustworthy

DataLens is the foundation that makes your AI initiatives trustworthy. Clean, connected, catalogued, and continuously checked — it turns fragmented retail data into a reliable asset that analysts trust today and AI systems can learn from tomorrow.
