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
