# Stori Chatbot — Owner's Guide

Stori is already set up and running on your website. This guide covers the **only two things you'll ever need to update yourself**: business information and promotions.

Everything else — availability, reservations, and pricing — will be pulled automatically from Storable once the API connection is fully activated.

---

## What Stori Does

Stori is the AI chat assistant on your website. When a visitor opens it, Stori:

- Asks what they're looking to store and recommends the right unit size
- Shows available units and pricing at the location they choose
- Lets customers reserve a unit online and sends them a confirmation email
- Answers questions about hours, policies, directions, boat/RV storage, and more
- Asks for a star rating at the end of every conversation — you'll get an email with each rating

---

## About Storable

Once your Storable API access is approved, Stori will automatically:

- Show **live, real-time unit availability** pulled directly from your Storable account
- Send reservations **directly into Storable** as leads
- Email customers a link to **complete their rental online** — pay, sign their lease, and move in through Storable's ClickandStor system

Until then, Stori uses the unit inventory that was entered during setup and works exactly the same way for customers.

---

## How to Update Business Information

Business information lives in one file: **`app.py`**

Open it in any text editor (Notepad on Windows, TextEdit on Mac) and use the **Find** feature (Ctrl+F on Windows, Cmd+F on Mac) to search for what you want to change.

---

### Updating Hours

Search for: `Office Hours`

You'll find three entries — one per location. Edit the times directly.

**Example — current:**
```
Office Hours: Tue–Fri 9:30 AM–6:00 PM, Sat 8:00 AM–4:30 PM, Sun–Mon Closed
```

**Example — updated:**
```
Office Hours: Mon–Fri 9:00 AM–6:00 PM, Sat 9:00 AM–5:00 PM, Sun Closed
```

---

### Updating Phone Numbers

Search for: `Phone:` (with a capital P)

You'll find one phone number per location. Replace the number with the new one.

---

### Updating Addresses

Search for: `Address:` (with a capital A)

Replace the address text. If the address changes, also update the Google Maps link on the line directly below it — replace the part after `query=` with the new address, using `+` instead of spaces.

**Example:**
```
https://www.google.com/maps/search/?api=1&query=500+N+Milford+Rd+Highland+MI+48357
```

---

### Updating Promotions

Promotions appear in two places in `app.py`.

---

**1. Per-unit promotions** (shown next to a specific unit when a customer asks about pricing)

Search for the unit size you want to update, for example: `10x10`

Each unit has a `"promo"` field. To add or change a promotion, replace the text between the quotes:

```
"promo": "1st Month $1"
```

To remove a promotion entirely, replace it with `None` (no quotes):

```
"promo": None
```

---

**2. General promotions** (what Stori says when someone asks about deals in general)

Search for: `CURRENT PROMOTIONS:`

Edit the lines below it. Keep each item on its own line starting with `- `

**Example:**
```
CURRENT PROMOTIONS:
- First month free on all 10×10 units through June
- Military, First Responder, and School Employee discounts with valid ID
- Prepaid discounts available — ask about 3-month and 6-month options
```

---

## After Making Any Change

Save the file and let your developer know so they can restart the chatbot. Changes take effect as soon as it restarts — usually takes less than a minute.

---

## Viewing Reservations and Feedback

Your developer can set up a link for you to view all reservations and star ratings at any time. You'll also receive an email notification for every new reservation and every feedback rating automatically.
