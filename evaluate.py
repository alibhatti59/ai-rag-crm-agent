import time
from agent import answer_query, decide_action
from eval_dataset import EVAL_CASES


def call_with_retry(func, *args, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 10
                print(f"   Rate limited, waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                return f"ERROR: {e}"


def run_evaluation():
    results = []
    passed = 0
    correctly_classified = 0

    for i, case in enumerate(EVAL_CASES, 1):
        query = case["query"]
        expected_source = case["expected_source"]
        expected_keywords = case["expected_keywords"]
        case_type = case.get("type", "standard")

        print(f"[{i}/{len(EVAL_CASES)}] Testing ({case_type}): {query}")

        classification = call_with_retry(decide_action, query)
        time.sleep(2)  # give quota room between the two calls for this case

        expected_classification = "CRM_LOOKUP" if "check" in query.lower() and "email" in str(case) else "DOCS"
        classification_correct = classification == expected_classification or (
            expected_source is None and classification == "DOCS"
        )
        if classification_correct:
            correctly_classified += 1

        answer = call_with_retry(answer_query, query)

        keyword_hit = any(kw.lower() in str(answer).lower() for kw in expected_keywords)
        source_hit = True
        if expected_source:
            source_hit = expected_source in str(answer)

        passed_case = keyword_hit and source_hit
        if passed_case:
            passed += 1

        results.append({
            "query": query,
            "type": case_type,
            "answer": answer,
            "classification": classification,
            "classification_correct": classification_correct,
            "expected_keywords": expected_keywords,
            "expected_source": expected_source,
            "keyword_hit": keyword_hit,
            "source_hit": source_hit,
            "passed": passed_case,
        })

        time.sleep(2)  # bigger gap between full cases to respect 15/min limit

    print("\n" + "=" * 55)
    print(f"ANSWER ACCURACY:         {passed}/{len(EVAL_CASES)} ({passed/len(EVAL_CASES)*100:.0f}%)")
    print(f"CLASSIFICATION ACCURACY: {correctly_classified}/{len(EVAL_CASES)} ({correctly_classified/len(EVAL_CASES)*100:.0f}%)")
    print("=" * 55 + "\n")

    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        class_status = "✅" if r["classification_correct"] else "❌"
        print(f"{status} | [{r['type']}] {r['query']}")
        print(f"   Classification: {r['classification']} {class_status}")
        if not r["passed"]:
            print(f"   Answer: {str(r['answer'])[:150]}")
            print(f"   Expected keywords: {r['expected_keywords']}, Expected source: {r['expected_source']}")

    return results


if __name__ == "__main__":
    run_evaluation()