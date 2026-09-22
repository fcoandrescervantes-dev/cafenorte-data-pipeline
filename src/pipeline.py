from src.ingest import (
    load_sales,
    load_inventory,
    load_ecommerce,
    load_exchange_rates,
)


def main():
    sales = load_sales()
    inventory = load_inventory()
    ecommerce = load_ecommerce()
    exchange_rates = load_exchange_rates()

    print("Sources loaded successfully")
    print(f"Sales rows: {len(sales):,}")
    print(f"Ecommerce rows: {len(ecommerce):,}")
    print(f"Exchange rate rows: {len(exchange_rates):,}")
    print(f"Inventory sections: {list(inventory.keys())}")


if __name__ == "__main__":
    main()