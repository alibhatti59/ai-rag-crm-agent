import os
import json
import re
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai
from retriever import hybrid_search

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-flash-lite-latest")

GHL_TOKEN = os.getenv("GHL_TOKEN")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
GHL_CALENDAR_ID = os.getenv("GHL_CALENDAR_ID")

if not GHL_CALENDAR_ID:
    raise ValueError("GHL_CALENDAR_ID is not set in your .env file")

# In-memory tracker for auto-tagging (resets on server restart — fine for a portfolio demo)
_pricing_question_count = {}

# In-memory session store: remembers each user's email once provided,
# until they give a new one (resets on server restart — fine for a portfolio demo)
_user_email_sessions = {}


def extract_email(text):
    # Handle Slack's auto-linked format: <mailto:email@example.com|email@example.com>
    slack_link_match = re.search(r'mailto:([\w\.-]+@[\w\.-]+\.\w+)', text)
    if slack_link_match:
        return slack_link_match.group(1)

    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None


def get_or_extract_email(user_id, query, explicit_email=None):
    """Returns the email to use: explicitly passed > extracted from message > remembered from session.
    Whatever email is used gets saved, so future messages from the same user reuse it
    until they provide a different one."""
    if explicit_email:
        _user_email_sessions[user_id] = explicit_email
        return explicit_email

    extracted = extract_email(query)
    if extracted:
        _user_email_sessions[user_id] = extracted
        return extracted

    return _user_email_sessions.get(user_id)


def search_ghl_contact_raw(email):
    """Returns the raw contact dict (or None), used internally by other functions."""
    url = "https://services.leadconnectorhq.com/contacts/search"
    headers = {
        "Authorization": f"Bearer {GHL_TOKEN}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
    }
    body = {
        "locationId": GHL_LOCATION_ID,
        "pageLimit": 1,
        "filters": [{"field": "email", "operator": "eq", "value": email}],
    }
    response = requests.post(url, headers=headers, json=body)
    data = response.json()
    contacts = data.get("contacts", [])
    return contacts[0] if contacts else None


def search_ghl_contact(email):
    """Live tool call: check if a contact exists in GHL by email."""
    contact = search_ghl_contact_raw(email)
    if contact:
        return f"Found contact: {contact.get('contactName', 'Unknown')}, added on {contact.get('dateAdded', 'unknown date')}."
    return "No contact found with that email."


