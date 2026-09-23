import pandas as pd

from src.analytics import (
    get_reference_date,
    calculate_inventory_turnover,
    calculate_stockout_events,
    calculate_monthly_sales_growth,
    calculate_negative_margin_products,
    summarize_negative_margin_products,
)


PROCESSED_DIR = "data/processed"


def load_analytical_model():
    fact_sales = pd.read_parquet(
        f"{PROCESSED_DIR}/fact_sales.parquet"
    )

    fact_inventory = pd.read_parquet(
        f"{PROCESSED_DIR}/fact_inventory.parquet"
    )

    dim_product = pd.read_parquet(
        f"{PROCESSED_DIR}/dim_product.parquet"
    )

    dim_store = pd.read_parquet(
        f"{PROCESSED_DIR}/dim_store.parquet"
    )

    return (
        fact_sales,
        fact_inventory,
        dim_product,
        dim_store,
    )


def test_reference_date():
    sales, inventory, _, _ = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    assert pd.notna(reference_date)

    assert reference_date <= sales["transaction_date"].max()

    assert reference_date <= inventory["snapshot_date"].max()


def test_inventory_turnover_returns_top_10():
    sales, inventory, products, _ = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    result = calculate_inventory_turnover(
        sales,
        inventory,
        products,
        reference_date,
    )

    assert len(result) <= 10
    assert len(result) > 0

    assert result["product_key"].notna().all()

    assert (
        result["inventory_turnover"] >= 0
    ).all()

    assert result["inventory_turnover"].is_monotonic_decreasing


def test_inventory_turnover_has_no_duplicate_products():
    sales, inventory, products, _ = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    result = calculate_inventory_turnover(
        sales,
        inventory,
        products,
        reference_date,
    )

    assert not result["product_key"].duplicated().any()


def test_stockout_events_are_longer_than_three_days():
    sales, inventory, products, stores = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    result = calculate_stockout_events(
        inventory,
        products,
        stores,
        reference_date,
    )

    assert (
        result["consecutive_days"] > 3
    ).all()

    calculated_duration = (
        result["stockout_end"]
        - result["stockout_start"]
    ).dt.days + 1

    assert (
        calculated_duration
        == result["consecutive_days"]
    ).all()


def test_stockout_events_have_store_and_product():
    sales, inventory, products, stores = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    result = calculate_stockout_events(
        inventory,
        products,
        stores,
        reference_date,
    )

    assert result["store_id"].notna().all()
    assert result["product_key"].notna().all()
    assert result["city"].notna().all()


def test_monthly_sales_growth_has_unique_channel_month():
    sales, inventory, _, _ = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    result = calculate_monthly_sales_growth(
        sales,
        reference_date,
    )

    assert not result.duplicated(
        ["channel", "month"]
    ).any()

    assert result["revenue_mxn"].notna().all()


def test_monthly_sales_growth_contains_both_channels():
    sales, inventory, _, _ = load_analytical_model()

    reference_date = get_reference_date(
        sales,
        inventory,
    )

    result = calculate_monthly_sales_growth(
        sales,
        reference_date,
    )

    assert set(result["channel"]) == {
        "physical",
        "ecommerce",
    }


def test_negative_margin_results_are_negative():
    sales, _, products, stores = load_analytical_model()

    result = calculate_negative_margin_products(
        sales,
        products,
        stores,
    )

    assert len(result) > 0

    assert (
        result["margin_mxn"] < 0
    ).all()

    assert result["margin_mxn"].notna().all()
    assert result["store_id"].notna().all()
    assert result["city"].notna().all()


def test_negative_margin_product_store_is_unique():
    sales, _, products, stores = load_analytical_model()

    result = calculate_negative_margin_products(
        sales,
        products,
        stores,
    )

    assert not result.duplicated(
        ["product_key", "store_id"]
    ).any()


def test_negative_margin_summary_is_consistent():
    sales, _, products, stores = load_analytical_model()

    detail = calculate_negative_margin_products(
        sales,
        products,
        stores,
    )

    summary = summarize_negative_margin_products(
        detail
    )

    assert (
        summary["margin_mxn"] < 0
    ).all()

    assert (
        summary["stores_affected"] > 0
    ).all()

    assert summary["product_key"].is_unique

    assert round(
        summary["margin_mxn"].sum(),
        2,
    ) == round(
        detail["margin_mxn"].sum(),
        2,
    )