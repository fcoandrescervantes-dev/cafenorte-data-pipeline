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
    normalize_stores,
    normalize_sku_mappings,
    normalize_inventory_snapshots,
    normalize_product_cost_history,
)


def test_normalize_sales():
    df = normalize_sales(load_sales())

    assert not df.empty
    assert pd.api.types.is_datetime64_any_dtype(df["fecha_hora"])
    assert pd.api.types.is_numeric_dtype(df["cantidad"])
    assert pd.api.types.is_numeric_dtype(df["monto"])


def test_normalize_ecommerce():
    df = normalize_ecommerce(load_ecommerce())

    expected_columns = {
        "order_id",
        "fecha",
        "product_handle",
        "cantidad",
        "amount",
        "currency",
    }

    assert set(df.columns) == expected_columns
    assert pd.api.types.is_datetime64_any_dtype(df["fecha"])
    assert pd.api.types.is_numeric_dtype(df["cantidad"])
    assert pd.api.types.is_numeric_dtype(df["amount"])


def test_normalize_exchange_rates():
    df = normalize_exchange_rates(load_exchange_rates())

    assert pd.api.types.is_datetime64_any_dtype(df["fecha"])
    assert pd.api.types.is_numeric_dtype(df["rate_to_mxn"])
    assert (df["rate_to_mxn"] > 0).all()


def test_normalize_stores():
    df = normalize_stores(load_inventory())

    assert df["store_id"].is_unique
    assert df["store_id"].notna().all()


def test_normalize_sku_mappings():
    df = normalize_sku_mappings(load_inventory())

    assert df["sku_pos"].is_unique


def test_inventory_na_is_not_stockout():
    df = normalize_inventory_snapshots(load_inventory())

    assert df["cantidad_en_stock"].isna().sum() > 0
    assert (df["cantidad_en_stock"] == 0).sum() > 0


def test_inventory_natural_key_is_unique():
    df = normalize_inventory_snapshots(load_inventory())

    duplicates = df.duplicated(
        subset=["fecha", "tienda_id", "sku_erp"]
    ).sum()

    assert duplicates == 0


def test_product_cost_history():
    df = normalize_product_cost_history(load_inventory())

    assert not df.empty
    assert df["effective_date"].notna().all()
    assert df["unit_cost_mxn"].notna().all()
    assert (df["unit_cost_mxn"] >= 0).all()