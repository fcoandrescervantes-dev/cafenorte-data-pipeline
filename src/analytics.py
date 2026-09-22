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