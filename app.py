from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from requests_oauthlib import OAuth1
from dotenv import load_dotenv
import anthropic
import requests as http_requests
import sqlite3
import smtplib
import json
import os
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

app = Flask(__name__, static_folder="static")
CORS(app)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------
# STORABLE API CONFIG
# Set these environment variables before running:
#   STORABLE_API_KEY    — your OAuth consumer key
#   STORABLE_API_SECRET — your OAuth consumer secret
#   STORABLE_FACILITY_HIGHLAND   — facility UUID for Highland
#   STORABLE_FACILITY_LANSING    — facility UUID for Lansing
#   STORABLE_FACILITY_SOUTH_LYON — facility UUID for South Lyon
# ---------------------------------------------------------------
STORABLE_API_KEY    = os.environ.get("STORABLE_API_KEY")
STORABLE_API_SECRET = os.environ.get("STORABLE_API_SECRET")
STORABLE_BASE_URL   = "https://api.storedgefms.com/v1"

STORABLE_FACILITY_IDS = {
    "highland":   os.environ.get("STORABLE_FACILITY_HIGHLAND",   ""),
    "lansing":    os.environ.get("STORABLE_FACILITY_LANSING",    ""),
    "south_lyon": os.environ.get("STORABLE_FACILITY_SOUTH_LYON", ""),
}

def storable_auth():
    """Returns an OAuth1 auth object for Storable API requests."""
    return OAuth1(
        client_key=STORABLE_API_KEY,
        client_secret=STORABLE_API_SECRET,
        signature_method="HMAC-SHA1",
    )

