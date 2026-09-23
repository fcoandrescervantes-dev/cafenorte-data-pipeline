from pathlib import Path

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
    normalize_stores,
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

from src.analytics import (
    get_reference_date,
    calculate_inventory_turnover,
    calculate_stockout_events,
    summarize_stockouts_by_store,
    calculate_monthly_sales_growth,
    calculate_negative_margin_products,
    summarize_negative_margin_products,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def main():
    # -------------------------
    # 1. Ingest
    # -------------------------
    sales_raw = load_sales()
    inventory_raw = load_inventory()
    ecommerce_raw = load_ecommerce()
    exchange_rates_raw = load_exchange_rates()

    # -------------------------
    # 2. Normalize
    # -------------------------
    sales = normalize_sales(sales_raw)
    ecommerce = normalize_ecommerce(ecommerce_raw)

    exchange_rates = normalize_exchange_rates(
        exchange_rates_raw
    )

    stores = normalize_stores(inventory_raw)

    mappings = normalize_sku_mappings(
        inventory_raw
    )

    inventory_snapshots = normalize_inventory_snapshots(
        inventory_raw
    )

    product_cost_history = normalize_product_cost_history(
        inventory_raw
    )

    # -------------------------
    # 3. Product reconciliation
    # -------------------------
    dim_product = build_product_dimension(
        inventory_raw,
        mappings,
        sales,
        ecommerce,
    )

    # -------------------------
    # 4. POS sales
    # -------------------------
    pos_sales = reconcile_pos_sales(
        sales,
        dim_product,
    )

    pos_fact = prepare_pos_fact(
        pos_sales
    )

    # -------------------------
    # 5. Ecommerce sales
    # -------------------------
    ecommerce_fx = apply_ecommerce_fx(
        ecommerce,
        exchange_rates,
    )

    ecommerce_sales = reconcile_ecommerce_sales(
        ecommerce_fx,
        dim_product,
    )

    ecommerce_fact = prepare_ecommerce_fact(
        ecommerce_sales
    )

    # -------------------------
    # 6. Unified sales fact
    # -------------------------
    fact_sales = combine_sales_facts(
        pos_fact,
        ecommerce_fact,
    )

    fact_sales = add_product_attributes_to_sales(
        fact_sales,
        dim_product,
    )

    fact_sales = add_historical_costs(
        fact_sales,
        product_cost_history,
    )

    fact_sales = calculate_sales_margin(
        fact_sales
    )

    # -------------------------
    # 7. Inventory fact
    # -------------------------
    fact_inventory = build_inventory_fact(
        inventory_snapshots,
        dim_product,
    )

        # -------------------------
    # 8. Business analytics
    # -------------------------
    reference_date = get_reference_date(
        fact_sales,
        fact_inventory,
    )

    # Q1 - Top 10 SKUs by inventory turnover
    q1_inventory_turnover = calculate_inventory_turnover(
        fact_sales,
        fact_inventory,
        dim_product,
        reference_date,
    )

    # Q2 - Stockout events longer than 3 days
    q2_stockout_events = calculate_stockout_events(
        fact_inventory,
        dim_product,
        stores,
        reference_date,
    )

    q2_stockouts_by_store = summarize_stockouts_by_store(
        q2_stockout_events
    )

    # Q3 - Month-over-month sales growth by channel
    q3_monthly_sales_growth = calculate_monthly_sales_growth(
        fact_sales,
        reference_date,
    )

    # Q4 - Products with negative aggregate margin by store
    q4_negative_margin_by_store = calculate_negative_margin_products(
        fact_sales,
        dim_product,
        stores,
    )

    q4_negative_margin_products = summarize_negative_margin_products(
        q4_negative_margin_by_store
    )
    
    # -------------------------
    # 9. Persist analytical model
    # -------------------------
    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stores.to_parquet(
        PROCESSED_DIR / "dim_store.parquet",
        index=False,
    )

    dim_product.to_parquet(
        PROCESSED_DIR / "dim_product.parquet",
        index=False,
    )

    product_cost_history.to_parquet(
        PROCESSED_DIR / "product_cost_history.parquet",
        index=False,
    )

    fact_sales.to_parquet(
        PROCESSED_DIR / "fact_sales.parquet",
        index=False,
    )

    fact_inventory.to_parquet(
        PROCESSED_DIR / "fact_inventory.parquet",
        index=False,
    )
    
        # -------------------------
    # 10. Persist business outputs
    # -------------------------
    q1_inventory_turnover.to_csv(
        OUTPUT_DIR / "q1_inventory_turnover.csv",
        index=False,
    )

    q2_stockout_events.to_csv(
        OUTPUT_DIR / "q2_stockout_events.csv",
        index=False,
    )

    q2_stockouts_by_store.to_csv(
        OUTPUT_DIR / "q2_stockouts_by_store.csv",
        index=False,
    )

    q3_monthly_sales_growth.to_csv(
        OUTPUT_DIR / "q3_monthly_sales_growth.csv",
        index=False,
    )

    q4_negative_margin_by_store.to_csv(
        OUTPUT_DIR / "q4_negative_margin_by_store.csv",
        index=False,
    )

    q4_negative_margin_products.to_csv(
        OUTPUT_DIR / "q4_negative_margin_products.csv",
        index=False,
    )

    # -------------------------
    # 11. Summary
    # -------------------------
    print("Pipeline completed successfully")
    print(f"Stores: {len(stores):,}")
    print(f"Products: {len(dim_product):,}")
    print(f"Cost history records: {len(product_cost_history):,}")
    print(f"Sales fact rows: {len(fact_sales):,}")
    print(f"Inventory fact rows: {len(fact_inventory):,}")

    print(
        "Sales with unknown historical cost: "
        f"{fact_sales['unit_cost_mxn'].isna().sum():,}"
    )

    print(
        "Inventory snapshots with unknown stock: "
        f"{fact_inventory['is_missing'].sum():,}"
    )
    
    print()
    print("Business analytics generated")
    print(f"Reference date: {reference_date.date()}")

    print(
        "Q1 - Inventory turnover SKUs: "
        f"{len(q1_inventory_turnover):,}"
    )

    print(
        "Q2 - Stockout events > 3 days: "
        f"{len(q2_stockout_events):,}"
    )

    print(
        "Q3 - Channel-month records: "
        f"{len(q3_monthly_sales_growth):,}"
    )

    print(
        "Q4 - Negative product-store combinations: "
        f"{len(q4_negative_margin_by_store):,}"
    )

    print(
        "Q4 - Negative-margin products: "
        f"{len(q4_negative_margin_products):,}"
    )


if __name__ == "__main__":
    main()