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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


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
    # 8. Persist analytical model
    # -------------------------
    PROCESSED_DIR.mkdir(
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
    # 9. Summary
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


if __name__ == "__main__":
    main()