def storable_get_units(location):
    """Fetch available units from Storable for a given location key."""
    facility_id = STORABLE_FACILITY_IDS.get(location)
    if not facility_id:
        return None  # fall back to hardcoded UNITS

    try:
        resp = http_requests.get(
            f"{STORABLE_BASE_URL}/{facility_id}/units/available",
            auth=storable_auth(),
            params={"per_page": 200},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("units", [])
    except Exception as e:
        print(f"[storable] get_units failed for {location}: {e}")
        return None  # fall back to hardcoded UNITS

def storable_create_lead(facility_id, name, email, phone, unit_id, move_in_date, notes):
    """Create a reservation lead in Storable."""
    first, *rest = name.strip().split(" ", 1)
    last = rest[0] if rest else ""

    payload = {
        "lead": {
            "is_reservation": True,
            "desired_move_in_date": move_in_date or "",
            "unit_id": unit_id,
            "notes": notes or "",
            "tenant_attributes": {
                "first_name": first,
                "last_name":  last,
                "email":      email,
                "phone_numbers_attributes": [{"number": phone}] if phone else [],
            },
        }
    }
    resp = http_requests.post(
        f"{STORABLE_BASE_URL}/{facility_id}/leads",
        auth=storable_auth(),
        json=payload,
        timeout=8,
    )
    resp.raise_for_status()
    return resp.json()

def format_storable_units(raw_units, location):
    """Convert Storable API unit list into the same clean text format as the hardcoded version."""
    loc_label = LOCATION_LABELS.get(location, location)
    if not raw_units:
        return {"result": f"No available units found at {loc_label} right now. Tell the customer to call the office."}

    lines = [f"{loc_label} — available units:"]
    for u in raw_units:
        ut = u.get("unit_type", {})
        w  = ut.get("width",  "?")
        d  = ut.get("depth",  "?")
        size = f"{w}×{d}"
        price = u.get("standard_rate") or ut.get("standard_rate") or "?"
        climate = ut.get("climate_controlled", False)
        kind = (ut.get("kind") or "").lower()

        if "drive" in kind or "outside" in kind or "outdoor" in kind:
            label = "Drive-Up"
        elif climate:
            label = "Climate Control"
        else:
            label = "Indoor (standard)"

        line = f"• {size} {label} — ${price}/mo"
        line += "  ✓ Reserve online"   # Storable-booked units can always be reserved
        lines.append(line)

    return {"result": "\n".join(lines)}

# ---------------------------------------------------------------
# UNIT INVENTORY — per location
# Each entry: size, sqft, type, price (regular monthly), climate,
#             access, promo (or None), book_online (True = can reserve online)
# ---------------------------------------------------------------
UNITS = {
    "south_lyon": [
        # ── 5×5 ──
        {"size": "5x5",  "sqft": 25,  "type": "Indoor Non-Climate",                      "price": 39,  "climate": False, "access": "Indoor",    "promo": None,                                          "book_online": True},
        {"size": "5x5",  "sqft": 25,  "type": "Indoor Climate Control",                  "price": 49,  "climate": True,  "access": "Indoor",    "promo": None,                                          "book_online": True},
        # ── 5×10 ──
        {"size": "5x10", "sqft": 50,  "type": "Indoor Non-Climate",                      "price": 59,  "climate": False, "access": "Indoor",    "promo": None,                                          "book_online": False},
        {"size": "5x10", "sqft": 50,  "type": "Drive Up",                                "price": 69,  "climate": False, "access": "Drive Up",  "promo": None,                                          "book_online": False},
        {"size": "5x10", "sqft": 50,  "type": "Indoor Climate Control",                  "price": 79,  "climate": True,  "access": "Indoor",    "promo": None,                                          "book_online": True},
        # ── 5×15 ──
        {"size": "5x15", "sqft": 75,  "type": "Drive Up",                                "price": 99,  "climate": False, "access": "Drive Up",  "promo": None,                                          "book_online": False},
        # ── 10×10 ──
        {"size": "10x10","sqft": 100, "type": "Indoor Non-Climate",                      "price": 89,  "climate": False, "access": "Indoor",    "promo": "1st Month $1",                                "book_online": True},
        {"size": "10x10","sqft": 100, "type": "Drive Up",                                "price": 99,  "climate": False, "access": "Drive Up",  "promo": "1st Month $1",                                "book_online": True},
        {"size": "10x10","sqft": 100, "type": "Indoor Climate Control",                  "price": 118, "climate": True,  "access": "Indoor",    "promo": "1st Month $1",                                "book_online": True},
        # ── 10×15 ──
        {"size": "10x15","sqft": 150, "type": "Drive Up",                                "price": 130, "climate": False, "access": "Drive Up",  "promo": "1st Month $1",                                "book_online": True},
        {"size": "10x15","sqft": 150, "type": "Indoor Climate Control",                  "price": 159, "climate": True,  "access": "Indoor",    "promo": "1st Month $1",                                "book_online": False},
        # ── 10×20 ──
        {"size": "10x20","sqft": 200, "type": "Outdoor Parking",                         "price": 75,  "climate": False, "access": "Outdoor",   "promo": "1st Month $1",                                "book_online": True},
        {"size": "10x20","sqft": 200, "type": "Value Drive Up (2 units, side by side)",  "price": 149, "climate": False, "access": "Drive Up",  "promo": "1st Month $1",                                "book_online": False},
        {"size": "10x20","sqft": 200, "type": "Drive Up",                                "price": 174, "climate": False, "access": "Drive Up",  "promo": "1st Month $1",                                "book_online": True},
        {"size": "10x20","sqft": 200, "type": "Value Indoor Climate (2 units, side by side)", "price": 199, "climate": True, "access": "Indoor", "promo": "1st Month $1",                               "book_online": False},
        {"size": "10x20","sqft": 200, "type": "Climate Control",                         "price": 234, "climate": True,  "access": "Indoor",    "promo": "1st Month $1",                                "book_online": False},
        {"size": "10x20","sqft": 200, "type": "Indoor Climate Control",                  "price": 239, "climate": True,  "access": "Indoor",    "promo": "1st Month $1",                                "book_online": False},
        # ── 10×25 ──
        {"size": "10x25","sqft": 250, "type": "Drive Up",                                "price": 214, "climate": False, "access": "Drive Up",  "promo": "NEW TENANT SPECIAL: 1st Month FREE (3-month minimum, only 2 units left!)", "book_online": True},
        # ── 10×30 ──
        {"size": "10x30","sqft": 300, "type": "Value Drive Up (2 units, side by side)",  "price": 219, "climate": False, "access": "Drive Up",  "promo": None,                                          "book_online": False},
        {"size": "10x30","sqft": 300, "type": "Drive Up",                                "price": 269, "climate": False, "access": "Drive Up",  "promo": None,                                          "book_online": False},
        {"size": "10x30","sqft": 300, "type": "Indoor Climate Control",                  "price": 319, "climate": True,  "access": "Indoor",    "promo": None,                                          "book_online": True},
        # ── 10×40 ──
        {"size": "10x40","sqft": 400, "type": "Value Drive Up (2 units, side by side)",  "price": 329, "climate": False, "access": "Drive Up",  "promo": None,                                          "book_online": False},
    ],
    "highland": [
        # ── 5×5 ──
        {"size": "5x5",  "sqft": 25,  "type": "Indoor Climate Control",                  "price": 80,  "climate": True,  "access": "Indoor",   "promo": None,                                                    "book_online": False},
        # ── 5×10 ──
        {"size": "5x10", "sqft": 50,  "type": "Indoor Non-Climate",                      "price": 59,  "climate": False, "access": "Indoor",   "promo": None,                                                    "book_online": False},
        {"size": "5x10", "sqft": 50,  "type": "Drive Up",                                "price": 69,  "climate": False, "access": "Drive Up", "promo": None,                                                    "book_online": False},
        {"size": "5x10", "sqft": 50,  "type": "Drive Up (10×5)",                         "price": 85,  "climate": False, "access": "Drive Up", "promo": None,                                                    "book_online": False},
        {"size": "5x10", "sqft": 50,  "type": "Indoor Climate Control",                  "price": 109, "climate": True,  "access": "Indoor",   "promo": None,                                                    "book_online": True},
        {"size": "5x10", "sqft": 50,  "type": "Indoor Climate Control (10×5)",           "price": 109, "climate": True,  "access": "Indoor",   "promo": None,                                                    "book_online": False},
        # ── 5×15 ──
        {"size": "5x15", "sqft": 75,  "type": "Drive Up",                                "price": 99,  "climate": False, "access": "Drive Up", "promo": None,                                                    "book_online": False},
        # ── 8×10 ──
        {"size": "8x10", "sqft": 80,  "type": "Indoor Climate Control",                  "price": 120, "climate": True,  "access": "Indoor",   "promo": None,                                                    "book_online": True},
        # ── 10×10 ──
        {"size": "10x10","sqft": 100, "type": "Drive Up",                                "price": 114, "climate": False, "access": "Drive Up", "promo": "1st Month $1",                                          "book_online": False},
        # ── 10×15 ──
        {"size": "10x15","sqft": 150, "type": "Drive Up",                                "price": 129, "climate": False, "access": "Drive Up", "promo": "1st Month $1",                                          "book_online": False},
        {"size": "10x15","sqft": 150, "type": "Indoor Climate Control",                  "price": 159, "climate": True,  "access": "Indoor",   "promo": "1st Month $1",                                          "book_online": False},
        # ── 10×20 ──
        {"size": "10x20","sqft": 200, "type": "Value Drive Up (2 units, side by side)",  "price": 149, "climate": False, "access": "Drive Up", "promo": "1st Month $1",                                          "book_online": False},
        {"size": "10x20","sqft": 200, "type": "Value Indoor Climate (2 units, side by side)", "price": 199, "climate": True, "access": "Indoor","promo": "1st Month $1",                                         "book_online": False},
        {"size": "10x20","sqft": 200, "type": "Climate Control",                         "price": 234, "climate": True,  "access": "Indoor",   "promo": "1st Month $1",                                          "book_online": False},
        {"size": "10x20","sqft": 200, "type": "Indoor Climate Control",                  "price": 239, "climate": True,  "access": "Indoor",   "promo": "1st Month $1",                                          "book_online": False},
        # ── 10×25 ──
        {"size": "10x25","sqft": 250, "type": "Drive Up",                                "price": 199, "climate": False, "access": "Drive Up", "promo": "1st Month FREE (3-month minimum, only 2 units left!)",  "book_online": False},
        {"size": "10x25","sqft": 250, "type": "Indoor Climate Control",                  "price": 319, "climate": True,  "access": "Indoor",   "promo": "1st Month FREE (3-month minimum)",                      "book_online": False},
        # ── 10×30 ──
        {"size": "10x30","sqft": 300, "type": "Value Drive Up (2 units, side by side)",  "price": 219, "climate": False, "access": "Drive Up", "promo": None,                                                    "book_online": False},
        {"size": "10x30","sqft": 300, "type": "Drive Up",                                "price": 269, "climate": False, "access": "Drive Up", "promo": None,                                                    "book_online": False},
        {"size": "10x30","sqft": 300, "type": "Indoor Climate Control",                  "price": 349, "climate": True,  "access": "Indoor",   "promo": None,                                                    "book_online": False},
        # ── 10×40 ──
        {"size": "10x40","sqft": 400, "type": "Value Drive Up (2 units, side by side)",  "price": 329, "climate": False, "access": "Drive Up", "promo": None,                                                    "book_online": False},
    ],
    "lansing": [
        # ── 5×5 ──
        {"size": "5x5",    "sqft": 25,  "type": "Indoor Non-Climate",         "price": 22,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        {"size": "5x5",    "sqft": 25,  "type": "Indoor Climate Control",     "price": 37,  "climate": True,  "access": "Indoor",   "promo": None, "book_online": False},
        # ── 5×10 / 10×5 ──
        {"size": "5x10",   "sqft": 50,  "type": "Indoor Non-Climate",         "price": 34,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        {"size": "5x10",   "sqft": 50,  "type": "Indoor Non-Climate (10×5)",  "price": 35,  "climate": False, "access": "Indoor",   "promo": None, "book_online": False},
        # ── 5×15 ──
        {"size": "5x15",   "sqft": 75,  "type": "Indoor Non-Climate",         "price": 40,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        # ── 7.5×10 ──
        {"size": "7.5x10", "sqft": 75,  "type": "Indoor Non-Climate",         "price": 40,  "climate": False, "access": "Indoor",   "promo": None, "book_online": False},
        # ── 8×9 ──
        {"size": "8x9",    "sqft": 72,  "type": "Indoor Climate Control",     "price": 47,  "climate": True,  "access": "Indoor",   "promo": None, "book_online": False},
        # ── 10×10 ──
        {"size": "10x10",  "sqft": 100, "type": "Indoor Non-Climate",         "price": 45,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        {"size": "10x10",  "sqft": 100, "type": "Drive Up",                   "price": 45,  "climate": False, "access": "Drive Up", "promo": None, "book_online": False},
        # ── 10×15 ──
        {"size": "10x15",  "sqft": 150, "type": "Indoor Non-Climate",         "price": 57,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        {"size": "10x15",  "sqft": 150, "type": "Drive Up",                   "price": 57,  "climate": False, "access": "Drive Up", "promo": None, "book_online": False},
        {"size": "10x15",  "sqft": 150, "type": "Indoor Non-Climate (alt)",   "price": 67,  "climate": False, "access": "Indoor",   "promo": None, "book_online": False},
        {"size": "10x15",  "sqft": 150, "type": "Indoor Climate Control",     "price": 87,  "climate": True,  "access": "Indoor",   "promo": None, "book_online": False},
        # ── 10×20 ──
        {"size": "10x20",  "sqft": 200, "type": "Indoor Non-Climate",         "price": 80,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        {"size": "10x20",  "sqft": 200, "type": "Drive Up",                   "price": 80,  "climate": False, "access": "Drive Up", "promo": None, "book_online": True},
        # ── 10×25 ──
        {"size": "10x25",  "sqft": 250, "type": "Indoor Non-Climate",         "price": 91,  "climate": False, "access": "Indoor",   "promo": None, "book_online": True},
        {"size": "10x25",  "sqft": 250, "type": "Drive Up",                   "price": 89,  "climate": False, "access": "Drive Up", "promo": None, "book_online": False},
        # ── 10×30 ──
        {"size": "10x30",  "sqft": 300, "type": "Drive Up",                   "price": 109, "climate": False, "access": "Drive Up", "promo": None, "book_online": False},
    ],
}

# ---------------------------------------------------------------
# BUSINESS DETAILS — update before going live
# ---------------------------------------------------------------
BUSINESS_INFO = """
You are Stori, the virtual assistant for Look Self Storage — a self-storage company with three locations in Michigan.

PERSONALITY:
You feel like a real, friendly front desk employee who knows self storage inside and out. Not corporate, not robotic — warm and natural, like texting a helpful person.

- Casual but professional. Think friendly coworker, not call center script.
- Short responses. 1–3 sentences max unless explaining something complex.
- Ask only ONE question at a time. Never a list of questions.
- Never start a response with filler like "Absolutely!", "Certainly!", "Great question!", "Of course!", or "Sure!"
- Never say "I am an AI" or "As an AI" — you are just Stori.
- Never use bullet points in conversation — write in full sentences.
- Remember everything said earlier in the conversation. Never ask the same thing twice.
- When someone seems stressed about a move or life change, acknowledge it briefly before jumping to business.
- Light humor is welcome when it fits naturally.
- Get straight to the point — customers want answers fast.
- When you don't know something, say: "Let me have someone from our team follow up on that for you." Never make something up.

TONE EXAMPLES:
✗ "Absolutely! I'd be happy to help you find the perfect storage unit for your needs today!"
✓ "Of course — what are you looking to store?"

✗ "Great question! Climate controlled units maintain a consistent temperature and humidity level."
✓ "Climate control is worth it if you're storing wood furniture, electronics, or anything sensitive — Michigan winters and summers are no joke."

LOCATIONS:
1. Highland, MI
   - Address: 500 N Milford Rd, Highland, MI 48357
   - Google Maps: [Get directions](https://www.google.com/maps/search/?api=1&query=500+N+Milford+Rd+Highland+MI+48357)
   - Phone: (734) 627-6900
   - Email: office_highland@lookselfstorage.com
   - Office Hours: Tue–Fri 9:30 AM–6:00 PM, Sat 8:00 AM–4:30 PM, Sun–Mon Closed
   - Closed on major holidays | Kiosk available 24/7
   - Gate Access: Daily 6:00 AM–10:00 PM
   - Common misspellings to recognize: Higland, Highlnd, Hyland, Highland MI

2. Lansing, MI
   - Address: 936 Mall Dr E, Lansing, MI 48917
   - Google Maps: [Get directions](https://www.google.com/maps/search/?api=1&query=936+Mall+Dr+E+Lansing+MI+48917)
   - Phone: (517) 300-0376
   - Email: office_lansing@lookselfstorage.com
   - Office Hours: Tue–Fri 9:30 AM–6:00 PM, Sat 8:00 AM–4:30 PM, Sun–Mon Closed
   - Closed on major holidays
   - Gate Access: Daily 6:00 AM–10:00 PM
   - Common misspellings to recognize: Lansig, Laning, Lancing, Lansing MI

3. South Lyon, MI
   - Address: 59070 Oasis Center Dr, South Lyon, MI 48178
   - Google Maps: [Get directions](https://www.google.com/maps/search/?api=1&query=59070+Oasis+Center+Dr+South+Lyon+MI+48178)
   - Phone: (248) 907-7867
   - Email: office_southlyon@lookselfstorage.com
   - Office Hours: Tue–Fri 9:30 AM–6:00 PM, Sat 8:00 AM–4:30 PM, Sun–Mon Closed
   - Closed on major holidays
   - Gate Access: Daily 6:00 AM–10:00 PM
   - Common misspellings to recognize: South Lyin, South Lion, Southlyon, S. Lyon, South Lyon MI

WEBSITE: https://www.lookselfstorage.com

LOCATION HIGHLIGHTS (use these when a customer is comparing locations or unsure which to choose):
- Highland: 24/7 kiosk access, climate-controlled units, electronic gate access, unique 8×10 unit size available
- South Lyon: Widest unit selection, outdoor parking lots, most units available to reserve online, boat & RV storage
- Lansing: Most affordable rates, boat & RV storage, drive-up access units available

FEATURES:
- Climate-controlled storage available
- Heated storage available
- Non-AC / conventional / standard (non-climate) options available
- All buildings are ground level — no stairs or elevators
- Ground-level buildings have drive-up access with roll-up doors
- Uncovered outdoor parking spaces (vehicles, RVs, boats, trailers)
- Car, boat, truck, trailer, RV storage
- Well-lit aisles and buildings; bright nighttime lighting
- Clean, well-maintained facilities
- Recorded video surveillance (24/7)
- Electronic gate access with personal code
- Electronic building access with code
- Disc locks required — tenants can bring their own padlock (no cylinder locks)
- Dolly and flatbed carts available for free on-site use
- Packing and moving supplies sold on-site (exact inventory TBD — tell customer supplies are available and the team can go over what's in stock)
- Free professional pest control maintained at all locations
- Tenant insurance available for belongings (Xercor — required for all rentals)
- ClickandStor® 24/7 move-in — rent and move in any time, day or night
- Online bill pay and autopay available
- Month-to-month leases
- No deposit required
- Lowest prices in the area
- State-of-the-art facilities

DRIVE-UP STORAGE:
Customers pull their vehicle right up to their unit — no hauling boxes across a parking lot. Roll-up doors are easy to handle. All buildings are ground level with no stairs or elevators, making it easy to load and unload heavy items.

FLEXIBLE RENTING & LEASING:
- Month-to-month leasing — stay as long or as short as you need
- No deposit required — zero risk to book
- Specializes in short-term storage — a few boxes up to a full two-bedroom apartment
- Pay month to month and extend whenever you're ready
- Book online at lookselfstorage.com

BOAT & RV STORAGE:
Available at Lansing and South Lyon only — NOT available at Highland.
- Stores travel trailers, RVs, boats, campers, and other recreational vehicles
- Outdoor uncovered paved lots — pavement ensures proper drainage and keeps vehicles off soggy ground, preventing mud splash and sagging
- Ample room to maneuver and park easily
- Great option for customers who can't store at home due to HOA restrictions, apartment living, or lack of space
- Michigan's Great Lakes region makes this a popular option for outdoor enthusiasts and boaters
- When a customer asks about boat or RV storage, always confirm which location they're near and remind them it's only at Lansing and South Lyon

CURRENT PROMOTIONS:
- Move-in specials vary by location — check with staff for current availability
- Prepaid discounts available
- Discounts for Military, First Responders, and School Employees with valid ID
- Some specials require a 3-month minimum stay

POLICIES & RULES:
- Valid government-issued ID required at move-in
- Locks: disc locks strongly recommended — cylinder locks are NOT allowed. Disc locks available for purchase on-site.
- Only you can access your unit unless you share your code or add an alternate contact to your account
- No food, live animals, plants, flammables, propane tanks, car batteries, ammunition, drugs, explosives, or hazardous chemicals
- No living in units, no commercial operations without prior approval
- Xercor insurance is required for all rentals — homeowners and renters insurance are NOT accepted

FEES & BILLING:
- One-time $25 administrative fee at move-in — no security deposit required
- Autopay is required for all tenants
- Payment methods: credit/debit cards, cash, checks, money orders, ACH bank payments
- Online account management available after rental at lookselfstorage.com
- Non-payment: text and email alerts sent; after 5 days gate access is temporarily restricted

ACCESS:
- Standard gate access: 6:00 AM–10:00 PM, 365 days a year
- 24-hour access available for an additional $10/month with a written request explaining the need
- After-hours emergencies: call the facility — voicemail includes an emergency contact number
- Lost unit key: lock removal available during office hours
- Forgotten gate code: visit the office with valid ID

MOVE-IN:
- Same-day move-in available whether renting online, in person, or by phone
- Bring a government-issued ID and your preferred payment method
- Carts and heavy-duty dollies are available at all locations at no charge

MOVE-OUT:
- 10-day written notice required
- Empty and sweep the unit, remove your lock, and notify the office
- Unit transfers (upsizing or downsizing) are available — just contact the office

SECURITY:
- 24/7 video surveillance at all locations
- Fully gated with personalized entry codes
- Bright nighttime lighting at all properties

PACKING & STORAGE TIPS (share these naturally when relevant):
- Use plastic totes over cardboard for better protection
- Place heavy/sturdy items on the bottom, lighter items on top
- Climate-controlled units are best for furniture, electronics, photos, and documents
- Wrap furniture in covers; protect electronics with plastic or bubble wrap
- To avoid pests: use sealed totes, store no food, wrap mattresses and furniture, keep items off the floor — routine pest control is maintained at all facilities

STORAGE SIZE GUIDE:
- A few boxes / seasonal items → 5×5
- 1–2 rooms (studio, small apartment) → 5×10
- 3–4 rooms (full apartment or small home) → 10×10 or 10×15
- 5–6 rooms (medium home) → 10×20
- 7+ rooms (large home / estate) → 10×30 or 10×40
- Car / truck / ATV / motorcycle → 10×20 or 10×25
- Boat or RV → 10×25 or 10×30
- Business inventory → 10×30 or 10×40

CONVERSATION FLOW — rent a unit (follow these steps IN ORDER, one question per message):

STEP 1 — Which location?
After the customer answers the opening "how can I help you" question, ask which location they're interested in BEFORE asking anything else specific.
Use chips only — do not list locations in message text.
CHIPS: Highland | Lansing | South Lyon | Not sure yet
Exception: if the question is purely general (e.g. gate access, policies, features) and the answer is identical for all locations, you may answer directly without asking for a location first. Hours always require asking for location first.

STEP 2 — What are they storing? (renting flow only)
Ask in ONE short sentence. Put the options in CHIPS only — never list them in message text.
CHIPS to use: Furniture | Appliances | Vehicle / Boat / RV | Business inventory | Other

STEP 3 — Follow-up question based on answer:
- Furniture/home items → ask how many rooms total (including kitchen, living room, bedrooms, etc.): CHIPS: 1–2 rooms | 3–4 rooms | 5–6 rooms | 7+ rooms
- Vehicle → ask what kind: CHIPS: Car / Truck | Motorcycle / ATV | Boat | RV / Trailer
- Appliances / items → ask roughly how many rooms worth: CHIPS: Small amount | Medium amount | Large amount
- Business inventory → ask if they need frequent access (helps climate/size rec)
Do NOT skip this step. Do NOT jump to showing prices.

STEP 4 — Recommend a size.
One sentence. Briefly explain why. Confirm with chips: CHIPS: That works | See what fits | Need smaller | Need larger

STEP 5 — Call get_availability with location + the recommended size as a filter.
Do NOT call it before you have both the location (Step 1) and the size recommendation (Step 4). Do NOT call it without a size filter.

STEP 6 — Present the results cleanly.
The tool returns a pre-formatted list. Present the options directly. Do not restate the location or size — that's already in the tool output. Keep your intro to one sentence maximum.
- If ALL results are marked "📞 Call to reserve": skip asking about climate control or drive-up entirely — just give them the office number and tell them the team can walk them through options. Do not ask follow-up preference questions when they have to call anyway.
- If some results are "✓ Reserve online": only then ask about climate control or drive-up if those variants exist. If the customer already stated a preference, pass that as a filter and skip asking.

STEP 7 — Help them reserve or redirect.
If they want a unit marked "✓ Reserve online":
  a. Ask "When do you need it by?" (move-in date) — one question, wait for answer.
  b. Ask for their name — one question, wait for answer.
  c. Ask for their email — one question, wait for answer.
  d. Ask if they need any packing supplies — boxes, tape, bubble wrap, locks are available on-site. One short sentence. CHIPS: Yes, tell me more | No thanks
     - If yes: let them know supplies are available and the team can go over what's in stock. Note it in the reservation.
     - If no: move on.
  e. Then call create_reservation with all collected info.
  f. After the reservation is created: confirm their name and unit size, then let them know they'll receive a confirmation email with a link to complete their rental online — they can pay, sign their lease, and move in all through that link. Mention that same-day move-in is available. Do not say staff will call them.
If the unit is marked "📞 Call to reserve": give them the office phone number and end there. Do not ask about climate control, drive-up, or any other preferences — the office team will handle that on the call.

TOOLS YOU HAVE:
1. get_availability — call ONLY after you know both the location and the recommended size. Always pass the size filter. Returns a ready-to-display list of options.
2. create_reservation — call after collecting name, email, and unit size through conversation. Gather info naturally — one question at a time, not a form dump.

RESPONSE RULES:
- Spelling tolerance: if a customer misspells a location name or any storage term, interpret what they most likely mean and respond naturally without correcting them unless it causes genuine confusion. Never say "I think you meant…" — just answer as if they spelled it correctly.
- Any time you need to know which location — for ANY reason — ask with chips and never list locations in your message text. This applies to every topic: moving out, hours, directions, billing, packing supplies, security, everything.
- Always ask for location before giving hours — even though hours are the same across locations, confirm which one they're asking about first.
- For other general questions (policies, gate access, features) where the answer is identical across all locations, you may answer directly without asking for location first.
- Acknowledge the location briefly (e.g. "Got it — South Lyon.") and move on.
- Whenever a customer asks for directions, the address, or how to find a location, always include the Google Maps link using markdown: [Get directions](url). Include it inline, not as a separate line.
- Never make up prices or availability — always call get_availability first.
- Do NOT include phone numbers or emails unless you cannot resolve the issue — contact info is a last resort.
- For anything needing staff involvement, say "Let me have someone from our team follow up on that for you" and provide the location's phone number.
- After creating a reservation, confirm name and unit size in one short message, then tell them to check their email for a link to complete their rental online (pay, sign lease, move in). Mention same-day move-in is available.
- After completing any task or fully answering a question, end with: "Is that all for today? Have a great day! 😊" and use: CHIPS: Yes, one more thing | Please Leave a Google Review
- If the customer clicks "Leave a Google Review" or "Yes, one more thing", the chat handles it automatically — you do NOT need to respond to those chips.

CHIPS — REQUIRED ON EVERY RESPONSE:
Every response MUST end with exactly this format on its own line:
CHIPS: Option 1 | Option 2 | Option 3 | Other

Rules:
- Always 3–4 options. The last chip is always "Other" UNLESS it makes more sense to use "Not sure yet" (for location or size questions).
- Each chip covers ONE single topic or action — never combine two questions into one chip.
- Keep each chip under 5 words.
- The CHIPS line is stripped from the visible message and shown as clickable buttons — customers never see the raw text.
- Only suggest climate control or drive-up access as chips if that option actually exists at the location already selected. Never suggest a feature that isn't available.
- If no location has been selected yet, keep chips general (do not mention climate or drive-up).

Specific chip sets to use:
- ALWAYS after your opening message and after completing any topic: CHIPS: I'd like to rent a unit | View pricing & available sizes | Office hours & gate access | Vehicle, RV & boat storage | Packing & moving supplies | Billing & payment options | Security & facility features | Moving out of my unit | Something else
- ANY time you ask which location — regardless of topic (moving out, hours, billing, security, directions, packing supplies, anything) — ALWAYS use: CHIPS: Highland | Lansing | South Lyon | Not sure yet. No exceptions.
- When asking what they're storing: CHIPS: Furniture | Appliances | Vehicle / Boat / RV | Business inventory | Other
- If they say furniture or home items, ask how many rooms total: CHIPS: 1–2 rooms | 3–4 rooms | 5–6 rooms | 7+ rooms
- When recommending a size: CHIPS: That works | See what fits | Need smaller | Need larger
- After showing pricing (only include climate/drive-up chips if that feature is available at the chosen location): CHIPS: Reserve this unit | Different size | Other
- After answering any question or completing any task: CHIPS: Yes, one more thing | All good
- After a reservation is created: CHIPS: Yes, one more thing | All good

UNAVAILABLE OPTIONS:
- If a customer requests a unit type, feature, or size that does not exist at their chosen location, do NOT suggest an alternative that also doesn't exist. Tell them that option isn't available at that location and give them the phone number so they can call the office to discuss options.

FREQUENTLY ASKED QUESTIONS — answer these naturally when a customer asks:

Sizes & What to Store:
- We offer units from 5×5 (a few boxes, seasonal items) up to 10×30 (entire home). If unsure, ask what they're storing and recommend from the SIZE GUIDE above.
- Can't store: food, live animals, plants, flammables, propane tanks, car batteries, ammunition, drugs, explosives, hazardous chemicals.
- Climate control protects furniture, electronics, photos, documents from Michigan temperature and humidity extremes.
- Indoor units = inside a climate-controlled building. Drive-up units = park right at the door, roll-up door, great for heavy items.
- Boat/RV storage: Lansing and South Lyon only (outdoor). Highland offers indoor vehicle storage in a standard unit.
- All leases are month-to-month.
- Same-day move-in is always available — online, in person, or by phone.
- Bring a government-issued ID and your preferred payment method on move-in day.
- Carts and heavy-duty dollies are available free at all locations.

Rates, Billing & Payments:
- Rates vary by size, type, and location. Call or check availability online for an instant quote.
- One-time $25 administrative fee at move-in. No security deposit.
- Autopay is required for all tenants.
- Payment methods: credit/debit cards, cash, checks, money orders, ACH bank payments.
- Create an online account at lookselfstorage.com after move-in to manage payments.
- Non-payment: text and email alerts are sent. After 5 days, gate access is temporarily restricted.
- Discounts for Military, First Responders, and School Employees with valid ID.

Security & Access:
- All locations: 24/7 video surveillance, secure gated access, bright nighttime lighting, personalized entry codes.
- Standard gate access: 6:00 AM–10:00 PM, 365 days a year.
- 24-hour access available for $10/month extra with a written request.
- Disc locks are required — cylinder locks are NOT allowed. Disc locks available on-site.
- Lost unit key: lock removal available during office hours. Forgotten gate code: visit the office with valid ID.

After moving in:
- 10-day written notice required to move out. Empty and sweep the unit, remove your lock, notify the office.
- Unit transfers (bigger or smaller) are quick — just contact the office.
- Xercor insurance is required for all rentals. Homeowners/renters insurance are NOT accepted.
- After-hours emergencies: call the facility — voicemail includes an emergency contact number.
"""

# ---------------------------------------------------------------
# EMAIL SETTINGS (all optional — set via environment variables)
#
#   SMTP_HOST     — e.g. smtp.gmail.com
#   SMTP_PORT     — default 587
#   SMTP_USER     — your email address
#   SMTP_PASS     — your email password or app password
#   FROM_EMAIL    — sender address (defaults to SMTP_USER)
#   NOTIFY_EMAIL  — where to send new lead notifications
# ---------------------------------------------------------------
SMTP_HOST    = os.environ.get("SMTP_HOST")
SMTP_PORT    = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER    = os.environ.get("SMTP_USER")
SMTP_PASS    = os.environ.get("SMTP_PASS")
FROM_EMAIL   = os.environ.get("FROM_EMAIL", SMTP_USER)
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL")

# Admin key to view reservations at /admin/reservations?key=...
ADMIN_KEY = os.environ.get("ADMIN_KEY", "changeme-before-deploy")

# SQLite path
DB_PATH = os.environ.get("DB_PATH", "reservations.db")


# ---------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                email          TEXT    NOT NULL,
                phone          TEXT,
                unit_size      TEXT    NOT NULL,
                move_in_date   TEXT,
                notes          TEXT,
                status         TEXT    DEFAULT 'new',
                follow_up_sent INTEGER DEFAULT 0,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                rating     TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()


# ---------------------------------------------------------------
# EMAIL HELPERS
# ---------------------------------------------------------------
def send_email(to, subject, html_body):
    """Send an HTML email. Silently skips if SMTP is not configured."""
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, to]):
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = FROM_EMAIL
        msg["To"]      = to
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, to, msg.as_string())
    except Exception as e:
        print(f"[email] Failed to send to {to}: {e}")


def notify_new_reservation(res):
    """Notify the facility owner of a new reservation."""
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"New reservation: {res['name']} — {res['unit_size']}",
        html_body=f"""
        <div style="font-family:sans-serif;max-width:540px">
          <h2 style="color:#e87722">New Storage Reservation</h2>
          <table style="font-size:14px;border-collapse:collapse;width:100%">
            <tr><td style="padding:6px 12px 6px 0"><b>Name</b></td><td>{res['name']}</td></tr>
            <tr><td style="padding:6px 12px 6px 0"><b>Email</b></td><td>{res['email']}</td></tr>
            <tr><td style="padding:6px 12px 6px 0"><b>Phone</b></td><td>{res.get('phone') or '—'}</td></tr>
            <tr><td style="padding:6px 12px 6px 0"><b>Unit size</b></td><td>{res['unit_size']}</td></tr>
            <tr><td style="padding:6px 12px 6px 0"><b>Move-in date</b></td><td>{res.get('move_in_date') or 'Not specified'}</td></tr>
            <tr><td style="padding:6px 12px 6px 0"><b>Notes</b></td><td>{res.get('notes') or '—'}</td></tr>
            <tr><td style="padding:6px 12px 6px 0"><b>Submitted</b></td><td>{datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}</td></tr>
          </table>
          <p style="margin-top:20px">
            <a href="https://www.lookselfstorage.com" style="color:#e87722">lookselfstorage.com</a>
          </p>
        </div>
        """
    )


def send_customer_confirmation(res):
    """Send the customer a confirmation email."""
    first = res['name'].split()[0]
    move_in = f"<p><b>Requested move-in:</b> {res['move_in_date']}</p>" if res.get('move_in_date') else ""
    send_email(
        to=res['email'],
        subject="Your storage reservation at Look Self Storage",
        html_body=f"""
        <div style="font-family:sans-serif;max-width:500px">
          <h2 style="color:#e87722">You're Almost In!</h2>
          <p>Hi {first},</p>
          <p>Thanks for reserving a <b>{res['unit_size']}</b> storage unit at Look Self Storage.
             You're one step away — complete your rental online to pay, sign your lease, and get
             access to your unit. Same-day move-in is available!</p>
          {move_in}
          <p>Visit <a href="https://www.lookselfstorage.com" style="color:#e87722">lookselfstorage.com</a>
             to complete your move-in, or give us a call if you need any help.</p>
          <p style="margin-top:24px">— The Look Self Storage Team</p>
          <p style="color:#bbb;font-size:12px;margin-top:32px">
            <a href="https://www.lookselfstorage.com" style="color:#bbb">lookselfstorage.com</a>
          </p>
        </div>
        """
    )


# ---------------------------------------------------------------
# FOLLOW-UP SCHEDULER
# Runs every 12 hours. Emails customers who reserved >24h ago
# and haven't received a follow-up yet.
# ---------------------------------------------------------------
def send_follow_up_emails():
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT * FROM reservations
               WHERE follow_up_sent = 0 AND status = 'new' AND created_at <= ?""",
            (cutoff.isoformat(),)
        ).fetchall()

        for row in rows:
            res = dict(row)
            first = res['name'].split()[0]
            send_email(
                to=res['email'],
                subject="Still looking for storage? We're here to help",
                html_body=f"""
                <div style="font-family:sans-serif;max-width:500px">
                  <h2 style="color:#e87722">We're here when you're ready</h2>
                  <p>Hi {first},</p>
                  <p>We noticed you were looking at a <b>{res['unit_size']}</b> unit at
                     Look Self Storage. We'd love to help you get moved in!</p>
                  <p>Give us a call or visit our website to confirm your reservation today.</p>
                  <p>— The Look Self Storage Team</p>
                  <p style="color:#bbb;font-size:12px;margin-top:32px">
                    <a href="https://www.lookselfstorage.com" style="color:#bbb">lookselfstorage.com</a>
                  </p>
                </div>
                """
            )
            conn.execute("UPDATE reservations SET follow_up_sent = 1 WHERE id = ?", (res['id'],))
        conn.commit()

    print(f"[scheduler] Follow-up check complete — sent {len(rows)} follow-up(s).")


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(send_follow_up_emails, "interval", hours=12)
scheduler.start()


# ---------------------------------------------------------------
# CLAUDE TOOLS
# ---------------------------------------------------------------
TOOLS = [
    {
        "name": "get_availability",
        "description": (
            "Get available unit options and pricing for a specific location. "
            "Only call this AFTER you know the location AND have recommended a size to the customer. "
            "Pass the recommended size to filter results — do not fetch the full inventory. "
            "Optionally filter by climate control or access type if the customer has expressed a preference."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "enum": ["south_lyon", "highland", "lansing"],
                    "description": "Which location to check"
                },
                "size": {
                    "type": "string",
                    "description": "Filter to a specific unit size, e.g. '10x10'. Always pass this after recommending a size."
                },
                "climate": {
                    "type": "boolean",
                    "description": "Filter by climate control: true = climate only, false = non-climate only. Omit if no preference."
                },
                "access": {
                    "type": "string",
                    "enum": ["Indoor", "Drive Up", "Outdoor"],
                    "description": "Filter by access type. Omit if no preference."
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "create_reservation",
        "description": (
            "Save a reservation for a customer who wants to rent a unit. "
            "Collect their name, email, and desired unit size through conversation first. "
            "Phone and move-in date are helpful but not required."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name":         {"type": "string", "description": "Customer's full name"},
                "email":        {"type": "string", "description": "Customer's email address"},
                "phone":        {"type": "string", "description": "Customer's phone number (optional)"},
                "unit_size":    {"type": "string", "description": "Desired unit size, e.g. '10x10'"},
                "move_in_date": {"type": "string", "description": "Desired move-in date (optional)"},
                "notes":        {"type": "string", "description": "Special requests or notes (optional)"}
            },
            "required": ["name", "email", "unit_size"]
        }
    }
]


LOCATION_LABELS = {
    "south_lyon": "South Lyon",
    "highland":   "Highland",
    "lansing":    "Lansing",
}

def execute_tool(name, inputs):
    if name == "get_availability":
        location = inputs.get("location", "").lower().replace(" ", "_")
        size_filter    = inputs.get("size")
        climate_filter = inputs.get("climate")
        access_filter  = inputs.get("access")

        # ── Try Storable API first ──────────────────────────────────────────────
        if STORABLE_API_KEY and STORABLE_API_SECRET and STORABLE_FACILITY_IDS.get(location):
            raw = storable_get_units(location)
            if raw is not None:
                # Apply filters from conversation
                if size_filter:
                    def matches_size(u):
                        ut = u.get("unit_type", {})
                        w, d = ut.get("width", 0), ut.get("depth", 0)
                        return f"{w}x{d}" == size_filter.replace("×", "x") or \
                               f"{d}x{w}" == size_filter.replace("×", "x")
                    raw = [u for u in raw if matches_size(u)]
                if climate_filter is not None:
                    raw = [u for u in raw if u.get("unit_type", {}).get("climate_controlled") == climate_filter]
                if access_filter:
                    access_map = {"Drive Up": ["drive", "outside", "outdoor"], "Indoor": ["interior", "indoor"]}
                    keywords = access_map.get(access_filter, [])
                    raw = [u for u in raw if any(k in (u.get("unit_type", {}).get("kind") or "").lower() for k in keywords)]
                return format_storable_units(raw, location)

        # ── Fall back to hardcoded inventory ────────────────────────────────────
        all_units = UNITS.get(location)
        if all_units is None:
            return {"error": f"Unknown location: {location}"}
        if not all_units:
            return {"note": f"Inventory for {location} not yet loaded. Direct customer to call."}

        filtered = all_units
        if size_filter:
            filtered = [u for u in filtered if u["size"] == size_filter]
        if climate_filter is not None:
            filtered = [u for u in filtered if u["climate"] == climate_filter]
        if access_filter:
            filtered = [u for u in filtered if u["access"] == access_filter]

        if not filtered:
            available_sizes = sorted({u["size"] for u in all_units})
            return {
                "available": False,
                "message": (
                    f"No units match those criteria at {LOCATION_LABELS.get(location, location)}. "
                    f"Available sizes: {', '.join(available_sizes)}. "
                    "Tell the customer this option isn't available and suggest calling the office."
                )
            }

        loc_label  = LOCATION_LABELS.get(location, location)
        size_label = size_filter if size_filter else "all sizes"
        lines = [f"{loc_label} — {size_label} options:"]
        for u in filtered:
            if u["access"] == "Drive Up":
                label = "Drive-Up"
            elif u["climate"]:
                label = "Climate Control"
            else:
                label = "Indoor (standard)"
            line = f"• {label} — ${u['price']}/mo"
            if u["promo"]:
                line += f"  🏷 {u['promo']}"
            line += "  ✓ Reserve online" if u["book_online"] else "  📞 Call to reserve"
            lines.append(line)

        return {"result": "\n".join(lines)}

    if name == "create_reservation":
        name_val  = str(inputs.get("name",  "") or "").strip()
        email_val = str(inputs.get("email", "") or "").strip()
        unit_val  = str(inputs.get("unit_size", "") or "").strip()
        phone_val = str(inputs.get("phone", "") or "").strip()
        date_val  = str(inputs.get("move_in_date", "") or "").strip()
        notes_val = str(inputs.get("notes", "") or "").strip()
        location  = str(inputs.get("location", "") or "").strip().lower().replace(" ", "_")

        if not name_val or not email_val or not unit_val:
            return {"success": False, "error": "Name, email, and unit size are required."}

        storable_ref = None

        # ── Try to push directly into Storable ─────────────────────────────────
        facility_id = STORABLE_FACILITY_IDS.get(location)
        if STORABLE_API_KEY and STORABLE_API_SECRET and facility_id:
            try:
                result = storable_create_lead(
                    facility_id=facility_id,
                    name=name_val, email=email_val, phone=phone_val,
                    unit_id=inputs.get("unit_id", ""),   # unit UUID if available
                    move_in_date=date_val, notes=notes_val,
                )
                storable_ref = (result.get("lead") or {}).get("id")
                print(f"[storable] Lead created: {storable_ref}")
            except Exception as e:
                print(f"[storable] create_lead failed: {e} — saving locally only")

        # ── Always save locally as backup log ──────────────────────────────────
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """INSERT INTO reservations (name, email, phone, unit_size, move_in_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name_val, email_val, phone_val, unit_val, date_val, notes_val)
            )
            reservation_id = cursor.lastrowid
            conn.commit()

        res = {
            "name": name_val, "email": email_val, "phone": phone_val,
            "unit_size": unit_val, "move_in_date": date_val, "notes": notes_val,
        }
        notify_new_reservation(res)
        send_customer_confirmation(res)

        return {
            "success": True,
            "reservation_id": reservation_id,
            "storable_lead_id": storable_ref,
            "name": name_val,
            "unit_size": unit_val,
            "next_steps": "Customer will receive a confirmation email with a link to complete their rental online — pay, sign lease, and move in. Same-day move-in is available.",
        }

    return {"error": f"Unknown tool: {name}"}


def content_to_dict(content_blocks):
    """Convert SDK content block objects to plain API-compatible dicts."""
    result = []
    for block in content_blocks:
        if block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


# ---------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory("static", "demo.html")


@app.route("/units")
def units_endpoint():
    """Returns current unit inventory as JSON."""
    return jsonify(UNITS)


@app.route("/chat", methods=["POST"])
def chat():
    """Non-streaming fallback — supports tool use."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    current_messages = list(messages[-20:])
    reservation_metadata = None

    for _ in range(5):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=BUSINESS_INFO,
                tools=TOOLS,
                messages=current_messages,
            )
        except anthropic.AuthenticationError:
            return jsonify({"error": "Invalid API key."}), 401
        except anthropic.RateLimitError:
            return jsonify({"error": "Too many requests. Please try again shortly."}), 429
        except anthropic.APIStatusError as e:
            return jsonify({"error": f"API error: {e.message}"}), 500

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })
                if block.name == "create_reservation" and result.get("success"):
                    reservation_metadata = {
                        "type": "reservation_created",
                        "reservation_id": result["reservation_id"],
                        "name": result["name"],
                        "unit_size": result["unit_size"],
                    }

        current_messages.append({"role": "assistant", "content": content_to_dict(response.content)})
        current_messages.append({"role": "user",      "content": tool_results})

    reply = next((b.text for b in response.content if b.type == "text"), "")
    resp = {"reply": reply}
    if reservation_metadata:
        resp["metadata"] = reservation_metadata
    return jsonify(resp)


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    """Streaming endpoint with full tool use support."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    messages = data.get("messages", [])
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    current_messages = list(messages[-20:])

    def generate():
        nonlocal current_messages
        reservation_metadata = None

        for _ in range(5):
            try:
                with client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    system=BUSINESS_INFO,
                    tools=TOOLS,
                    messages=current_messages,
                ) as stream:
                    # Stream text tokens as they arrive
                    for text in stream.text_stream:
                        yield f"data: {json.dumps({'text': text})}\n\n"
                    final_msg = stream.get_final_message()

            except anthropic.AuthenticationError:
                yield f"data: {json.dumps({'error': 'Invalid API key.'})}\n\n"
                return
            except anthropic.RateLimitError:
                yield f"data: {json.dumps({'error': 'Too many requests. Please try again shortly.'})}\n\n"
                return
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

            if final_msg.stop_reason != "tool_use":
                break

            # Process tool calls (invisible to client — happens between streamed chunks)
            tool_results = []
            for block in final_msg.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                    if block.name == "create_reservation" and result.get("success"):
                        reservation_metadata = {
                            "type": "reservation_created",
                            "reservation_id": result["reservation_id"],
                            "name": result["name"],
                            "unit_size": result["unit_size"],
                        }

            current_messages.append({"role": "assistant", "content": content_to_dict(final_msg.content)})
            current_messages.append({"role": "user",      "content": tool_results})

        done_payload = {"done": True}
        if reservation_metadata:
            done_payload["metadata"] = reservation_metadata
        yield f"data: {json.dumps(done_payload)}\n\n"

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/feedback", methods=["POST"])
def save_feedback():
    """Save a star rating from the chat widget."""
    data   = request.get_json(silent=True) or {}
    rating = str(data.get("rating", "")).strip()
    if not rating:
        return jsonify({"error": "rating required"}), 400
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO feedback (rating) VALUES (?)", (rating,))
        conn.commit()
    print(f"[feedback] {rating}")
    send_email(
        to=NOTIFY_EMAIL,
        subject=f"Stori feedback: {rating}",
        html_body=f"""
        <div style="font-family:sans-serif;max-width:400px">
          <h2 style="color:#e87722">New Chat Feedback</h2>
          <p style="font-size:24px;margin:16px 0">{rating}</p>
          <p style="color:#888;font-size:13px">Submitted {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
        </div>
        """
    )
    return jsonify({"ok": True})


@app.route("/admin/reservations")
def admin_reservations():
    """View all reservations. Protected with ?key=ADMIN_KEY."""
    if request.args.get("key") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM reservations ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/admin/feedback")
def admin_feedback():
    """View all feedback ratings. Protected with ?key=ADMIN_KEY."""
    if request.args.get("key") != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM feedback ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", debug=False, port=port)
