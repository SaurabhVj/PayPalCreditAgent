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
        """Smart broad search — uses word matching with category awareness."""
        query_lower = query.lower().strip()
        query_words = [w for w in query_lower.split() if len(w) > 1]

        if not query_words:
            return []

        # Detect if query includes a category keyword
        category_keywords = {
            "shoes": "shoes", "shoe": "shoes", "sneakers": "shoes", "footwear": "shoes",
            "clothing": "clothing", "clothes": "clothing", "shirt": "clothing", "tshirt": "clothing",
            "t-shirt": "clothing", "jeans": "clothing", "pants": "clothing", "jacket": "clothing",
            "shorts": "clothing",
            "electronics": "electronics", "phone": "electronics", "laptop": "electronics",
            "headphones": "electronics", "tablet": "electronics", "watch": "electronics",
            "baby": "baby", "diapers": "baby", "stroller": "baby",
            "groceries": "groceries", "grocery": "groceries", "food": "groceries",
            "home": "home", "kitchen": "home", "vacuum": "home",
            "accessories": "accessories", "sunglasses": "accessories",
            "dining": "dining", "coffee": "dining",
        }

        required_category = None
        brand_words = []
        product_words = []

        for word in query_words:
            if word in category_keywords:
                required_category = category_keywords[word]
            else:
                # Could be brand or product name
                product_words.append(word)

        results = []
        for p in self.products.values():
            searchable = f"{p['name']} {p.get('brand','')} {' '.join(p.get('tags',[]))}".lower()
            category = p.get("category", "").lower()

            # If category is specified, enforce it
            if required_category and category != required_category:
                # Exception: some tags might match the category
                tags = [t.lower() for t in p.get("tags", [])]
                if required_category not in tags and required_category not in searchable:
                    continue

            # Match remaining words against product
            if product_words:
                if not any(word in searchable for word in product_words):
                    continue
            elif not required_category:
                # No product words, no category — match any word
                if not any(word in searchable for word in query_words):
                    continue

            # Apply filters
            if filters:
                if "color" in filters and filters["color"]:
                    if filters["color"].lower() not in [c.lower() for c in p.get("colors", [])]:
                        continue
                if "color_exclude" in filters and filters["color_exclude"]:
                    if any(c.lower() in [pc.lower() for pc in p.get("colors", [])] for c in filters["color_exclude"]):
                        continue

            results.append(p)

        return results[:15]


    def get_candidates_summary(self, products: list[dict]) -> str:
        """Format candidates for LLM reranking."""
        lines = []
        for p in products:
            lines.append(f"ID:{p['id']} | {p['name']} | {p.get('brand','')} | ${p['price']} | {p.get('category','')} | tags:{','.join(p.get('tags',[]))} | {'in_stock' if p.get('in_stock') else 'out_of_stock'}")
        return "\n".join(lines)

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
