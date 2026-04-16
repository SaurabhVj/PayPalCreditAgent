"""Product catalog service — pluggable interface with dummy implementation."""

import json
import os
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

CATALOGS_DIR = "catalogs"


class ProductCatalog(ABC):
    """Abstract interface — swap dummy for real APIs later."""

    @abstractmethod
    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        pass

    @abstractmethod
    def get_product(self, product_id: str) -> dict | None:
        pass

    @abstractmethod
    def check_stock(self, product_id: str) -> bool:
        pass

    @abstractmethod
    def get_all_products(self) -> list[dict]:
        pass


class DummyCatalog(ProductCatalog):
    """Loads products from JSON files."""

    def __init__(self):
        self.products: dict[str, dict] = {}
        self.stores: list[str] = []
        self._load_all()

    def _load_all(self):
        if not os.path.exists(CATALOGS_DIR):
            logger.warning(f"Catalogs dir not found: {CATALOGS_DIR}")
            return
        for fname in sorted(os.listdir(CATALOGS_DIR)):
            if fname.endswith(".json"):
                path = os.path.join(CATALOGS_DIR, fname)
                with open(path, "r") as f:
                    store_data = json.load(f)
                store_name = store_data.get("store_name", fname.replace(".json", ""))
                self.stores.append(store_name)
                for p in store_data.get("products", []):
                    p["store"] = store_name
                    self.products[p["id"]] = p
        logger.info(f"Loaded {len(self.products)} products from {len(self.stores)} stores")

    def search(self, query: str, filters: dict | None = None) -> list[dict]:
        query_lower = query.lower()
        results = []

        for p in self.products.values():
            # Match against name, brand, category, tags
            searchable = f"{p['name']} {p.get('brand','')} {p.get('category','')} {' '.join(p.get('tags',[]))}".lower()
            if query_lower in searchable or any(word in searchable for word in query_lower.split()):
                # Apply filters
                if filters:
                    if "color" in filters and filters["color"]:
                        if filters["color"].lower() not in [c.lower() for c in p.get("colors", [])]:
                            continue
                    if "color_exclude" in filters and filters["color_exclude"]:
                        if any(c.lower() in [pc.lower() for pc in p.get("colors", [])] for c in filters["color_exclude"]):
                            continue
                    if "brand" in filters and filters["brand"]:
                        if p.get("brand", "").lower() not in [b.lower() for b in filters["brand"]]:
                            continue
                    if "max_price" in filters and filters["max_price"]:
                        if p.get("price", 0) > filters["max_price"]:
                            continue
                    if "min_price" in filters and filters["min_price"]:
                        if p.get("price", 0) < filters["min_price"]:
                            continue
                results.append(p)

        # Sort by relevance (exact name match first, then brand match)
        results.sort(key=lambda p: (
            0 if query_lower in p["name"].lower() else 1,
            p.get("price", 0),
        ))
        return results[:10]  # Max 10 results

    def get_product(self, product_id: str) -> dict | None:
        return self.products.get(product_id)

    def check_stock(self, product_id: str) -> bool:
        p = self.products.get(product_id)
        return p.get("in_stock", False) if p else False

    def get_all_products(self) -> list[dict]:
        return list(self.products.values())

    def update_stock(self, product_id: str, in_stock: bool):
        """For testing — toggle stock status."""
        if product_id in self.products:
            self.products[product_id]["in_stock"] = in_stock


# Singleton
_catalog: DummyCatalog | None = None


def get_catalog() -> DummyCatalog:
    global _catalog
    if _catalog is None:
        _catalog = DummyCatalog()
    return _catalog
