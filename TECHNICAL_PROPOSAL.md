# CafeNorte — AWS Production Data Platform Proposal

## Executive Summary

CafeNorte can consolidate its POS, ecommerce, inventory, product, cost, and exchange-rate data into a lightweight AWS analytical platform that provides consistent sales, inventory, and margin reporting.

Given approximately 40 stores and moderate batch volumes, I recommend a serverless, pay-per-use architecture instead of a dedicated data warehouse or distributed processing platform. The design prioritizes low cost, data traceability, and the ability to scale as CafeNorte's requirements grow.

## Proposed AWS Architecture

```text
 POS / Ecommerce / Inventory / Reference Data
                       |
                       v
              +----------------+
              | Amazon S3      |
              | Raw Zone       |
              +-------+--------+
                      |
              EventBridge Schedule
                      |
                      v
              +----------------+
              | AWS Glue       |
              | Python ETL     |
              | Reconciliation |
              | Data Quality   |
              +-------+--------+
                      |
                      v
              +----------------+
              | Amazon S3      |
              | Curated Zone   |
              | Parquet        |
              +-------+--------+
                      |
             +--------+---------+
             |                  |
             v                  v
      Glue Data Catalog    Amazon Athena
                                |
                                v
                         BI / Reporting

 IAM: least-privilege access and security
 CloudWatch: logs, metrics and operational alerts
```

**Why this architecture:**

S3 provides low-cost durable storage and preserves raw data for reprocessing and auditability. The existing Python/pandas logic can be adapted to Glue Python Shell without introducing Spark at the current scale. Curated data is stored as Parquet to reduce Athena scans and cost. Athena provides serverless SQL analytics without the fixed infrastructure of a dedicated warehouse such as Redshift. Glue Spark or Redshift can be evaluated later if data volume, concurrency, or latency requirements increase.

## Estimated Monthly Cost

The initial estimate assumes approximately 40 stores, one daily batch, 30 ETL executions per month, approximately 10 minutes per execution, 20 GB of initial S3 storage, approximately 5 GB monthly storage growth, and moderate Athena usage.

| Service                    | Monthly estimate |
| -------------------------- | ---------------: |
| Amazon S3                  |              ~$1 |
| AWS Glue Python Shell      |              ~$5 |
| Glue Data Catalog          |              <$1 |
| Amazon Athena              |              ~$1 |
| Amazon EventBridge         |              <$1 |
| Amazon CloudWatch          |              ~$2 |
| Growth / usage contingency |             ~$10 |
| **Estimated total**        |   **~$20/month** |

This is a planning estimate rather than a fixed quote. Actual cost will depend on production data volume, execution duration, query patterns, retention, logging, and refresh frequency. Under these assumptions, the initial serverless platform is expected to remain well below CafeNorte's stated infrastructure budget of approximately $200/month, while preserving capacity for moderate growth and operational variability.

## Implementation Plan

**Phase 1 — Foundation & ingestion.** Configure S3 raw and curated zones, IAM access, encryption, and reliable ingestion of the production sources. Raw data remains unchanged so that datasets can be reprocessed when rules change or data issues are discovered.

**Phase 2 — Transformation & data quality.** Deploy normalization, product reconciliation, FX conversion, historical-cost assignment, sales/inventory modeling, and automated quality controls in AWS Glue. Missing inventory or cost information remains explicitly unknown instead of being converted to artificial zero values.

**Phase 3 — Analytics & business validation.** Register curated datasets in Glue Data Catalog and expose them through Athena. Validate with CafeNorte the approved definitions and results for inventory turnover, stockouts, monthly channel growth, and negative margins.

**Phase 4 — Operations & handover.** Automate execution through EventBridge and implement CloudWatch logging and alerts for job failures, missing sources, schema changes, and quality exceptions. Deliver operating documentation and a basic support/runbook process.

## Key Risks and Mitigations

The main risks are source schema changes, incomplete product mappings, and missing historical costs. Immutable raw storage, schema validation, quality alerts, and reconciliation coverage metrics reduce these risks. Unmatched products and unknown costs should remain explicitly identified rather than being silently discarded or converted to zero.

Processing time and AWS spend should also be monitored as transaction volume, store count, users, or refresh frequency grow. The architecture should scale only when measured requirements justify additional infrastructure.

## Assumptions and Open Questions

The estimate assumes daily batch processing, moderate growth, source availability through files or batch extracts, and that S3/Parquet with Athena satisfies the initial analytical SLA.

Before implementation, I would confirm:

* What refresh frequency and availability SLA are required?
* How will each production source be exposed: files, APIs, databases, SFTP, or third-party integrations?
* What are the approved business definitions of inventory turnover, stockout, revenue, and margin?
* Which system is the authoritative product master, and who owns POS/ERP/ecommerce mappings?
* Who owns remediation when mappings, costs, inventory snapshots, or exchange rates are incomplete?
* What retention, security, recovery, and 12–24 month growth requirements must the platform support?

These answers would be validated before finalizing the production scope, implementation schedule, and AWS cost commitment.
