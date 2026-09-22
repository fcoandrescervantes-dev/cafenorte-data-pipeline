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


def main():
    # -------------------------
    # 1. Ingest raw sources
    # -------------------------
    sales_raw = load_sales()
    inventory_raw = load_inventory()
    ecommerce_raw = load_ecommerce()
    exchange_rates_raw = load_exchange_rates()

    # -------------------------
    # 2. Normalize sources
    # -------------------------
    sales = normalize_sales(sales_raw)

    ecommerce = normalize_ecommerce(
        ecommerce_raw
    )

    exchange_rates = normalize_exchange_rates(
        exchange_rates_raw
    )

    stores = normalize_stores(
        inventory_raw
    )

    sku_mappings = normalize_sku_mappings(
        inventory_raw
    )

    inventory_snapshots = normalize_inventory_snapshots(
        inventory_raw
    )

    product_cost_history = normalize_product_cost_history(
        inventory_raw
    )

    # -------------------------
    # Pipeline summary
    # -------------------------
    print("Ingestion and normalization completed successfully")
    print(f"POS sales: {len(sales):,}")
    print(f"Ecommerce sales: {len(ecommerce):,}")
    print(f"Exchange rates: {len(exchange_rates):,}")
    print(f"Stores: {len(stores):,}")
    print(f"SKU mappings: {len(sku_mappings):,}")
    print(f"Inventory snapshots: {len(inventory_snapshots):,}")
    print(f"Cost history records: {len(product_cost_history):,}")


if __name__ == "__main__":
    main()