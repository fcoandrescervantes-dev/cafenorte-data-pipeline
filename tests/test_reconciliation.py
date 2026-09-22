import pandas as pd

from src.ingest import (
    load_sales,
    load_inventory,
    load_ecommerce,
    load_exchange_rates,
)

from src.transform import (
    normalize_sales,
    normalize_ecommerce,
    normalize_exchange_rates,
    normalize_sku_mappings,
    normalize_inventory_snapshots,
    normalize_product_cost_history,
)

from src.reconcile import (
    build_product_dimension,
    reconcile_pos_sales,
    reconcile_ecommerce_sales,
    apply_ecommerce_fx,
    prepare_pos_fact,
    prepare_ecommerce_fact,
    combine_sales_facts,
    add_product_attributes_to_sales,
    add_historical_costs,
    calculate_sales_margin,
    build_inventory_fact,
)


def build_test_model():
    inventory_raw = load_inventory()

    sales = normalize_sales(load_sales())
    ecommerce = normalize_ecommerce(load_ecommerce())
    exchange_rates = normalize_exchange_rates(
        load_exchange_rates()
    )
    mappings = normalize_sku_mappings(inventory_raw)
    costs = normalize_product_cost_history(inventory_raw)

    dim_product = build_product_dimension(
        inventory_raw,
        mappings,
        sales,
        ecommerce,
    )

    pos = reconcile_pos_sales(
        sales,
        dim_product,
    )

    pos = prepare_pos_fact(pos)

    ecommerce_fx = apply_ecommerce_fx(
        ecommerce,
        exchange_rates,
    )

    ecommerce_reconciled = reconcile_ecommerce_sales(
        ecommerce_fx,
        dim_product,
    )

    ecommerce_fact = prepare_ecommerce_fact(
        ecommerce_reconciled
    )

    fact_sales = combine_sales_facts(
        pos,
        ecommerce_fact,
    )

    fact_sales = add_product_attributes_to_sales(
        fact_sales,
        dim_product,
    )

    fact_sales = add_historical_costs(
        fact_sales,
        costs,
    )

    fact_sales = calculate_sales_margin(
        fact_sales
    )

    inventory_snapshots = normalize_inventory_snapshots(
        inventory_raw
    )

    fact_inventory = build_inventory_fact(
        inventory_snapshots,
        dim_product,
    )

    return dim_product, fact_sales, fact_inventory


def test_product_dimension_has_unique_keys():
    dim_product, _, _ = build_test_model()

    assert dim_product["product_key"].is_unique

    assert (
        dim_product["sku_pos"]
        .dropna()
        .is_unique
    )

    assert (
        dim_product["sku_erp"]
        .dropna()
        .is_unique
    )

    assert (
        dim_product["shopify_handle"]
        .dropna()
        .is_unique
    )


def test_sales_reconciliation_preserves_rows():
    _, fact_sales, _ = build_test_model()

    assert len(fact_sales) == 96437
    assert fact_sales["product_key"].notna().all()
    assert fact_sales["revenue_mxn"].notna().all()


def test_sales_channel_counts():
    _, fact_sales, _ = build_test_model()

    counts = fact_sales["channel"].value_counts()

    assert counts["physical"] == 86490
    assert counts["ecommerce"] == 9947


def test_known_erp_products_have_historical_cost():
    _, fact_sales, _ = build_test_model()

    sales_with_erp = fact_sales[
        fact_sales["sku_erp"].notna()
    ]

    assert (
        sales_with_erp["unit_cost_mxn"]
        .notna()
        .all()
    )


def test_unknown_cost_does_not_become_zero():
    _, fact_sales, _ = build_test_model()

    unknown = fact_sales[
        ~fact_sales["has_known_cost"]
    ]

    assert not unknown.empty
    assert unknown["unit_cost_mxn"].isna().all()
    assert unknown["cogs_mxn"].isna().all()
    assert unknown["margin_mxn"].isna().all()


def test_inventory_preserves_missing_stock():
    _, _, fact_inventory = build_test_model()

    assert len(fact_inventory) == 230776

    assert (
        fact_inventory["is_missing"].sum()
        == 4417
    )

    assert (
        fact_inventory["is_stockout"].sum()
        == 11726
    )

    invalid = (
        fact_inventory["is_missing"]
        & fact_inventory["is_stockout"]
    )

    assert invalid.sum() == 0


def test_inventory_natural_key_unique():
    _, _, fact_inventory = build_test_model()

    duplicates = fact_inventory.duplicated(
        [
            "snapshot_date",
            "store_id",
            "product_key",
        ]
    ).sum()

    assert duplicates == 0