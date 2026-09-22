from src.ingest import (
    load_sales,
    load_inventory,
    load_ecommerce,
    load_exchange_rates,
)


def test_load_sales():
    df = load_sales()

    assert not df.empty
    assert "venta_id" in df.columns
    assert "sku" in df.columns


def test_load_ecommerce():
    df = load_ecommerce()

    assert not df.empty
    assert "order_id" in df.columns
    assert "product_handle" in df.columns


def test_load_exchange_rates():
    df = load_exchange_rates()

    assert not df.empty
    assert "currency" in df.columns
    assert "rate_to_mxn" in df.columns


def test_load_inventory():
    data = load_inventory()

    assert "snapshots" in data
    assert "sku_mappings" in data
    assert "catalogo" in data