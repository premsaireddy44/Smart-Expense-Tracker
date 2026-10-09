import re

# Category name -> keywords that signal it. Names must match your categories table.
KEYWORDS = {
    "Food": ["swiggy", "zomato", "restaurant", "cafe", "coffee", "tea", "pizza", "burger",
             "dominos", "domino", "mcdonalds", "mcdonald", "kfc", "starbucks", "lunch",
             "dinner", "breakfast", "biryani", "snack", "snacks", "dining", "takeaway",
             "uber eats", "ubereats"],
    "Groceries": ["grocery", "groceries", "bigbasket", "blinkit", "zepto", "instamart",
                  "supermarket", "vegetables", "vegetable", "fruit", "fruits", "milk",
                  "dmart", "tesco", "lidl", "aldi", "sainsburys"],
    "Rent": ["rent", "landlord", "hostel", "pg"],
    "Utilities": ["electricity", "water bill", "gas bill", "internet", "wifi", "broadband",
                  "recharge", "mobile recharge", "phone bill", "jio", "airtel", "vodafone"],
    "Transport": ["uber", "ola", "rapido", "auto", "taxi", "cab", "bus", "metro", "train",
                  "petrol", "fuel", "diesel", "parking", "toll", "tube", "oyster"],
    "Travel": ["flight", "hotel", "airbnb", "makemytrip", "irctc", "booking", "vacation",
               "trip", "visa", "holiday", "train ticket"],
    "Entertainment": ["movie", "cinema", "bookmyshow", "concert", "gaming", "game", "pub",
                      "club", "party"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "meesho", "clothes", "shoes",
                 "shopping", "mall", "electronics"],
    "Health": ["doctor", "hospital", "pharmacy", "medicine", "medical", "clinic", "dentist",
               "apollo", "gym", "lab test"],
    "Education": ["tuition", "school", "college", "fees", "course", "udemy", "coursera",
                  "books", "exam", "university", "textbook"],
    "Insurance": ["insurance", "lic"],
    "Subscriptions": ["netflix", "spotify", "prime", "youtube premium", "hotstar",
                      "subscription", "icloud", "chatgpt", "amazon prime"],
    "Gifts & Donations": ["gift", "donation", "charity", "birthday", "wedding"],
    "Personal Care": ["salon", "haircut", "spa", "grooming", "skincare", "barber"],
    "Salary": ["salary", "payroll", "wages", "stipend", "paycheck", "bonus"],
    "Freelance Income": ["freelance", "client payment", "invoice", "consulting",
                         "project payment"],
    "Investments": ["dividend", "interest", "mutual fund", "capital gains", "returns"],
}

INCOME_CATEGORIES = {"Salary", "Freelance Income", "Investments"}


def clean(text: str) -> str:
    text = text.lower()
    text = re.sub(r"['\u2019]", "", text)          # Domino's -> dominos
    text = re.sub(r"[^a-z0-9]+", " ", text)        # punctuation -> spaces
    return f" {text.strip()} "                     # padded so whole words match


def suggest_category(description: str, tx_type: str):
    """Return a category name, or None if nothing matches."""
    text = clean(description)
    want_income = str(getattr(tx_type, "value", tx_type)) == "income"

    best_name = None
    best_length = 0
    for name, words in KEYWORDS.items():
        if (name in INCOME_CATEGORIES) != want_income:
            continue                                # income only matches income categories
        for word in words:
            if f" {clean(word).strip()} " in text and len(word) > best_length:
                best_name = name
                best_length = len(word)             # longest keyword wins
    return best_name