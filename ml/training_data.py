"""Training examples for the category model.

Each category has a list of short phrases: the kind of thing a person types, or a bank
statement shows. make_examples() wraps them in everyday wording ("paid", "upi") and in
bank-statement style ("CARD PAYMENT TO ... LONDON GB"), adds typos and capital letters,
and adds an "Unknown" class made of text that carries no clue (names, junk, vague words).

These examples are manufactured, so they only teach the model the basics. The model gets
better as it also learns from the user's own corrected transactions (see train_model.py).
"""
import random

PHRASES = {
    'Food': [
        'swiggy', 'zomato', 'restaurant dinner', 'cafe coffee', 'lunch with friends', 'dominos pizza',
        'mcdonalds burger', 'kfc chicken', 'starbucks latte', 'biryani', 'tea and snacks', 'breakfast at hotel',
        'uber eats', 'deliveroo', 'just eat', 'pret a manger sandwich', 'greggs', 'nandos', 'wagamama',
        'costa coffee', 'subway sandwich', 'dosa and chai', 'street food', 'canteen lunch', 'takeaway curry',
        'ice cream', 'bakery cake', 'thali meal', 'chinese takeaway', 'burger king', 'pizza hut', 'five guys',
        'lunch', 'dinner', 'brunch', 'food order', 'snacks', 'juice shop', 'chai', 'samosa', 'maggi noodles', 'kebab',
        'rolls', 'idli sambar', 'pav bhaji', 'chaat', 'momos', 'sushi', 'ramen', 'noodles', 'chicken wings',
        'fried chicken', 'sandwich', 'wrap', 'salad bowl', 'dessert', 'pastry', 'bagel', 'smoothie', 'milkshake',
        'barbeque nation', 'cafe coffee day', 'itsu', 'leon', 'chipotle', 'taco bell', 'papa johns', 'dunkin',
        'krispy kreme', 'eating out', 'restaurant bill', 'food court', 'mess fees', 'tiffin service', 'office lunch',
        'team dinner', 'coffee with friend', 'juice', 'dhaba', 'bar and grill', 'curry house', 'burger and fries',
        'pizza night',
    ],
    'Groceries': [
        'bigbasket', 'blinkit', 'zepto', 'instamart', 'dmart', 'tesco', 'lidl', 'aldi', 'sainsburys', 'asda',
        'morrisons', 'waitrose', 'co-op food', 'vegetables', 'fruits and milk', 'grocery shopping', 'supermarket',
        'weekly shop', 'kirana store', 'eggs bread milk', 'rice and dal', 'reliance fresh', 'more supermarket',
        'ocado', 'milk delivery', 'fresh vegetables market', 'monthly groceries', 'atta oil sugar', 'supermarket run',
        'veggies', 'fruit and vegetable shop', 'bread and eggs', 'daily needs store', 'provision store', 'grofers',
        'amazon fresh', 'natures basket', 'star bazaar', 'spar', 'iceland foods', 'marks and spencer food',
        'farm shop', 'butcher', 'fish market', 'rice bag', 'lentils', 'cooking oil', 'tea powder and sugar',
        'household essentials', 'toilet paper and detergent', 'cleaning supplies', 'dairy products', 'yoghurt',
        'cereal', 'pasta and sauce', 'big bazaar', 'weekly food shopping', 'co op',
    ],
    'Rent': [
        'monthly rent', 'house rent', 'room rent', 'landlord payment', 'pg rent', 'hostel fees', 'flat rent',
        'rent for october', 'accommodation rent', 'rent transfer to landlord', 'studio rent', 'deposit rent',
        'student accommodation', 'halls rent', 'rent payment', 'rent november', 'rent for the room',
        'housing payment', 'accommodation payment', 'lease payment', 'tenancy payment', 'security deposit',
        'broker fee flat', 'maintenance charges flat', 'society maintenance', 'paying guest', 'shared flat rent',
        'landlord transfer', 'rent to owner', 'monthly lodging', 'dorm fees', 'residence hall',
        'rent split with roommate', 'nobroker rent', 'rent due',
    ],
    'Utilities': [
        'electricity bill', 'water bill', 'gas bill', 'broadband bill', 'wifi recharge', 'mobile recharge',
        'phone bill', 'jio recharge', 'airtel postpaid', 'vodafone', 'british gas', 'octopus energy', 'thames water',
        'council tax', 'bt broadband', 'sky broadband', 'internet bill', 'lpg cylinder', 'dth recharge', 'o2 mobile',
        'ee mobile plan', 'three mobile', 'energy bill', 'bses bill', 'electric bill', 'power bill', 'bescom', 'tneb',
        'water supply charges', 'gas connection', 'png gas', 'indane gas', 'cooking gas', 'prepaid mobile',
        'postpaid bill', 'data pack', 'sim recharge', 'internet plan', 'fibre broadband', 'act fibernet', 'hathway',
        'tata sky', 'dish tv', 'sky tv', 'tv licence', 'utility bill', 'eon energy', 'edf energy', 'scottish power',
        'severn trent', 'virgin media', 'gas and electricity', 'water rates', 'phone top up',
    ],
    'Transport': [
        'uber ride', 'ola cab', 'rapido bike', 'auto rickshaw', 'taxi fare', 'bus ticket', 'metro card recharge',
        'train fare', 'petrol', 'diesel fuel', 'parking fee', 'toll charge', 'tube fare', 'oyster top up',
        'tfl travel', 'bolt ride', 'national rail commute', 'monthly bus pass', 'bike service', 'car fuel',
        'contactless tfl', 'railcard', 'cab to office', 'uber', 'ola', 'uber trip', 'ola ride', 'rapido', 'auto fare',
        'rickshaw', 'cab fare', 'taxi to station', 'bus fare', 'metro ticket', 'local train pass', 'monthly pass',
        'petrol bunk', 'fuel station', 'shell petrol', 'bp fuel', 'car wash', 'bike repair', 'vehicle service',
        'cycle hire', 'lime scooter', 'santander cycles', 'congestion charge', 'ulez charge', 'tram fare',
        'season ticket', 'national express coach', 'flixbus', 'redbus', 'ride share', 'toll plaza', 'bus', 'metro',
        'train',
    ],
    'Travel': [
        'flight tickets', 'hotel booking', 'airbnb stay', 'makemytrip', 'irctc ticket', 'vacation trip', 'visa fee',
        'holiday package', 'booking.com', 'ryanair', 'easyjet', 'british airways', 'goa trip',
        'train ticket to delhi', 'weekend getaway', 'travel insurance trip', 'airport transfer', 'luggage for trip',
        'cleartrip', 'skyscanner', 'hostel booking trip', 'eurostar', 'indigo flight', 'flight booking', 'air ticket',
        'air india', 'vistara', 'emirates', 'lufthansa', 'hotel stay', 'resort booking', 'oyo rooms', 'airbnb',
        'trip expenses', 'tour package', 'sightseeing tickets', 'tourist visa', 'passport renewal fee',
        'forex card trip', 'holiday homestay', 'backpacking', 'city break', 'cruise', 'booking flights',
        'travel agent', 'ticket to goa', 'vacation rental', 'hotel', 'flight', 'trip', 'holiday',
    ],
    'Entertainment': [
        'movie tickets', 'cinema', 'bookmyshow', 'concert tickets', 'gaming', 'steam game', 'playstation',
        'pub night', 'club entry', 'party', 'bowling', 'theme park', 'odeon', 'vue cinema', 'comedy show',
        'board games', 'football match tickets', 'karaoke', 'arcade', 'museum entry', 'escape room', 'movie night',
        'multiplex', 'imax tickets', 'theatre show', 'live gig', 'music festival', 'nightclub cover', 'bar tab',
        'drinks with friends', 'game purchase', 'steam wallet', 'arcade tokens', 'go karting', 'trampoline park',
        'paintball', 'zoo tickets', 'amusement park', 'sports event', 'cricket match ticket', 'ipl tickets',
        'west end theatre', 'stand up show', 'magic show', 'snooker', 'pool hall', 'karaoke night', 'movie', 'movies',
        'night out', 'fun',
    ],
    'Shopping': [
        'amazon order', 'flipkart', 'myntra', 'ajio', 'meesho', 'clothes', 'new shoes', 'shopping mall',
        'electronics', 'headphones', 'primark', 'zara', 'h&m', 'next clothing', 'argos', 'ikea furniture',
        'phone cover', 'laptop bag', 'uniqlo', 'nike store', 'tshirt', 'jeans', 'backpack', 'ebay purchase', 'croma',
        'decathlon', 'home decor', 'online shopping', 'amazon purchase', 'amazon co uk', 'ebay', 'etsy', 'shein',
        'h and m', 'marks and spencer clothing', 'tk maxx', 'john lewis', 'currys', 'apple store', 'samsung phone',
        'laptop', 'keyboard and mouse', 'gadget', 'watch', 'sunglasses', 'handbag', 'sneakers', 'kurta', 'saree',
        'dress', 'jacket', 'winter wear', 'socks', 'furniture', 'bedsheets', 'kitchenware', 'home appliances',
        'lifestyle store', 'westside', 'pantaloons', 'shopping',
    ],
    'Health': [
        'doctor visit', 'hospital bill', 'pharmacy', 'medicines', 'medical store', 'clinic fee', 'dentist', 'apollo',
        'gym membership', 'lab test', 'boots pharmacy', 'nhs prescription', 'eye test glasses', 'physiotherapy',
        'vitamins', 'health checkup', 'blood test', 'optician', 'netmeds', '1mg order', 'doctor appointment',
        'gp private', 'consultation fee', 'pharmacy bill', 'chemist', 'tablets', 'prescription medicines',
        'cough syrup', 'dental check', 'teeth cleaning', 'orthodontist', 'eye doctor', 'spectacles', 'contact lenses',
        'physio', 'chiropractor', 'therapy session', 'counselling session', 'gym fee', 'yoga class',
        'fitness membership', 'cult fit', 'protein supplement', 'x-ray', 'scan', 'diagnostic centre', 'path lab',
        'vaccination', 'health supplements', 'gym',
    ],
    'Education': [
        'tuition fees', 'school fees', 'college fees', 'online course', 'udemy', 'coursera', 'books', 'exam fee',
        'university fees', 'textbook', 'stationery', 'ielts exam', 'gre registration', 'library fine',
        'coding bootcamp', 'notebooks pens', 'course material', 'language classes', 'student loan payment',
        'pearson exam', 'tuition payment', 'college tuition', 'semester fee', 'admission fee',
        'application fee university', 'ucas fee', 'coaching fees', 'tutor fees', 'online class subscription',
        'udacity', 'edx', 'datacamp', 'certification exam', 'toefl fee', 'pte exam', 'gmat registration',
        'study material', 'reference books', 'lab manual', 'printing assignments', 'course enrollment',
        'workshop fee', 'hackathon registration', 'tuition', 'course', 'exam',
    ],
    'Insurance': [
        'insurance premium', 'lic premium', 'health insurance', 'car insurance', 'life insurance',
        'term plan premium', 'bike insurance', 'home insurance', 'aviva', 'admiral insurance', 'star health premium',
        'policy renewal', 'student health surcharge', 'gadget insurance', 'insurance premium paid', 'policy payment',
        'premium instalment', 'hdfc life', 'icici prudential', 'sbi life', 'max life', 'bajaj allianz', 'tata aig',
        'lv insurance', 'direct line', 'aviva policy', 'bupa', 'axa health', 'legal and general', 'vehicle insurance',
        'two wheeler insurance', 'mediclaim', 'life cover', 'home contents insurance', 'pet insurance',
        'gadget cover', 'annual policy renewal', 'insurance',
    ],
    'Subscriptions': [
        'netflix', 'spotify', 'amazon prime', 'youtube premium', 'hotstar', 'icloud storage', 'chatgpt plus',
        'disney plus', 'apple music', 'monthly subscription', 'annual membership', 'linkedin premium', 'notion plan',
        'google one', 'audible', 'xbox game pass', 'adobe creative cloud', 'dropbox', 'prime video', 'sony liv',
        'zee5', 'github copilot', 'netflix subscription', 'hulu', 'hbo max', 'paramount plus', 'apple tv', 'now tv',
        'sky sports pass', 'ps plus', 'nintendo online', 'microsoft 365', 'office 365', 'canva pro', 'grammarly',
        'medium membership', 'substack', 'patreon', 'duolingo plus', 'headspace', 'calm app', 'strava',
        'vpn subscription', 'nordvpn', '1password', 'icloud plus', 'youtube music', 'jiosaavn', 'gaana',
        'audible membership', 'kindle unlimited', 'newspaper subscription', 'the hindu digital',
        'subscription renewal',
    ],
    'Gifts & Donations': [
        'birthday gift', 'wedding gift', 'donation', 'charity', 'gift for mom', 'diwali gifts', 'temple donation',
        'red cross', 'cancer research donation', 'flowers for friend', 'anniversary present', 'gift card',
        'christmas presents', 'ngo contribution', 'baby shower gift', 'shagun envelope', 'present for friend',
        'gift hamper', 'birthday cake and gift', 'wedding contribution', 'shagun', 'rakhi gifts', 'christmas gift',
        'festival gifts', 'baby gift', 'housewarming gift', 'charitable donation', 'give india', 'ngo donation',
        'temple offering', 'church donation', 'gurudwara donation', 'crowdfunding contribution', 'gofundme',
        'bouquet', 'greeting cards', 'gift voucher', 'secret santa', 'gift', 'gifts',
    ],
    'Personal Care': [
        'salon', 'haircut', 'spa', 'grooming', 'skincare products', 'barber', 'beard trim', 'facial', 'nail salon',
        'perfume', 'shampoo and soap', 'waxing', 'massage', 'cosmetics', 'nykaa order', 'toothpaste razor',
        'moisturiser', 'hair colour', 'salon bill', 'hair cut', 'hair spa', 'hair styling', 'manicure', 'pedicure',
        'threading', 'eyebrows', 'bridal makeup', 'grooming kit', 'razor blades', 'shaving cream', 'face cream',
        'sunscreen', 'body lotion', 'lipstick', 'makeup products', 'sephora', 'the body shop', 'lush', 'mamaearth',
        'wellness spa', 'ayurvedic massage', 'trimmer', 'skincare',
    ],
    'Salary': [
        'salary credited', 'monthly salary', 'payroll', 'wages', 'stipend', 'paycheck', 'bonus', 'salary october',
        'company salary credit', 'part time wages', 'internship stipend', 'overtime pay', 'net pay',
        'salary from employer', 'incentive payout', 'salary for the month', 'net salary credited', 'pay slip credit',
        'company payout', 'monthly pay', 'paycheque', 'stipend credited', 'research assistant pay',
        'teaching assistant pay', 'part time job pay', 'shift pay', 'overtime', 'performance bonus', 'festival bonus',
        'arrears', 'salary advance', 'employer payment', 'payroll credit', 'wages credited', 'tcs salary',
        'infosys salary', 'nhs pay', 'salary',
    ],
    'Freelance Income': [
        'freelance payment', 'client payment', 'invoice paid', 'consulting fee', 'project payment', 'upwork payout',
        'fiverr earnings', 'design work payment', 'website project client', 'tutoring income', 'contract work',
        'gig payment', 'freelance project', 'writing assignment payment', 'freelance income',
        'freelance invoice payment', 'side project income', 'client invoice settled', 'consulting payment',
        'gig earnings', 'contract payment', 'design project payout', 'development project payment',
        'content writing payment', 'translation job payment', 'photography shoot payment', 'tutoring fees received',
        'teaching income', 'payoneer', 'paypal payment received freelance', 'wise transfer client',
        'freelancer payout', 'fiverr payout', 'toptal payout', 'stripe payout', 'freelance',
    ],
    'Investments': [
        'dividend', 'interest credited', 'mutual fund returns', 'capital gains', 'fd interest', 'stock sale',
        'sip returns', 'savings account interest', 'bond interest', 'crypto sale profit', 'etf dividend',
        'share profit', 'rent from property', 'returns on investment', 'dividend received', 'interest income',
        'fixed deposit interest', 'fd maturity', 'rd maturity', 'mutual fund redemption', 'sip redemption',
        'stock profit', 'shares sold', 'trading profit', 'bond income', 'coupon payment', 'savings interest',
        'bank interest credited', 'ppf interest', 'nps returns', 'isa interest', 'premium bonds prize',
        'rental income', 'etf gains', 'crypto profit', 'gold sale', 'interest', 'returns',
    ],
}

