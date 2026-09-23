import pandas as pd


def get_reference_date(
    fact_sales: pd.DataFrame,
    fact_inventory: pd.DataFrame,
) -> pd.Timestamp:
    """
    Return the latest available date across the analytical datasets.
    This makes all reporting windows reproducible.
    """
    max_sales_date = fact_sales["transaction_date"].max()
    max_inventory_date = fact_inventory["snapshot_date"].max()

    return max(max_sales_date, max_inventory_date)

def calculate_inventory_turnover(
    fact_sales: pd.DataFrame,
    fact_inventory: pd.DataFrame,
    dim_product: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Calculate top SKUs by inventory turnover over the last six
    calendar months ending at the reference date.

    Operational definition:
        units sold / average daily inventory units

    Inventory is first aggregated across stores by product/day.
    Missing inventory observations are excluded rather than
    interpreted as zero.
    """
    start_date = (
        reference_date
        - pd.DateOffset(months=6)
        + pd.Timedelta(days=1)
    )

    sales_window = fact_sales[
        (fact_sales["transaction_date"] >= start_date)
        & (fact_sales["transaction_date"] <= reference_date)
    ].copy()

    inventory_window = fact_inventory[
        (fact_inventory["snapshot_date"] >= start_date)
        & (fact_inventory["snapshot_date"] <= reference_date)
    ].copy()

    # Physical sales are used because inventory snapshots represent
    # physical stores and ecommerce has no store attribution.
    physical_sales = sales_window[
        sales_window["channel"] == "physical"
    ]

    units_sold = (
        physical_sales
        .groupby("product_key", as_index=False)["quantity"]
        .sum()
        .rename(columns={"quantity": "units_sold"})
    )

    # Missing observations remain unknown.
    known_inventory = inventory_window[
        ~inventory_window["is_missing"]
    ].copy()

    daily_inventory = (
        known_inventory
        .groupby(
            ["snapshot_date", "product_key"],
            as_index=False,
        )["stock_quantity"]
        .sum()
        .rename(
            columns={
                "stock_quantity": "daily_inventory_units"
            }
        )
    )

    average_inventory = (
        daily_inventory
        .groupby("product_key", as_index=False)[
            "daily_inventory_units"
        ]
        .mean()
        .rename(
            columns={
                "daily_inventory_units":
                    "average_daily_inventory_units"
            }
        )
    )

    turnover = units_sold.merge(
        average_inventory,
        on="product_key",
        how="inner",
        validate="one_to_one",
    )

    turnover["inventory_turnover"] = (
        turnover["units_sold"]
        / turnover["average_daily_inventory_units"]
    )

    product_attributes = dim_product[
        [
            "product_key",
            "sku_pos",
            "sku_erp",
            "product_name",
            "category",
        ]
    ]

    turnover = turnover.merge(
        product_attributes,
        on="product_key",
        how="left",
        validate="one_to_one",
    )

    turnover["period_start"] = start_date
    turnover["period_end"] = reference_date

    turnover = turnover.sort_values(
        "inventory_turnover",
        ascending=False,
    )

    columns = [
        "product_key",
        "sku_pos",
        "sku_erp",
        "product_name",
        "category",
        "units_sold",
        "average_daily_inventory_units",
        "inventory_turnover",
        "period_start",
        "period_end",
    ]

    return turnover[columns].head(10).reset_index(drop=True)

def get_last_complete_quarter(
    reference_date: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Return the start and end dates of the most recent complete
    calendar quarter relative to the reference date.
    """
    current_quarter = reference_date.to_period("Q")

    if reference_date == current_quarter.end_time.normalize():
        last_complete_quarter = current_quarter
    else:
        last_complete_quarter = current_quarter - 1

    quarter_start = last_complete_quarter.start_time.normalize()
    quarter_end = last_complete_quarter.end_time.normalize()

    return quarter_start, quarter_end

def calculate_stockout_events(
    fact_inventory: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_store: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Find store/product stockout episodes lasting more than
    three consecutive calendar days during the last complete quarter.

    Missing inventory observations break a stockout sequence.
    """
    quarter_start, quarter_end = get_last_complete_quarter(
        reference_date
    )

    inventory = fact_inventory[
        (fact_inventory["snapshot_date"] >= quarter_start)
        & (fact_inventory["snapshot_date"] <= quarter_end)
    ].copy()

    inventory = inventory.sort_values(
        [
            "store_id",
            "product_key",
            "snapshot_date",
        ]
    )

    # A valid stockout day must be explicitly observed as zero.
    inventory["valid_stockout"] = (
        inventory["is_stockout"]
        & ~inventory["is_missing"]
    )

    # Previous state/date inside each store-product combination.
    grouped = inventory.groupby(
        ["store_id", "product_key"],
        sort=False,
    )

    inventory["previous_date"] = grouped[
        "snapshot_date"
    ].shift(1)

    inventory["previous_stockout"] = (
        grouped["valid_stockout"]
        .shift(1)
        .eq(True)
    )

    # Start a new episode when:
    # - current day is a stockout, AND
    # - previous row was not a stockout, OR
    # - previous date was not the previous calendar day.
    previous_calendar_day = (
        inventory["snapshot_date"]
        - pd.Timedelta(days=1)
    )

    inventory["starts_stockout_episode"] = (
        inventory["valid_stockout"]
        & (
            ~inventory["previous_stockout"]
            | (
                inventory["previous_date"]
                != previous_calendar_day
            )
        )
    )

    # Non-stockout rows also create boundaries between episodes.
    inventory["sequence_boundary"] = (
        inventory["starts_stockout_episode"]
        | ~inventory["valid_stockout"]
    )

    inventory["sequence_id"] = grouped[
        "sequence_boundary"
    ].cumsum()

    stockout_days = inventory[
        inventory["valid_stockout"]
    ].copy()

    events = (
        stockout_days
        .groupby(
            [
                "store_id",
                "product_key",
                "sequence_id",
            ],
            as_index=False,
        )
        .agg(
            stockout_start=("snapshot_date", "min"),
            stockout_end=("snapshot_date", "max"),
            consecutive_days=("snapshot_date", "size"),
        )
    )

    # Requirement: strictly more than 3 days.
    events = events[
        events["consecutive_days"] > 3
    ].copy()

    product_attributes = dim_product[
        [
            "product_key",
            "sku_pos",
            "sku_erp",
            "product_name",
            "category",
        ]
    ]

    events = events.merge(
        product_attributes,
        on="product_key",
        how="left",
        validate="many_to_one",
    )

    store_attributes = dim_store[
        [
            "store_id",
            "city",
            "region",
        ]
    ]

    events = events.merge(
        store_attributes,
        on="store_id",
        how="left",
        validate="many_to_one",
    )

    events["quarter_start"] = quarter_start
    events["quarter_end"] = quarter_end

    events = events.sort_values(
        [
            "consecutive_days",
            "store_id",
            "product_key",
        ],
        ascending=[False, True, True],
    )

    columns = [
        "store_id",
        "city",
        "region",
        "product_key",
        "sku_pos",
        "sku_erp",
        "product_name",
        "category",
        "stockout_start",
        "stockout_end",
        "consecutive_days",
        "quarter_start",
        "quarter_end",
    ]

    return events[columns].reset_index(drop=True)

def summarize_stockouts_by_store(
    stockout_events: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize qualifying stockout episodes at store level.
    """
    if stockout_events.empty:
        return pd.DataFrame(
            columns=[
                "store_id",
                "city",
                "region",
                "stockout_events",
                "affected_products",
                "total_stockout_days",
                "longest_stockout_days",
            ]
        )

    summary = (
        stockout_events
        .groupby(
            ["store_id", "city", "region"],
            as_index=False,
        )
        .agg(
            stockout_events=(
                "consecutive_days",
                "size",
            ),
            affected_products=(
                "product_key",
                "nunique",
            ),
            total_stockout_days=(
                "consecutive_days",
                "sum",
            ),
            longest_stockout_days=(
                "consecutive_days",
                "max",
            ),
        )
    )

    summary = summary.sort_values(
        [
            "longest_stockout_days",
            "stockout_events",
        ],
        ascending=False,
    )

    return summary.reset_index(drop=True)

def calculate_monthly_sales_growth(
    fact_sales: pd.DataFrame,
    reference_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Calculate month-over-month revenue growth by channel for the
    last 12 complete calendar months ending at the reference month.

    Revenue is expressed in MXN.

    The previous month is included temporarily when available so
    that MoM growth for the first reporting month can be calculated.

    If a channel has no data in the previous month, its first MoM
    value remains unknown rather than assuming zero revenue.
    """
    report_end = reference_date.to_period("M").start_time

    report_start = (
        report_end
        - pd.DateOffset(months=11)
    )

    comparison_start = (
        report_start
        - pd.DateOffset(months=1)
    )

    sales = fact_sales.copy()

    sales["month"] = (
        sales["transaction_date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    comparison_window = sales[
        (sales["month"] >= comparison_start)
        & (sales["month"] <= report_end)
    ].copy()

    monthly = (
        comparison_window
        .groupby(
            ["channel", "month"],
            as_index=False,
        )
        .agg(
            revenue_mxn=("revenue_mxn", "sum"),
            units_sold=("quantity", "sum"),
            transactions=("transaction_id", "size"),
        )
    )

    monthly = monthly.sort_values(
        ["channel", "month"]
    )

    monthly["previous_month"] = (
        monthly.groupby("channel")["month"]
        .shift(1)
    )

    monthly["previous_revenue_mxn"] = (
        monthly.groupby("channel")["revenue_mxn"]
        .shift(1)
    )

    expected_previous_month = (
        monthly["month"]
        - pd.DateOffset(months=1)
    )

    has_valid_previous_month = (
        monthly["previous_month"]
        == expected_previous_month
    )

    monthly["mom_growth_pct"] = pd.NA

    valid = (
        has_valid_previous_month
        & monthly["previous_revenue_mxn"].notna()
        & (monthly["previous_revenue_mxn"] != 0)
    )

    monthly.loc[
        valid,
        "mom_growth_pct"
    ] = (
        (
            monthly.loc[valid, "revenue_mxn"]
            - monthly.loc[valid, "previous_revenue_mxn"]
        )
        / monthly.loc[valid, "previous_revenue_mxn"]
        * 100
    )

    monthly["mom_growth_pct"] = pd.to_numeric(
        monthly["mom_growth_pct"],
        errors="coerce",
    )

    result = monthly[
        (monthly["month"] >= report_start)
        & (monthly["month"] <= report_end)
    ].copy()

    columns = [
        "month",
        "channel",
        "revenue_mxn",
        "previous_revenue_mxn",
        "mom_growth_pct",
        "units_sold",
        "transactions",
    ]

    return (
        result[columns]
        .sort_values(["month", "channel"])
        .reset_index(drop=True)
    )
    
def calculate_negative_margin_products(
    fact_sales: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_store: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identify product/store combinations with negative aggregate margin.

    Only transactions with a known historical unit cost are included.
    Unknown costs are excluded rather than interpreted as zero.

    A product/store combination is considered negative only when its
    aggregate margin is below zero.
    """
    known_cost = fact_sales[
        fact_sales["has_known_cost"]
        & fact_sales["unit_cost_mxn"].notna()
    ].copy()

    # Q4 asks in which stores negative margins occur, so only
    # transactions with a physical store attribution are evaluated.
    store_sales = known_cost[
        known_cost["store_id"].notna()
    ].copy()

    # Aggregate using analytical keys only.
    result = (
        store_sales
        .groupby(
            [
                "store_id",
                "product_key",
            ],
            as_index=False,
        )
        .agg(
            transactions=("transaction_id", "size"),
            units_sold=("quantity", "sum"),
            revenue_mxn=("revenue_mxn", "sum"),
            cogs_mxn=("cogs_mxn", "sum"),
        )
    )

    result["margin_mxn"] = (
        result["revenue_mxn"]
        - result["cogs_mxn"]
    )

    result["margin_pct"] = (
        result["margin_mxn"]
        / result["revenue_mxn"]
        * 100
    )

    # Keep only product/store combinations whose aggregate margin
    # is actually negative.
    result = result[
        result["margin_mxn"] < 0
    ].copy()

    # Add product attributes after aggregation.
    product_attributes = dim_product[
        [
            "product_key",
            "sku_pos",
            "sku_erp",
            "product_name",
            "category",
        ]
    ]

    result = result.merge(
        product_attributes,
        on="product_key",
        how="left",
        validate="many_to_one",
    )

    # Add store attributes.
    store_attributes = dim_store[
        [
            "store_id",
            "city",
            "region",
        ]
    ]

    result = result.merge(
        store_attributes,
        on="store_id",
        how="left",
        validate="many_to_one",
    )

    result = result.sort_values(
        "margin_mxn",
        ascending=True,
    )

    columns = [
        "product_key",
        "sku_pos",
        "sku_erp",
        "product_name",
        "category",
        "store_id",
        "city",
        "region",
        "transactions",
        "units_sold",
        "revenue_mxn",
        "cogs_mxn",
        "margin_mxn",
        "margin_pct",
    ]

    return result[columns].reset_index(drop=True)

def summarize_negative_margin_products(
    negative_margin_products: pd.DataFrame,
) -> pd.DataFrame:
    """
    Summarize negative-margin product/store combinations by product.

    The input contains only product/store combinations whose aggregate
    margin is negative.
    """
    if negative_margin_products.empty:
        return pd.DataFrame(
            columns=[
                "product_key",
                "sku_pos",
                "sku_erp",
                "product_name",
                "category",
                "stores_affected",
                "transactions",
                "units_sold",
                "revenue_mxn",
                "cogs_mxn",
                "margin_mxn",
                "margin_pct",
            ]
        )

    summary = (
        negative_margin_products
        .groupby(
            [
                "product_key",
                "sku_pos",
                "sku_erp",
                "product_name",
                "category",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            stores_affected=("store_id", "nunique"),
            transactions=("transactions", "sum"),
            units_sold=("units_sold", "sum"),
            revenue_mxn=("revenue_mxn", "sum"),
            cogs_mxn=("cogs_mxn", "sum"),
        )
    )

    summary["margin_mxn"] = (
        summary["revenue_mxn"]
        - summary["cogs_mxn"]
    )

    summary["margin_pct"] = (
        summary["margin_mxn"]
        / summary["revenue_mxn"]
        * 100
    )

    summary = summary.sort_values(
        "margin_mxn",
        ascending=True,
    )

    return summary.reset_index(drop=True)