def get_appointment_status(email):
    """Live tool call: check if the contact has an upcoming appointment in GHL."""
    contact = search_ghl_contact_raw(email)
    if not contact:
        return "I couldn't find your contact record, so I can't check appointment status."

    contact_id = contact["id"]

    url = "https://services.leadconnectorhq.com/calendars/events"
    headers = {
        "Authorization": f"Bearer {GHL_TOKEN}",
        "Version": "2021-04-15",
    }
    params = {
        "locationId": GHL_LOCATION_ID,
        "calendarId": GHL_CALENDAR_ID,
        "startTime": int(time.time() * 1000),
        "endTime": int((time.time() + 30 * 24 * 60 * 60) * 1000),
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    events = data.get("events", [])

    matching = [e for e in events if e.get("contactId") == contact_id]

    if matching:
        appt = matching[0]
        raw_time = appt.get("startTime")
        try:
            dt = datetime.fromisoformat(raw_time)
            formatted = dt.strftime("%A, %B %d, %Y at %I:%M %p")
        except (ValueError, TypeError):
            formatted = raw_time
        return f"Your appointment is scheduled for {formatted}."
    return "You don't have any upcoming appointments scheduled right now."


def add_tag_to_contact(contact_id, tag):
    """Adds a tag to a GHL contact."""
    url = f"https://services.leadconnectorhq.com/contacts/{contact_id}/tags"
    headers = {
        "Authorization": f"Bearer {GHL_TOKEN}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
    }
    body = {"tags": [tag]}
    requests.post(url, headers=headers, json=body)


def track_and_tag_if_high_intent(email, query):
    """If a contact asks pricing-related questions repeatedly, tag them as high-intent in GHL."""
    pricing_keywords = ["price", "pricing", "cost", "plan", "how much"]
    if not any(kw in query.lower() for kw in pricing_keywords) or not email:
        return

    _pricing_question_count[email] = _pricing_question_count.get(email, 0) + 1
    print(f"[DEBUG] Pricing question count for {email}: {_pricing_question_count[email]}")

    if _pricing_question_count[email] == 2:  # tag after 2nd pricing question
        contact = search_ghl_contact_raw(email)
        if contact:
            add_tag_to_contact(contact["id"], "high-intent")
            print(f"[DEBUG] Tagged {email} as high-intent")


def decide_action(query):
    """Step 1: Ask the LLM to classify what kind of request this is."""
    prompt = f"""Classify this user query into exactly one category. Respond ONLY with the category word.

Categories:
- DOCS: any question seeking factual information, even if unrelated to this business (pricing, policies, FAQs, or ANY other factual/informational question)
- CRM_LOOKUP: question asking to check/verify their own account or contact status (requires an email)
- APPOINTMENT_STATUS: question asking about their own upcoming appointment/booking
- GENERAL: ONLY greetings, thanks, or casual small talk — NOT factual questions

Query: {query}

Category:"""
    response = model.generate_content(prompt)
    return response.text.strip().upper()


def answer_query(query, user_email=None, user_id="default"):
    # Resolve which email to use: explicit > extracted from this message > remembered from session
    user_email = get_or_extract_email(user_id, query, explicit_email=user_email)
    print(f"[DEBUG] Using email for user '{user_id}': {user_email}")

    action = decide_action(query)
    print(f"[DEBUG] Classified as: {action}")

    if action == "CRM_LOOKUP":
        if not user_email:
            return "I can check that for you — what's the email associated with your account?"
        return search_ghl_contact(user_email)

    elif action == "APPOINTMENT_STATUS":
        if not user_email:
            return "I can check that for you — what's the email associated with your account?"
        return get_appointment_status(user_email)

    elif action == "DOCS":
        if user_email:
            track_and_tag_if_high_intent(user_email, query)

        results = hybrid_search(query)
        context = "\n\n".join([doc.page_content for doc in results])
        sources = list(set([doc.metadata.get("source", "unknown") for doc in results]))

        prompt = f"""Answer the user's question using ONLY the context below.

Context:
{context}

Question: {query}

Respond ONLY in this exact JSON format:
{{"answer": "your answer here, or 'I don't have that information' if the context doesn't cover it", "confidence": "HIGH/MEDIUM/LOW"}}

Rules:
- confidence HIGH: the context directly and clearly answers the question
- confidence MEDIUM: the context partially relates but doesn't fully answer it
- confidence LOW: the context doesn't meaningfully address the question at all
- If confidence is LOW, the answer must be "I don't have that information."
"""
        response = model.generate_content(prompt)
        cleaned = response.text.strip().replace("```json", "").replace("```", "").strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            return "I don't have that information right now. Could you rephrase your question?"

        if parsed.get("confidence") == "LOW":
            return "I don't have that information in my knowledge base. Would you like me to connect you with a team member?"

        answer = parsed.get("answer", "I don't have that information.")
        return f"{answer}\n\n📄 Sources: {', '.join(sources)} | Confidence: {parsed.get('confidence')}"

    else:
        response = model.generate_content(f"Respond briefly and naturally: {query}")
        return response.text.strip()


if __name__ == "__main__":
    print(answer_query("What's your refund policy?", user_id="test_user"))
    print("\n---\n")
    print(answer_query("What's the weather like on Mars?", user_id="test_user"))
    print("\n---\n")
    print(answer_query("Can you check if I'm already a customer? My email is test@gmail.com", user_id="test_user"))
    print("\n---\n")
    print(answer_query("When's my next appointment?", user_id="test_user"))  # no email — should reuse remembered one
    print("\n---\n")
    print(answer_query("What's your pricing?", user_id="test_user"))
    print(answer_query("How much does it cost?", user_id="test_user"))  # 2nd pricing Q — should trigger tag
    print("\n---\n")
    print(answer_query("Actually check alibhatti59110@gmail.com instead", user_id="test_user"))  # should switch email