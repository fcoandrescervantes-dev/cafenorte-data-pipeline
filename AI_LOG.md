# AI Usage Log

## 1. AI Tools Used

I used ChatGPT as an AI assistant during the development of this challenge.

- **Tool:** ChatGPT
- **Model:** GPT-5.6 Sol
- **Main uses:** implementation guidance, code review, debugging support, test design, documentation review, and repository preparation.
- **Development environment:** Visual Studio Code / PowerShell with Python 3.11.
- **Version control:** Git and GitHub.

I did not use autonomous agents or MCP servers to directly modify the repository or execute the pipeline on my behalf. I executed the commands locally, inspected the intermediate results, reviewed the proposed changes, and validated the implementation before continuing.

## 2. Workflow

I used ChatGPT primarily as an iterative development and review assistant rather than asking it to generate the entire solution in a single prompt.

My workflow was:

1. Inspect the source data and repository structure.
2. Implement one pipeline layer at a time: ingestion, normalization, reconciliation, analytical modeling, and business analytics.
3. Run the proposed code locally and inspect actual row counts, schemas, missing values, mappings, and business results.
4. When a result failed or looked inconsistent, investigate the underlying data before changing the implementation.
5. Add automated tests after the core behavior had been validated manually.
6. Run the complete test suite and pipeline repeatedly after significant changes.
7. Create a clean Python environment from `requirements.txt` and rerun the full test suite and pipeline to verify reproducibility.
8. Review the Git-tracked files, ignored files, repository archive, and source code for credentials, local paths, TODOs, and temporary artifacts before publishing the repository.

I intentionally worked incrementally because a pipeline that executes successfully can still produce incorrect business results. I therefore treated AI suggestions as proposals that required validation rather than as authoritative answers.

At the end of the implementation, the project had 45 automated tests passing, and I also validated the pipeline from a newly created virtual environment using only the dependencies declared in `requirements.txt`.

## 3. Key Prompts and Decisions


The following examples represent three important ways in which I used AI during the challenge. I did not automatically accept the generated suggestions; I executed the proposed steps locally and validated the results against the actual data and repository before continuing.

### Prompt 1 — Step-by-step pipeline implementation

**Prompt**

> "para el paso 5, estoy udando VS Code, pude realizar el paso 5.1 de crear la carpeta "cafenorte-data-pipeline " dime como realizar los demas pasos que me pides si utilizo la terminal de VS Code, damelo paso por paso"

**AI response (summary)**

ChatGPT adapted the implementation instructions to my development environment and proposed continuing the challenge incrementally rather than generating the complete project at once.

It also established a roadmap covering data profiling, business rules, analytical modeling, project structure, ingestion, normalization, SKU/currency/cost reconciliation, fact tables, business analytics, testing, documentation, AWS architecture, and interview preparation.

**What I did**

I followed the incremental approach and executed the commands locally from the VS Code PowerShell terminal. After each relevant step, I returned the actual command output to ChatGPT and used the results to decide whether it was safe to continue.

I inspected source row counts, schemas, normalized values, product mappings, missing data, historical costs, analytical results, and test results throughout the implementation.

**Why**

Working incrementally made failures easier to isolate and prevented me from treating a successful execution as proof that the business logic was correct. It also allowed me to understand the implementation as it evolved instead of accepting a complete AI-generated solution without reviewing its intermediate assumptions.

### Prompt 2 — Debugging an incorrect AI-generated assumption

**Prompt**

> "obtuve un error en 9.19 y 9.20 y no pude continuar"

I included the runtime error produced by `calculate_negative_margin_products`:

> `KeyError: 'sku_pos'`

**AI response (summary)**

The implementation being tested assumed that `sku_pos` was already present in `fact_sales`. After I reported the failure, ChatGPT suggested inspecting the actual persisted schema before modifying the calculation further.

**What I did**

I inspected the columns of `fact_sales.parquet` directly and confirmed that the table contained `product_key`, `sku_erp`, `product_name`, and `category`, but did not contain `sku_pos`.

Instead of creating an artificial column or removing the required identifier from the report, I changed the negative-margin analysis so that it also receives `dim_product` and obtains the appropriate product attributes through `product_key`.

I then reran the calculation and validated the result:

