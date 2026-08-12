EVAL_CASES = [
    {
        "query": "What's your refund policy?",
        "expected_source": "policies.md",
        "expected_keywords": ["14-day", "money-back"],
    },
    {
        "query": "What CRMs do you integrate with?",
        "expected_source": "faq.md",
        "expected_keywords": ["GoHighLevel", "HubSpot", "Salesforce"],
    },
    {
        "query": "Is there a free trial?",
        "expected_source": "faq.md",
        "expected_keywords": ["money-back", "guarantee"],
        "type": "standard",
    },
    {
        "query": "What's the capital of France?",
        "expected_source": None,  # should NOT find an answer — tests hallucination resistance
        "expected_keywords": ["don't have that information"],
    },
    {
        "query": "What happens if I go over my lead limit?",
        "expected_source": "faq.md",
        "expected_keywords": ["overage", "0.50"],
    },
    {
        "query": "What happens after the trial ends, do I need to do anything?",
        "expected_source": "faq.md",
        "expected_keywords": ["money-back", "guarantee"],
        "type": "partial_coverage",
    },
    {
        "query": "can i cancle my acount",
        "expected_source": "faq.md",
        "expected_keywords": ["cancel", "anytime"],
        "type": "misspelled",
    },
    {
        "query": "I want to know if my account is active and also what plans you offer",
        "expected_source": "pricing.md",
        "expected_keywords": ["Starter", "Growth", "Enterprise"],
        "type": "ambiguous_mixed_intent",
    },
]
