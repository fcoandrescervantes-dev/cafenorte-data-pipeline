from pathlib import Path
import json

import pandas as pd


RAW_DATA_DIR = Path("data/raw")


def validate_columns(df: pd.DataFrame, required_columns: list[str], source_name: str) -> None:
    """
    Validate that a DataFrame contains all required columns.
    """
    missing_columns = set(required_columns) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"{source_name} is missing required columns: {sorted(missing_columns)}"
        )


def load_sales(file_path: Path = RAW_DATA_DIR / "sales.csv") -> pd.DataFrame:
    """
    Load physical store sales from the POS CSV file.
    """
    df = pd.read_csv(file_path)

    required_columns = [
        "venta_id",
        "fecha_hora",
        "tienda_id",
        "sku",
        "cantidad",
        "monto",
        "moneda",
        "tipo_comprobante",
    ]

    validate_columns(df, required_columns, "sales.csv")

    return df


def load_ecommerce(
    file_path: Path = RAW_DATA_DIR / "ecommerce_orders.parquet",
) -> pd.DataFrame:
    """
    Load Shopify ecommerce order lines from the Parquet file.
    """
    df = pd.read_parquet(file_path)

    required_columns = [
        "order_id",
        "fecha",
        "product_handle",
        "cantidad",
        "amount",
        "currency",
    ]

    validate_columns(df, required_columns, "ecommerce_orders.parquet")

    return df


def load_exchange_rates(
    file_path: Path = RAW_DATA_DIR / "exchange_rates.csv",
) -> pd.DataFrame:
    """
    Load daily exchange rates used to convert foreign currencies to MXN.
    """
    df = pd.read_csv(file_path)

    required_columns = [
        "fecha",
        "currency",
        "rate_to_mxn",
    ]

    validate_columns(df, required_columns, "exchange_rates.csv")

    return df


def load_inventory(
    file_path: Path = RAW_DATA_DIR / "inventory.json",
) -> dict:
    """
    Load the legacy ERP inventory JSON.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    required_sections = [
        "metadata",
        "tiendas_info",
        "sku_mappings",
        "catalogo",
        "snapshots",
    ]

    missing_sections = set(required_sections) - set(data.keys())

    if missing_sections:
        raise ValueError(
            f"inventory.json is missing required sections: {sorted(missing_sections)}"
        )

    return data