# Text with no clue about the category. The model learns "no clue -> do not guess".
UNKNOWN_WORDS = [
    "payment", "transfer", "misc", "miscellaneous", "other", "bill", "cash", "upi", "paid", "expense",
    "money sent", "withdrawal", "atm withdrawal", "adjustment", "refund", "test", "temp", "stuff",
    "things", "general", "card payment", "bank transfer", "sent to friend", "returned", "balance",
    "fee", "charge", "purchase", "order", "online payment", "pos", "debit", "credit", "ref",
    "deposit", "credited", "received", "amount", "money", "pay", "sent", "settlement",
]
PEOPLE = [
    "ramesh", "john smith", "priya", "amit kumar", "sarah", "rahul", "mohammed ali", "anita",
    "david", "suresh", "emma wilson", "vikram", "neha", "james", "kavya", "ravi", "sophie", "arjun",
    "mr gupta", "mrs rao", "deepak", "lucy", "tom", "farah", "sunita", "peter jones", "meera",
]
KEYBOARD_JUNK = ["asdf", "qwer", "zxcv", "qzxv", "wplk", "hjkl", "xyz", "abc", "aaa", "lorem", "poiu", "mnbv", "asdfgh", "zzz"]
BARE_STATEMENT_LINES = [
    "CARD PAYMENT {n4} LONDON GB", "UPI-{n10}@okaxis", "NEFT {n6}", "POS {n4}", "TXN REF {n6}",
    "ATM CASH WITHDRAWAL", "IMPS {n6}", "FASTER PAYMENT {n6}", "DIRECT CREDIT {n6}", "CHEQUE {n6}",
]

