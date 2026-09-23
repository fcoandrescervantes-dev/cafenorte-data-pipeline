from pathlib import Path

import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


@pytest.fixture(scope="module")
def fact_sales():
    return pd.read_parquet(
        PROCESSED_DIR / "fact_sales.parquet"
    )


@pytest.fixture(scope="module")
def fact_inventory():
    return pd.read_parquet(
        PROCESSED_DIR / "fact_inventory.parquet"
    )


@pytest.fixture(scope="module")
def dim_product():
    return pd.read_parquet(
        PROCESSED_DIR / "dim_product.parquet"
    )


@pytest.fixture(scope="module")
def dim_store():
    return pd.read_parquet(
        PROCESSED_DIR / "dim_store.parquet"
    )


def test_sales_transaction_id_is_unique(fact_sales):
    assert fact_sales["transaction_id"].notna().all()
    assert fact_sales["transaction_id"].is_unique


def test_sales_product_key_is_valid(
    fact_sales,
    dim_product,
):
    valid_products = set(
        dim_product["product_key"].dropna()
    )

    sales_products = set(
        fact_sales["product_key"].dropna()
    )

    assert fact_sales["product_key"].notna().all()
    assert sales_products.issubset(valid_products)


def test_physical_sales_store_is_valid(
    fact_sales,
    dim_store,
):
    physical = fact_sales[
        fact_sales["channel"] == "physical"
    ]

    valid_stores = set(
        dim_store["store_id"].dropna()
    )

    physical_stores = set(
        physical["store_id"].dropna()
    )

    assert physical["store_id"].notna().all()
    assert physical_stores.issubset(valid_stores)


def test_sales_quantity_is_positive(fact_sales):
    assert fact_sales["quantity"].notna().all()
    assert (fact_sales["quantity"] > 0).all()


def test_sales_revenue_is_non_negative(fact_sales):
    assert fact_sales["revenue_mxn"].notna().all()
    assert (fact_sales["revenue_mxn"] >= 0).all()
    
def test_sales_fx_rate_is_positive(fact_sales):
    assert fact_sales["rate_to_mxn"].notna().all()
    assert (fact_sales["rate_to_mxn"] > 0).all()


def test_mxn_transactions_use_rate_one(fact_sales):
    mxn = fact_sales[
        fact_sales["currency"] == "MXN"
    ]

    assert (mxn["rate_to_mxn"] == 1.0).all()


def test_revenue_mxn_matches_fx_conversion(fact_sales):
    expected_revenue = (
        fact_sales["amount_original"]
        * fact_sales["rate_to_mxn"]
    )

    assert (
        fact_sales["revenue_mxn"]
        .sub(expected_revenue)
        .abs()
        < 0.000001
    ).all()


def test_known_cost_has_valid_cogs_and_margin(
    fact_sales,
):
    known = fact_sales[
        fact_sales["has_known_cost"]
    ]

    assert known["unit_cost_mxn"].notna().all()
    assert known["cogs_mxn"].notna().all()
    assert known["margin_mxn"].notna().all()

    expected_cogs = (
        known["quantity"]
        * known["unit_cost_mxn"]
    )

    assert (
        known["cogs_mxn"]
        .sub(expected_cogs)
        .abs()
        < 0.000001
    ).all()

    expected_margin = (
        known["revenue_mxn"]
        - known["cogs_mxn"]
    )

    assert (
        known["margin_mxn"]
        .sub(expected_margin)
        .abs()
        < 0.000001
    ).all()


def test_unknown_cost_remains_unknown(fact_sales):
    unknown = fact_sales[
        ~fact_sales["has_known_cost"]
    ]

    assert len(unknown) > 0

    assert unknown["unit_cost_mxn"].isna().all()
    assert unknown["cogs_mxn"].isna().all()
    assert unknown["margin_mxn"].isna().all()
    
def test_inventory_natural_key_is_unique(
    fact_inventory,
):
    duplicates = fact_inventory.duplicated(
        [
            "snapshot_date",
            "store_id",
            "product_key",
        ]
    )

    assert duplicates.sum() == 0


def test_inventory_product_key_is_valid(
    fact_inventory,
    dim_product,
):
    valid_products = set(
        dim_product["product_key"].dropna()
    )

    inventory_products = set(
        fact_inventory["product_key"].dropna()
    )

    assert fact_inventory["product_key"].notna().all()
    assert inventory_products.issubset(valid_products)


def test_inventory_store_is_valid(
    fact_inventory,
    dim_store,
):
    valid_stores = set(
        dim_store["store_id"].dropna()
    )

    inventory_stores = set(
        fact_inventory["store_id"].dropna()
    )

    assert fact_inventory["store_id"].notna().all()
    assert inventory_stores.issubset(valid_stores)


def test_known_inventory_is_non_negative(
    fact_inventory,
):
    known = fact_inventory[
        ~fact_inventory["is_missing"]
    ]

    assert known["stock_quantity"].notna().all()
    assert (known["stock_quantity"] >= 0).all()


def test_missing_inventory_is_not_stockout(
    fact_inventory,
):
    missing = fact_inventory[
        fact_inventory["is_missing"]
    ]

    assert len(missing) > 0

    assert missing["stock_quantity"].isna().all()
    assert (~missing["is_stockout"]).all()


def test_stockout_means_zero_known_stock(
    fact_inventory,
):
    stockouts = fact_inventory[
        fact_inventory["is_stockout"]
    ]

    assert len(stockouts) > 0
    assert (~stockouts["is_missing"]).all()
    assert (stockouts["stock_quantity"] == 0).all()