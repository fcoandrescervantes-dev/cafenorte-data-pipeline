import pandas as pd

def build_product_dimension(
    inventory_data: dict,
    sku_mappings: pd.DataFrame,
    sales: pd.DataFrame,
    ecommerce: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a canonical product dimension.

    ERP catalog products form the backbone of the dimension.
    Mapping rows without an ERP identifier and source identifiers without
    any mapping are preserved rather than silently discarded.
    """

    # -------------------------
    # 1. ERP catalog backbone
    # -------------------------
    catalog_records = []

    for product in inventory_data["catalogo"]["productos"]:
        catalog_records.append(
            {
                "sku_erp": product.get("sku_erp"),
                "product_name": product.get("nombre"),
                "category": product.get("categoria"),
            }
        )

    catalog = pd.DataFrame(catalog_records)

    catalog["sku_erp"] = (
        catalog["sku_erp"]
        .astype("string")
        .str.strip()
    )

    # -------------------------
    # 2. Mappings linked to ERP
    # -------------------------
    erp_mappings = sku_mappings.dropna(
        subset=["sku_erp"]
    ).copy()

    products = catalog.merge(
        erp_mappings,
        on="sku_erp",
        how="left",
        validate="one_to_one",
    )

    # -------------------------
    # 3. Mapping rows without ERP
    # -------------------------
    mappings_without_erp = sku_mappings[
        sku_mappings["sku_erp"].isna()
    ].copy()

    if not mappings_without_erp.empty:
        mappings_without_erp["product_name"] = pd.NA
        mappings_without_erp["category"] = pd.NA

        mappings_without_erp = mappings_without_erp[
            [
                "sku_erp",
                "product_name",
                "category",
                "sku_pos",
                "shopify_handle",
            ]
        ]

        products = pd.concat(
            [products, mappings_without_erp],
            ignore_index=True,
        )

    # -------------------------
    # 4. Preserve POS identifiers
    #    not represented anywhere
    # -------------------------
    mapped_pos = set(
        products["sku_pos"].dropna()
    )

    source_pos = set(
        sales["sku"].dropna()
    )

    unmapped_pos = sorted(
        source_pos - mapped_pos
    )

    pos_orphans = pd.DataFrame(
        {
            "sku_erp": pd.NA,
            "product_name": pd.NA,
            "category": pd.NA,
            "sku_pos": unmapped_pos,
            "shopify_handle": pd.NA,
        }
    )

    # -------------------------
    # 5. Preserve Shopify identifiers
    #    not represented anywhere
    # -------------------------
    mapped_shopify = set(
        products["shopify_handle"].dropna()
    )

    source_shopify = set(
        ecommerce["product_handle"].dropna()
    )

    unmapped_shopify = sorted(
        source_shopify - mapped_shopify
    )

    shopify_orphans = pd.DataFrame(
        {
            "sku_erp": pd.NA,
            "product_name": pd.NA,
            "category": pd.NA,
            "sku_pos": pd.NA,
            "shopify_handle": unmapped_shopify,
        }
    )

    # -------------------------
    # 6. Combine all products
    # -------------------------
    for frame in [products, pos_orphans, shopify_orphans]:
        for column in [
            "sku_erp",
            "product_name",
            "category",
            "sku_pos",
            "shopify_handle",
        ]:
            frame[column] = frame[column].astype("string")
    products = pd.concat(
        [
            products,
            pos_orphans,
            shopify_orphans,
        ],
        ignore_index=True,
    )

    # -------------------------
    # 7. Mapping status
    # -------------------------
    identifier_columns = [
        "sku_pos",
        "sku_erp",
        "shopify_handle",
    ]

    identifier_count = (
        products[identifier_columns]
        .notna()
        .sum(axis=1)
    )

    products["mapping_status"] = "partial"

    products.loc[
        identifier_count == 3,
        "mapping_status"
    ] = "complete"

    products.loc[
        identifier_count == 1,
        "mapping_status"
    ] = "unmapped"

    # -------------------------
    # 8. Canonical surrogate key
    # -------------------------
    products["product_key"] = [
        f"P{i:05d}"
        for i in range(1, len(products) + 1)
    ]

    columns = [
        "product_key",
        "sku_pos",
        "sku_erp",
        "shopify_handle",
        "product_name",
        "category",
        "mapping_status",
    ]

    return products[columns]

def reconcile_pos_sales(
    sales: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reconcile POS sales with the canonical product dimension.
    """
    product_lookup = (
        dim_product[
            [
                "product_key",
                "sku_pos",
                "mapping_status",
            ]
        ]
        .dropna(subset=["sku_pos"])
        .copy()
    )

    reconciled = sales.merge(
        product_lookup,
        left_on="sku",
        right_on="sku_pos",
        how="left",
        validate="many_to_one",
    )

    reconciled["channel"] = "physical"
    reconciled["source_system"] = "pos"

    return reconciled

def reconcile_ecommerce_sales(
    ecommerce: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    """
    Reconcile Shopify sales with the canonical product dimension.
    """
    product_lookup = (
        dim_product[
            [
                "product_key",
                "shopify_handle",
                "mapping_status",
            ]
        ]
        .dropna(subset=["shopify_handle"])
        .copy()
    )

    reconciled = ecommerce.merge(
        product_lookup,
        left_on="product_handle",
        right_on="shopify_handle",
        how="left",
        validate="many_to_one",
    )

    reconciled["channel"] = "ecommerce"
    reconciled["source_system"] = "shopify"

    return reconciled

def apply_ecommerce_fx(
    ecommerce: pd.DataFrame,
    exchange_rates: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert ecommerce revenue to MXN using the exchange rate
    for the transaction date and currency.
    """
    ecommerce = ecommerce.copy()
    exchange_rates = exchange_rates.copy()

    ecommerce["transaction_date"] = (
        ecommerce["fecha"].dt.normalize()
    )

    exchange_rates["rate_date"] = (
        exchange_rates["fecha"].dt.normalize()
    )

    foreign_rates = exchange_rates[
        ["rate_date", "currency", "rate_to_mxn"]
    ]

    ecommerce = ecommerce.merge(
        foreign_rates,
        left_on=["transaction_date", "currency"],
        right_on=["rate_date", "currency"],
        how="left",
        validate="many_to_one",
    )

    # MXN transactions do not require an external FX record.
    ecommerce.loc[
        ecommerce["currency"] == "MXN",
        "rate_to_mxn"
    ] = 1.0

    ecommerce["revenue_mxn"] = (
        ecommerce["amount"]
        * ecommerce["rate_to_mxn"]
    )

    ecommerce = ecommerce.drop(
        columns=["rate_date"]
    )

    return ecommerce

def prepare_pos_fact(
    pos_sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Standardize reconciled POS sales into the common sales fact schema.
    POS revenue is already denominated in MXN.
    """
    df = pos_sales.copy()
    
    df["store_id"] = df["tienda_id"].astype("string")

    df["transaction_date"] = df["fecha_hora"].dt.normalize()
    df["rate_to_mxn"] = 1.0
    df["revenue_mxn"] = df["monto"]

    df = df.rename(
        columns={
            "venta_id": "transaction_id",
            "fecha_hora": "transaction_ts",
            "cantidad": "quantity",
            "monto": "amount_original",
            "moneda": "currency",
        }
    )

    columns = [
        "transaction_id",
        "transaction_ts",
        "transaction_date",
        "product_key",
        "store_id",
        "channel",
        "quantity",
        "amount_original",
        "currency",
        "rate_to_mxn",
        "revenue_mxn",
        "mapping_status",
        "source_system",
    ]

    return df[columns]

def prepare_ecommerce_fact(
    ecommerce_sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Standardize reconciled ecommerce sales into the common sales fact schema.
    Ecommerce has no physical store identifier in the source.
    """
    df = ecommerce_sales.copy()

    df = df.rename(
        columns={
            "order_id": "transaction_id",
            "fecha": "transaction_ts",
            "cantidad": "quantity",
            "amount": "amount_original",
        }
    )

    df["store_id"] = pd.Series(
    pd.NA,
    index=df.index,
    dtype="string",
    )

    columns = [
        "transaction_id",
        "transaction_ts",
        "transaction_date",
        "product_key",
        "store_id",
        "channel",
        "quantity",
        "amount_original",
        "currency",
        "rate_to_mxn",
        "revenue_mxn",
        "mapping_status",
        "source_system",
    ]

    return df[columns]

def combine_sales_facts(
    pos_fact: pd.DataFrame,
    ecommerce_fact: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combine physical and ecommerce sales into one analytical fact table.
    """
    fact_sales = pd.concat(
        [pos_fact, ecommerce_fact],
        ignore_index=True,
    )

    return fact_sales

def add_product_attributes_to_sales(
    fact_sales: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add ERP product identity and descriptive attributes needed
    for historical cost attribution and analytics.
    """
    product_attributes = dim_product[
        [
            "product_key",
            "sku_erp",
            "product_name",
            "category",
        ]
    ].copy()

    result = fact_sales.merge(
        product_attributes,
        on="product_key",
        how="left",
        validate="many_to_one",
    )

    return result

def add_historical_costs(
    fact_sales: pd.DataFrame,
    product_cost_history: pd.DataFrame,
) -> pd.DataFrame:
    """
    Assign the most recent known unit cost effective on or before
    each transaction date.

    Sales without an ERP product mapping retain missing cost,
    COGS and margin rather than receiving an assumed value.
    """
    sales = fact_sales.copy()
    costs = product_cost_history.copy()

    # Preserve rows that cannot be connected to ERP separately.
    sales_with_erp = sales[
        sales["sku_erp"].notna()
    ].copy()

    sales_without_erp = sales[
        sales["sku_erp"].isna()
    ].copy()

    # merge_asof requires sorted temporal keys.
    sales_with_erp = sales_with_erp.sort_values(
        ["transaction_date", "sku_erp"]
    )

    costs = costs.sort_values(
        ["effective_date", "sku_erp"]
    )

    sales_with_cost = pd.merge_asof(
        sales_with_erp,
        costs[
            [
                "sku_erp",
                "effective_date",
                "unit_cost_mxn",
            ]
        ],
        left_on="transaction_date",
        right_on="effective_date",
        by="sku_erp",
        direction="backward",
        allow_exact_matches=True,
    )

    # Rows without ERP cannot be assigned a defensible cost.
    sales_without_erp["effective_date"] = pd.NaT
    sales_without_erp["unit_cost_mxn"] = float("nan")

    result = pd.concat(
        [
            sales_with_cost,
            sales_without_erp,
        ],
        ignore_index=True,
    )

    # Restore a deterministic analytical order.
    result = result.sort_values(
        ["transaction_ts", "transaction_id"]
    ).reset_index(drop=True)

    return result

def calculate_sales_margin(
    fact_sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate transaction-level COGS and margin where historical
    unit cost is known.
    """
    df = fact_sales.copy()

    df["cogs_mxn"] = (
        df["quantity"]
        * df["unit_cost_mxn"]
    )

    df["margin_mxn"] = (
        df["revenue_mxn"]
        - df["cogs_mxn"]
    )

    df["has_known_cost"] = (
        df["unit_cost_mxn"].notna()
    )

    return df

def build_inventory_fact(
    inventory_snapshots: pd.DataFrame,
    dim_product: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build canonical daily inventory snapshot fact.
    Missing stock remains unknown and is not interpreted as zero.
    """
    product_lookup = (
        dim_product[
            [
                "product_key",
                "sku_erp",
            ]
        ]
        .dropna(subset=["sku_erp"])
        .copy()
    )

    inventory = inventory_snapshots.merge(
        product_lookup,
        on="sku_erp",
        how="left",
        validate="many_to_one",
    )

    inventory = inventory.rename(
        columns={
            "fecha": "snapshot_date",
            "tienda_id": "store_id",
            "cantidad_en_stock": "stock_quantity",
        }
    )

    inventory["is_missing"] = (
        inventory["stock_quantity"].isna()
    )

    inventory["is_stockout"] = (
        inventory["stock_quantity"].eq(0)
        & ~inventory["is_missing"]
    )

    inventory["source_system"] = "erp"

    columns = [
        "snapshot_date",
        "store_id",
        "product_key",
        "sku_erp",
        "stock_quantity",
        "is_stockout",
        "is_missing",
        "source_system",
    ]

    return inventory[columns]