PREFIX = ["", "", "", "paid ", "payment to ", "upi ", "card payment ", "pos ", "online ", "debit ", "to ",
          "bill - ", "txn ", "ref ", "monthly ", "my "]
SUFFIX = ["", "", "", "", " order", " payment", " bill", " 450", " rs 300", " 12.50", " ltd", " india", " uk",
          " london", " #2231", " ref 88231", " today", " online", " card", " upi"]

CITIES = ["LONDON", "MUMBAI", "DELHI", "BANGALORE", "MANCHESTER", "PUNE", "HYDERABAD", "LEEDS", "CHENNAI"]
BANKS = ["okhdfc", "okaxis", "ybl", "oksbi", "paytm", "icici"]
EXPENSE_STATEMENT = [
    "CARD PAYMENT TO {x} {city} GB", "POS {n4} {x}", "UPI-{x}-{n10}@{bank}", "UPI/{n10}/{x}",
    "DIRECT DEBIT {x}", "{x} *{n4}", "PAYMENT TO {x} REF {n4}", "{x} {city}", "{x} ORDER {n6}", "DEBIT {x} {n6}",
]
INCOME_STATEMENT = [
    "NEFT CR {x}", "BY TRANSFER {x}", "CREDIT {x} {n6}", "FASTER PAYMENT {x}", "IMPS {x} {n6}", "{x} CREDITED {n4}",
]


