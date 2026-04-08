"""Mock data for demo — replaces real PayPal API calls."""

MOCK_USER = {
    "name": "",  # Set dynamically from login
    "email": "",  # Set dynamically from login
    "initials": "",
    "tenure_months": 36,
    "credit_band": "prime",
    "monthly_spend": 4200,
}

MOCK_TRANSACTIONS = [
    {"icon": "👟", "name": "Nike.com", "category": "Sports & Fitness", "amount": "-$129.00", "date": "Apr 1"},
    {"icon": "🍔", "name": "Uber Eats", "category": "Food & Drink", "amount": "-$24.50", "date": "Mar 30"},
    {"icon": "📦", "name": "Amazon", "category": "Shopping", "amount": "-$67.99", "date": "Mar 28"},
    {"icon": "☕", "name": "Starbucks", "category": "Coffee", "amount": "-$8.75", "date": "Mar 27"},
    {"icon": "🎵", "name": "Spotify", "category": "Subscriptions", "amount": "-$9.99", "date": "Mar 25"},
    {"icon": "🛒", "name": "Target", "category": "Shopping", "amount": "-$45.20", "date": "Mar 23"},
    {"icon": "🎬", "name": "Netflix", "category": "Subscriptions", "amount": "-$15.99", "date": "Mar 20"},
    {"icon": "💳", "name": "PayPal Credit", "category": "Payment Received", "amount": "+$200.00", "date": "Mar 15", "credit": True},
]

MOCK_BALANCE = {
    "current_balance": "$847.23",
    "available_credit": "$1,652.77",
    "credit_limit": "$2,500",
    "due_date": "Apr 15",
    "min_payment": "$25.00",
    "utilization": "33.9%",
}

MOCK_CARD = {
    "number_masked": "•••• •••• •••• 4821",
    "number_full": "4821 0043 8812 4821",
    "cvv_masked": "•••",
    "cvv_full": "847",
    "holder": "",  # Set dynamically from login
    "expiry": "09/28",
    "product": "PayPal Pay Later",
    "controls": {
        "online": True,
        "international": False,
        "contactless": True,
        "alerts": True,
    },
}

MOCK_REWARDS = {
    "total_cashback": "$114.20",
    "points": 42180,
    "tier": "Silver",
    "next_milestone": "7,820 pts to Gold",
}

MOCK_PORTFOLIO = {
    "total_credit": "$42,000",
    "total_balance": "$3,820",
    "utilization": "9.1%",
    "rewards_ytd": "$698",
    "cards": [
        {
            "name": "PayPal Miles+",
            "number": "•••• 4821",
            "limit": "$22,000",
            "balance": "$3,240",
            "available": "$18,760",
            "utilization": "14.7%",
            "rewards": "42,180 miles",
            "earn_rates": {"travel": "3x", "dining": "2x", "groceries": "1x", "other": "1x"},
            "nudge": "7,820 miles from a free Mumbai–Dubai return. Spend $260 more on travel.",
        },
        {
            "name": "PayPal Everyday Cash",
            "number": "•••• 9203",
            "limit": "$20,000",
            "balance": "$580",
            "available": "$19,420",
            "utilization": "2.9%",
            "rewards": "$114.20 cashback",
            "earn_rates": {"travel": "1%", "dining": "2%", "groceries": "2%", "other": "2%"},
            "nudge": "Use this card for groceries — Miles+ only earns 1x there, Everyday Cash earns 2%.",
        },
    ],
    "spend_breakdown": {
        "travel": {"annual": 4200, "miles_earn": 0.05, "cash_earn": 0.02},
        "dining": {"annual": 2800, "miles_earn": 0.03, "cash_earn": 0.02},
        "shopping": {"annual": 3600, "miles_earn": 0.02, "cash_earn": 0.02},
        "other": {"annual": 1800, "miles_earn": 0.01, "cash_earn": 0.02},
    },
}

MOCK_COLLECTIONS = {
    "case_id": "C-2024-00391",
    "customer": "Account holder",
    "card": "PayPal Miles+ ••••3847",
    "overdue_amount": "$1,240",
    "minimum_due": "$148",
    "days_past_due": 61,
    "hardship_flag": "Possible — spend dropped 60%",
    "human_escalation": "Auto at Day 90 if unresolved",
    "options": {
        "A": {"name": "Minimum today", "detail": "Pay $148 minimum — freeze interest for 90 days"},
        "B": {"name": "3-month instalments", "detail": "$415/month · 0% interest · starts next month"},
        "C": {"name": "Lump sum settlement", "detail": "Pay $800 now — 35% reduction"},
    },
}
