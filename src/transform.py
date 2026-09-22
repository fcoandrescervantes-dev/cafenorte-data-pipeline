import pandas as pd

def normalize_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize physical POS sales.
    """
    df = df.copy()

    df["fecha_hora"] = pd.to_datetime(
        df["fecha_hora"],
        errors="coerce"
    )

    df["cantidad"] = pd.to_numeric(
        df["cantidad"],
        errors="coerce"
    )

    df["monto"] = pd.to_numeric(
        df["monto"],
        errors="coerce"
    )

    df["moneda"] = (
        df["moneda"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    df["sku"] = (
        df["sku"]
        .astype("string")
        .str.strip()
    )

    df["tienda_id"] = (
        df["tienda_id"]
        .astype("string")
        .str.strip()
    )

    return df

def normalize_ecommerce(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize Shopify ecommerce sales.
    Only retain fields required by the analytical model.
    """
    df = df.copy()

    df["fecha"] = pd.to_datetime(
        df["fecha"],
        errors="coerce"
    )

    df["cantidad"] = pd.to_numeric(
        df["cantidad"],
        errors="coerce"
    )

    df["amount"] = pd.to_numeric(
        df["amount"],
        errors="coerce"
    )

    df["currency"] = (
        df["currency"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    df["product_handle"] = (
        df["product_handle"]
        .astype("string")
        .str.strip()
    )

    columns_to_keep = [
        "order_id",
        "fecha",
        "product_handle",
        "cantidad",
        "amount",
        "currency",
    ]

    return df[columns_to_keep]

def normalize_exchange_rates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize daily foreign exchange rates.
    """
    df = df.copy()

    df["fecha"] = pd.to_datetime(
        df["fecha"],
        errors="coerce"
    )

    df["currency"] = (
        df["currency"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    df["rate_to_mxn"] = pd.to_numeric(
        df["rate_to_mxn"],
        errors="coerce"
    )

    return df

def normalize_stores(inventory_data: dict) -> pd.DataFrame:
    """
    Normalize store master data from the ERP JSON.
    """
    stores = pd.DataFrame(inventory_data["tiendas_info"])

    stores = stores.rename(
        columns={
            "tienda_id": "store_id",
            "ciudad": "city",
            "region": "region",
            "timezone": "timezone",
        }
    )

    stores["store_id"] = (
        stores["store_id"]
        .astype("string")
        .str.strip()
    )

    return stores

def normalize_sku_mappings(inventory_data: dict) -> pd.DataFrame:
    """
    Normalize cross-system product identifiers.
    """
    mappings = pd.DataFrame(inventory_data["sku_mappings"])

    mappings = mappings.rename(
        columns={
            "handle": "shopify_handle"
        }
    )

    for column in ["sku_pos", "sku_erp", "shopify_handle"]:
        mappings[column] = (
            mappings[column]
            .astype("string")
            .str.strip()
        )

    return mappings

def normalize_inventory_snapshots(inventory_data: dict) -> pd.DataFrame:
    """
    Normalize daily inventory snapshots.

    Missing inventory values such as "N/A" remain missing and are not
    interpreted as zero stock.
    """
    snapshots = pd.DataFrame(inventory_data["snapshots"])

    snapshots["fecha"] = pd.to_datetime(
        snapshots["fecha"],
        errors="coerce"
    )

    snapshots["cantidad_en_stock"] = pd.to_numeric(
        snapshots["cantidad_en_stock"],
        errors="coerce"
    )

    snapshots["tienda_id"] = (
        snapshots["tienda_id"]
        .astype("string")
        .str.strip()
    )

    snapshots["sku_erp"] = (
        snapshots["sku_erp"]
        .astype("string")
        .str.strip()
    )

    return snapshots

def normalize_product_cost_history(inventory_data: dict) -> pd.DataFrame:
    """
    Flatten product cost history from the ERP catalog.
    """
    records = []

    products = inventory_data["catalogo"]["productos"]

    for product in products:
        sku_erp = product.get("sku_erp")
        product_name = product.get("nombre")
        category = product.get("categoria")

        for cost in product.get("cost_history", []):
            records.append(
                {
                    "sku_erp": sku_erp,
                    "product_name": product_name,
                    "category": category,
                    "effective_date": cost.get("fecha_vigencia"),
                    "unit_cost_mxn": cost.get("costo_mxn"),
                    "supplier": cost.get("proveedor"),
                }
            )

    costs = pd.DataFrame(records)

    costs["effective_date"] = pd.to_datetime(
        costs["effective_date"],
        errors="coerce"
    )

    costs["unit_cost_mxn"] = pd.to_numeric(
        costs["unit_cost_mxn"],
        errors="coerce"
    )

    costs["sku_erp"] = (
        costs["sku_erp"]
        .astype("string")
        .str.strip()
    )

    return costs