def digits(rng, n):
    return "".join(rng.choice("0123456789") for _ in range(n))


def as_statement_line(phrase, is_income, rng):
    template = rng.choice(INCOME_STATEMENT if is_income else EXPENSE_STATEMENT)
    return template.format(x=phrase.upper(), city=rng.choice(CITIES), bank=rng.choice(BANKS),
                           n4=digits(rng, 4), n6=digits(rng, 6), n10=digits(rng, 10))


def add_typo(text, rng):
    """Drop, swap or double one letter, like a fast typist."""
    if len(text) < 5:
        return text
    i = rng.randrange(1, len(text) - 1)
    kind = rng.choice(["drop", "swap", "double"])
    if kind == "drop":
        return text[:i] + text[i + 1:]
    if kind == "swap":
        return text[:i] + text[i + 1] + text[i] + text[i + 2:]
    return text[:i] + text[i] + text[i:]


INCOME_NAMES = {"Salary", "Freelance Income", "Investments"}


def make_examples(per_phrase=10, seed=1, extra=None, extra_copies=6):
    """Return (texts, labels).

    extra: optional list of (description, category) pairs from real users. They are repeated
    extra_copies times so that real examples count for more than manufactured ones.
    """
    rng = random.Random(seed)
    texts, labels = [], []
    for category, phrases in PHRASES.items():
        is_income = category in INCOME_NAMES
        for phrase in phrases:
            for _ in range(per_phrase):
                roll = rng.random()
                if roll < 0.25:
                    t = as_statement_line(phrase, is_income, rng)          # bank-statement style
                else:
                    t = rng.choice(PREFIX) + phrase + rng.choice(SUFFIX)  # everyday style
                    if rng.random() < 0.2:
                        t = add_typo(t, rng)
                    if rng.random() < 0.3:
                        t = t.upper() if rng.random() < 0.5 else t.title()
                texts.append(t)
                labels.append(category)

    # The "Unknown" class: vague words, names, keyboard junk and statement lines with no merchant.
    for _ in range(per_phrase * 22):
        kind = rng.random()
        if kind < 0.3:
            t = rng.choice(UNKNOWN_WORDS)
        elif kind < 0.5:
            t = rng.choice(PEOPLE)
        elif kind < 0.7:
            t = " ".join(rng.sample(KEYBOARD_JUNK, rng.choice([1, 2])))
        elif kind < 0.9:
            t = rng.choice(BARE_STATEMENT_LINES).format(n4=digits(rng, 4), n6=digits(rng, 6), n10=digits(rng, 10))
        else:
            t = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randint(3, 9)))
        t = rng.choice(PREFIX) + t + rng.choice(SUFFIX)
        texts.append(t)
        labels.append("Unknown")

    for description, category in (extra or []):
        for _ in range(extra_copies):
            texts.append(description)
            labels.append(category)
    return texts, labels