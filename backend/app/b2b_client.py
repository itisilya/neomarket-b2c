import os
from typing import List, Dict, Any, Optional
from uuid import UUID

# Simulated B2B source database
# Note: In a real environment, this class will make HTTP requests to the B2B service
# using an HTTP client (e.g. httpx or requests) with the 'X-Service-Key' header.
class B2BClient:
    def __init__(self, service_key: str = "B2B_SECRET_KEY_PROD_2026"):
        self.service_key = service_key
        self.headers = {"X-Service-Key": self.service_key}
        self.simulate_outage = False

        # Raw B2B Database seeding
        # This simulates B2B-side data before applying standard filter rules
        # (status = MODERATED, deleted = false, in_stock / active_quantity > 0)
        self._categories = [
            {"id": UUID("e1010000-e29b-41d4-a716-446655440001"), "name": "Электроника (Каналы)", "slug": "electronics", "parent_id": None},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440002"), "name": "Технологии & IT", "slug": "it-tech", "parent_id": None},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440003"), "name": "Искусственный интеллект", "slug": "ai-news", "parent_id": UUID("e1010000-e29b-41d4-a716-446655440002")},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440004"), "name": "Разработка ПО", "slug": "software-dev", "parent_id": UUID("e1010000-e29b-41d4-a716-446655440002")},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440005"), "name": "Бизнес & Финансы", "slug": "business-finance", "parent_id": None},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440006"), "name": "Криптовалюты", "slug": "crypto", "parent_id": UUID("e1010000-e29b-41d4-a716-446655440005")},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440007"), "name": "Развлечения & Юмор", "slug": "humor-ent", "parent_id": None},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440008"), "name": "Мемы", "slug": "memes", "parent_id": UUID("e1010000-e29b-41d4-a716-446655440007")},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440009"), "name": "Образование & Наука", "slug": "education", "parent_id": None},
            {"id": UUID("e1010000-e29b-41d4-a716-446655440010"), "name": "Иностранные языки", "slug": "languages", "parent_id": UUID("e1010000-e29b-41d4-a716-446655440009")}
        ]

        self._products = [
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440001"),
                "title": "Crypto Whale Alerts 🐳",
                "slug": "crypto-whale-alerts",
                "description": "Раздел аналитики криптовалютных рынков и крупных транзакций. Стабильный доход со спансорских постов, высокая вовлеченность трейдеров и крипто-энтузиастов.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440006"),
                "price": 15000000,
                "old_price": 18000000,
                "subscribers": 42000,
                "monthly_income": 25000000,
                "er": 14.5,
                "verified": True,
                "rating": 4.8,
                "reviews_count": 24,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 100,
                "seller": {"id": "s1111111-e29b-41d4-a716-446655440001", "display_name": "Григорий Криптатов"},
                "images": [
                    {"id": "img1", "url": "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [
                    {"name": "Тематика", "value": "Криптовалюты"},
                    {"name": "Язык аудитории", "value": "Русский"}
                ],
                "skus": [
                    {"id": UUID("00000000-0000-0000-0000-000000000001"), "name": "Полная передача прав (Базовый)", "sku_code": "TG-WHALE-BASE", "price": 15000000, "available_quantity": 100, "images": []}
                ]
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440002"),
                "title": "IT Career Roadmap 🚀",
                "slug": "it-career-roadmap",
                "description": "Ведущий образовательный ресурс для начинающих программистов. Интегрированная CPA-сеть вакансий и курсов приносит стабильный пассивный доход.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440004"),
                "price": 39000000,
                "old_price": 45000000,
                "subscribers": 87000,
                "monthly_income": 80000000,
                "er": 18.2,
                "verified": True,
                "rating": 4.9,
                "reviews_count": 53,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 3,
                "seller": {"id": "s1111111-e29b-41d4-a716-446655440002", "display_name": "Dev Академия"},
                "images": [
                    {"id": "img3", "url": "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [
                    {"name": "Тематика", "value": "IT-образование"}
                ],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440003"),
                "title": "Бизнес Формула 📝",
                "slug": "business-formula",
                "description": "Канал с цитатами, кейсами крупных предпринимателей и экспертными статьями по маркетингу. Аудитория взрослая, платежеспособная.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440005"),
                "price": 8000000,
                "old_price": None,
                "subscribers": 15000,
                "monthly_income": 15000000,
                "er": 8.4,
                "verified": False,
                "rating": 4.1,
                "reviews_count": 12,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 2,
                "seller": {"id": "s1111111-e29b-41d4-a716-446655440003", "display_name": "Иван Смирнов"},
                "images": [
                    {"id": "img5", "url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440004"),
                "title": "Meme Hub Ru 🎭",
                "slug": "meme-hub-ru",
                "description": "Крупнейший развлекательный канал с вирусными картинками и короткими видео. Огромные охваты и автоматические продажи рекламы.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440008"),
                "price": 45000000,
                "old_price": 52000000,
                "subscribers": 120000,
                "monthly_income": 120000000,
                "er": 22.1,
                "verified": False,
                "rating": 4.5,
                "reviews_count": 67,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 1,
                "seller": {"id": "s1111111-e29b-41d4-a716-446655440011", "display_name": "Юмор Медиа"},
                "images": [
                    {"id": "img6", "url": "https://images.unsplash.com/photo-1511512578047-dfb367046420?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440005"),
                "title": "AI Explorer (Нейросети) 🧠",
                "slug": "ai-explorer",
                "description": "Канал-первооткрыватель в сфере Сравнительных Обзоров ИИ, генераций Midjourney и новостей технологий Open AI. Самая трендовая ниша этого года.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440003"),
                "price": 21000000,
                "old_price": None,
                "subscribers": 31000,
                "monthly_income": 45000000,
                "er": 15.2,
                "verified": True,
                "rating": 4.7,
                "reviews_count": 19,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 4,
                "seller": {"id": "s1111111-e29b-41d4-a716-446655440005", "display_name": "Future AI Lab"},
                "images": [
                    {"id": "img7", "url": "https://images.unsplash.com/photo-1677442136019-21780efad99a?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440006"),
                "title": "English Every Day 🇬🇧",
                "slug": "english-every-day",
                "description": "Популярный обучающий интерактив по изучению английского языка. Зарабатывает на рекламе курсов, репетиторов и разговорных клубов.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440010"),
                "price": 28000000,
                "old_price": 33000000,
                "subscribers": 95000,
                "monthly_income": 50000000,
                "er": 9.8,
                "verified": True,
                "rating": 4.6,
                "reviews_count": 41,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 5,
                "seller": {"id": "s1111111-e29b-41d4-a716-446655440006", "display_name": "Polyglot Hub"},
                "images": [
                    {"id": "img8", "url": "https://images.unsplash.com/photo-1544717305-2782549b5136?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655d40011"),
                "title": "Crypto Signals Premium 📈",
                "slug": "crypto-signals-premium",
                "description": "Лучшие торговые сигналы, технический анализ и обучающие материалы по трейдингу. Высокая вовлеченность платежеспособных инвесторов.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440006"),
                "price": 12000000,
                "old_price": 14500000,
                "subscribers": 25000,
                "monthly_income": 18000000,
                "er": 11.2,
                "verified": True,
                "rating": 4.7,
                "reviews_count": 14,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 1,
                "images": [
                    {"id": "img_signals", "url": "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655d40012"),
                "title": "DeFi INSIDER 🔗",
                "slug": "defi-insider",
                "description": "Глубокая аналитика рынка децентрализованных финансов, ликвидности, стейкинга и венчурных раундов на ранних стадиях.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440006"),
                "price": 18000000,
                "old_price": None,
                "subscribers": 31000,
                "monthly_income": 22000000,
                "er": 13.4,
                "verified": False,
                "rating": 4.5,
                "reviews_count": 9,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 2,
                "images": [
                    {"id": "img_defi", "url": "https://images.unsplash.com/photo-1639762681485-074b7f938ba0?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655d40013"),
                "title": "Python Cheat Sheets 🐍",
                "slug": "python-cheat-sheets",
                "description": "Ежедневные шпаргалки по Python, разборы лучших практик, регулярные выражения, работа с популярными библиотеками.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440004"),
                "price": 9500000,
                "old_price": 11000000,
                "subscribers": 42000,
                "monthly_income": 12000000,
                "er": 15.5,
                "verified": True,
                "rating": 4.8,
                "reviews_count": 31,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 2,
                "images": [
                    {"id": "img_python", "url": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655d40021"),
                "title": "Deutsch Online 🇩🇪",
                "slug": "deutsch-online",
                "description": "Крупный образовательный проект по изучению немецкого языка от А1 до С1. Стабильная монетизация рекламой языковых школ.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440010"),
                "price": 11200000,
                "old_price": 13000000,
                "subscribers": 34000,
                "monthly_income": 8500000,
                "er": 10.4,
                "verified": True,
                "rating": 4.7,
                "reviews_count": 14,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 3,
                "images": [
                    {"id": "img_deutsch", "url": "https://images.unsplash.com/photo-1527891751199-7225231a68dd?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655d40022"),
                "title": "English Grammar Hacks 📝",
                "slug": "english-grammar-hacks",
                "description": "Полезный канал с карточками и шпаргалками по грамматике английского языка. Интерактивные тесты и высокая активность.",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440010"),
                "price": 8500000,
                "old_price": None,
                "subscribers": 19000,
                "monthly_income": 4000000,
                "er": 12.1,
                "verified": False,
                "rating": 4.4,
                "reviews_count": 8,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 2,
                "images": [
                    {"id": "img_grammar", "url": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=600&auto=format&fit=crop&q=80", "ordering": 0, "is_main": True}
                ],
                "characteristics": [],
                "skus": []
            },
            # Edge Cases Draft channels to test filtering
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440099"),
                "title": "Draft Channel 📝",
                "slug": "draft-channel",
                "description": "Not moderated channel",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440006"),
                "price": 500000,
                "subscribers": 100,
                "monthly_income": 0,
                "er": 1.0,
                "verified": False,
                "rating": 0.0,
                "in_stock": True,
                "status": "DRAFT",
                "deleted": False,
                "active_quantity": 1,
                "seller": None,
                "images": [],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440098"),
                "title": "Deleted Channel ❌",
                "slug": "deleted-channel",
                "description": "Deleted channel",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440006"),
                "price": 500000,
                "subscribers": 100,
                "monthly_income": 0,
                "er": 1.0,
                "verified": False,
                "rating": 0.0,
                "in_stock": True,
                "status": "MODERATED",
                "deleted": True,
                "active_quantity": 1,
                "seller": None,
                "images": [],
                "characteristics": [],
                "skus": []
            },
            {
                "id": UUID("770e8400-e29b-41d4-a716-446655440097"),
                "title": "Out of Stock Channel 👻",
                "slug": "out-of-stock-channel",
                "description": "No active quantity",
                "category_id": UUID("e1010000-e29b-41d4-a716-446655440006"),
                "price": 500000,
                "subscribers": 100,
                "monthly_income": 0,
                "er": 1.0,
                "verified": False,
                "rating": 0.0,
                "in_stock": False,
                "status": "MODERATED",
                "deleted": False,
                "active_quantity": 0,
                "seller": None,
                "images": [],
                "characteristics": [],
                "skus": []
            }
        ]

    def _check_auth(self, headers: Dict[str, str]):
        # Simulate standard service token check
        auth_key = headers.get("X-Service-Key")
        if not auth_key or auth_key != self.service_key:
            raise Exception("Unauthorized B2B access: Invalid X-Service-Key")

    def fetch_categories(self, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        if self.simulate_outage:
            raise Exception("B2B Connection Failed")
        self._check_auth(headers)
        return self._categories

    def fetch_products(self, headers: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Simulates retrieval from B2B with strict visibility filters applied on B2B-side.
        Criteria: status = MODERATED AND deleted = false AND active_quantity > 0.
        """
        if self.simulate_outage:
            raise Exception("B2B Connection Failed")
        self._check_auth(headers)

        # Apply B2B database rule filtering
        visible_set = []
        for p in self._products:
            if p["status"] == "MODERATED" and not p["deleted"] and p["active_quantity"] > 0:
                visible_set.append(p)
        return visible_set