* 80 unique negative-margin product/store combinations;
* 2 affected products;
* 40 affected stores;
* 0 non-negative margins in the result;
* 0 missing margins;
* 0 missing stores or cities;
* 0 duplicate product/store combinations.

**Why**

The original assumption was structurally plausible but did not match the analytical model that had actually been persisted. I therefore rejected that assumption and used the real schema as the source of truth.

This was an important example of why I did not consider AI-generated code correct simply because it looked reasonable.

### Prompt 3 — Validation and delivery preparation

**Prompt / interaction**

After the core implementation was complete, I continued asking ChatGPT to guide me through the remaining validation and delivery steps one at a time. I provided the output of each command before asking to continue to the next step.

For example, after completing one of the validation stages, my follow-up messages consisted of the actual terminal results and requests to continue with the next numbered step.

**AI response (summary)**

ChatGPT guided me through a sequence of final checks rather than proposing additional functionality. These checks included expanding data-quality tests, running the complete test suite, reviewing dependencies, validating the project from a clean Python environment, checking Git-tracked and ignored files, inspecting the repository archive, searching for credentials and local paths, and preparing the repository for GitHub.

**What I did**

I executed these checks locally and used the actual results to determine whether to continue.

The final validation included:

* 45 automated tests covering ingestion, transformations, reconciliation, analytics, and data quality;
* successful end-to-end execution of `python -m src.pipeline`;
* creation of a separate clean virtual environment;
* installation using only `requirements.txt`;
* `pip check` with no broken requirements;
* all 45 tests passing again in the clean environment;
* successful pipeline execution in the clean environment;
* verification of the exact files included in a Git archive;
* confirmation that raw challenge data and generated outputs were ignored;
* searches for credentials, local machine paths, TODO/FIXME markers, and temporary artifacts;
* confirmation of a clean Git working tree before publishing to GitHub.

**Why**

I wanted to validate not only that the solution worked on my existing machine, but that the repository was reproducible and safe to deliver.

This step-by-step review also helped me avoid accepting AI guidance blindly: I supplied the result of each validation command back to the conversation before moving to the next check.


## 4. AI Failure / Incorrect Suggestion

The clearest AI failure occurred while implementing the negative-margin analysis.

The initial implementation of `calculate_negative_margin_products` assumed that `sku_pos` was already available in `fact_sales`. The assumption was reasonable from the perspective of the final report, which needed product identifiers, but it did not match the analytical model that had actually been persisted.

I detected the problem by executing the proposed calculation locally, which failed with:

```text
KeyError: 'sku_pos'
```

Instead of trying to suppress the error or adding a placeholder column, I inspected the actual schema of `fact_sales.parquet`. This confirmed that `sku_pos` was not present and that the relationship should instead be resolved through `product_key` and `dim_product`.

I corrected the design so that `calculate_negative_margin_products` explicitly receives the product dimension and obtains the required product attributes from it.

After the correction, I did not consider the issue resolved only because the function executed successfully. I validated that the result contained 80 unique product/store combinations, only negative margins, no missing margins, no missing store information, and no duplicate product/store combinations.

This case reinforced an important rule in my workflow: AI-generated code can be syntactically correct and conceptually plausible while still being inconsistent with the actual data model. The persisted schema and validated data were therefore treated as the source of truth.

## 5. Final Self-Critique

I consider the final technical decisions and the responsibility for the delivered solution to be mine, particularly the decision to preserve unknown inventory and cost values, validate reconciliation before using it for analytics, keep the implementation proportional to the challenge, and verify the business results instead of relying only on successful execution. ChatGPT contributed significantly as a development assistant by proposing implementation approaches, helping structure the work, suggesting code and tests, and supporting debugging and repository review. I did not accept those outputs as automatically correct: I validated them through direct schema inspection, row counts, reconciliation checks, business invariants, manual inspection of analytical results, 45 automated tests, repeated end-to-end pipeline executions, and a clean-environment installation using only `requirements.txt`. The main area I would improve with more time is adding stronger automated edge-case tests around time boundaries, exchange-rate availability, and incomplete product mappings, but I intentionally prioritized a small, understandable, reproducible pipeline over adding infrastructure or abstractions that were not necessary for the challenge.
