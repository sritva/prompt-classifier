import os
import sys
import json
import time
import argparse
import statistics
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.classifier import classify_heuristically, classify_prompt

def calculate_metrics(y_true, y_pred, labels):
    metrics = {}
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        
        support = tp + fn
        if support == 0:
            continue
            
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        metrics[str(label)] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support
        }
    return metrics

def build_confusion_matrix(y_true, y_pred, labels):
    matrix = {}
    for actual in labels:
        matrix[str(actual)] = {}
        for predicted in labels:
            count = sum(1 for t, p in zip(y_true, y_pred) if t == actual and p == predicted)
            matrix[str(actual)][str(predicted)] = count
    return matrix

def print_confusion_matrix(matrix, labels):
    header = f"{'Actual \\ Predicted':<25} | " + " | ".join(f"{str(l):<15}" for l in labels)
    print(header)
    print("-" * len(header))
    for actual in labels:
        row = matrix[str(actual)]
        row_str = f"{str(actual):<25} | " + " | ".join(f"{row[str(l)]:<15}" for l in labels)
        print(row_str)

def evaluate_file(dataset_path, mode="heuristic", concurrency=4):
    if not os.path.exists(dataset_path):
        return None

    prompts = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                prompts.append(json.loads(line))

    def run_inference(item):
        prompt_text = item["prompt"]
        t0 = time.perf_counter()
        if mode == "llm":
            result = classify_prompt(prompt_text)
        else:
            result = classify_heuristically(prompt_text)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return item, result, duration_ms

    if mode == "llm" and len(prompts) > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            results_tuples = list(executor.map(run_inference, prompts))
    else:
        results_tuples = [run_inference(p) for p in prompts]

    y_true_class = []
    y_pred_class = []
    y_true_subtype = []
    y_pred_subtype = []
    latencies = []
    total_tokens_list = []
    misclassified = []
    
    for item, result, duration_ms in results_tuples:
        prompt_text = item["prompt"]
        expected_class = item["expected_classification"]
        expected_subtype = item.get("expected_subtype")
        
        latencies.append(duration_ms)
        if result.total_tokens:
            total_tokens_list.append(result.total_tokens)
        
        pred_class = result.classification
        pred_subtype = None if pred_class == "divergent" else result.subtype
        
        y_true_class.append(expected_class)
        y_pred_class.append(pred_class)
        y_true_subtype.append(expected_subtype)
        y_pred_subtype.append(pred_subtype)
        
        is_misclassified = (pred_class != expected_class) or (pred_subtype != expected_subtype)
        
        if is_misclassified:
            misclassified.append({
                "prompt": prompt_text,
                "expected": {
                    "classification": expected_class,
                    "subtype": expected_subtype
                },
                "actual": {
                    "classification": pred_class,
                    "subtype": pred_subtype,
                    "confidence": result.confidence,
                    "is_heuristic": getattr(result, "is_heuristic", False)
                }
            })
            
    correct_class = sum(1 for t, p in zip(y_true_class, y_pred_class) if t == p)
    correct_subtype = sum(1 for t, p in zip(y_true_subtype, y_pred_subtype) if t == p)
    correct_overall = sum(
        1 for tc, pc, ts, ps in zip(y_true_class, y_pred_class, y_true_subtype, y_pred_subtype)
        if tc == pc and ts == ps
    )
    
    total = len(prompts) if prompts else 1
    overall_accuracy = correct_overall / total
    class_accuracy = correct_class / total
    subtype_accuracy = correct_subtype / total
    
    class_labels = ["convergent", "divergent"]
    subtype_labels = ["factual_lookup", "computation", "code_debugging", "decision_making", "other", None]
    
    class_metrics = calculate_metrics(y_true_class, y_pred_class, class_labels)
    subtype_metrics = calculate_metrics(y_true_subtype, y_pred_subtype, subtype_labels)
    
    class_cm = build_confusion_matrix(y_true_class, y_pred_class, class_labels)
    subtype_cm = build_confusion_matrix(y_true_subtype, y_pred_subtype, subtype_labels)
    
    p50_latency = round(statistics.median(latencies), 3) if latencies else 0.0
    p95_latency = round(statistics.quantiles(latencies, n=20)[18], 3) if len(latencies) >= 20 else round(max(latencies or [0.0]), 3)
    
    return {
        "mode": mode,
        "metrics": {
            "overall_accuracy": round(overall_accuracy, 4),
            "class_accuracy": round(class_accuracy, 4),
            "subtype_accuracy": round(subtype_accuracy, 4),
            "classification": class_metrics,
            "subtype": subtype_metrics,
            "latency_ms": {
                "p50": p50_latency,
                "p95": p95_latency
            },
            "total_tokens_consumed": sum(total_tokens_list) if total_tokens_list else 0
        },
        "confusion_matrices": {
            "classification": class_cm,
            "subtype": subtype_cm
        },
        "misclassified": misclassified,
        "total_prompts": len(prompts)
    }

def verify_against_targets(results, targets_path):
    if not os.path.exists(targets_path):
        return []
        
    with open(targets_path, "r", encoding="utf-8") as f:
        targets = json.load(f)
        
    checks = []
    
    acc_targets = targets.get("accuracy", {})
    overall_acc = results["metrics"]["overall_accuracy"]
    min_overall = acc_targets.get("overall_accuracy", 0.90)
    checks.append({
        "name": "Overall Accuracy",
        "target": f">={min_overall:.2%}",
        "actual": f"{overall_acc:.2%}",
        "passed": overall_acc >= min_overall
    })
    
    subtype_targets = targets.get("subtypes", {})
    if "factual_lookup" in subtype_targets:
        target_fl_recall = subtype_targets["factual_lookup"].get("recall", 0.92)
        fl_metrics = results["metrics"]["subtype"].get("factual_lookup", {})
        actual_fl_recall = fl_metrics.get("recall", 0.0)
        checks.append({
            "name": "Factual Lookup Recall",
            "target": f">={target_fl_recall:.2%}",
            "actual": f"{actual_fl_recall:.2%}",
            "passed": actual_fl_recall >= target_fl_recall
        })
        
    latency_targets = targets.get("latency_ms", {})
    max_p50 = latency_targets.get("heuristic_p50_max", 2.0)
    actual_p50 = results["metrics"]["latency_ms"]["p50"]
    checks.append({
        "name": "Latency p50",
        "target": f"<={max_p50:.1f}ms",
        "actual": f"{actual_p50:.2f}ms",
        "passed": actual_p50 <= max_p50
    })

    return checks

def evaluate_traces_file(traces_path):
    if not os.path.exists(traces_path):
        return None
        
    from datetime import datetime, timezone, timedelta
    from app.overreliance import calculate_overreliance
    from app.models import PromptRecord
    
    traces = []
    with open(traces_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                traces.append(json.loads(line))
                
    now = datetime.now(timezone.utc)
    tp, fp, tn, fn = 0, 0, 0, 0
    results = []
    
    for trace in traces:
        records = []
        for p in trace["prompts"]:
            t = now - timedelta(minutes=p.get("offset_minutes", 1))
            res = classify_heuristically(p["prompt"])
            records.append(PromptRecord(
                classification=res.classification,
                subtype=res.subtype,
                confidence=res.confidence,
                created_at=t
            ))
            
        ov_result = calculate_overreliance(records, reference_time=now)
        predicted_signal = ov_result["signal"]
        expected_signal = trace["expected_signal"]
        
        has_warning_pred = predicted_signal in ["moderate", "high"]
        has_warning_exp = expected_signal in ["moderate", "high"]
        
        if has_warning_pred and has_warning_exp:
            tp += 1
        elif has_warning_pred and not has_warning_exp:
            fp += 1
        elif not has_warning_pred and not has_warning_exp:
            tn += 1
        else:
            fn += 1
            
        results.append({
            "session_id": trace["session_id"],
            "expected_signal": expected_signal,
            "predicted_signal": predicted_signal,
            "score": ov_result["score"]
        })
        
    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    false_warning_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    
    return {
        "precision": round(precision, 4),
        "false_warning_rate": round(false_warning_rate, 4),
        "total_traces": len(traces),
        "trace_results": results
    }

def print_report(results, filename, checks=None, traces_result=None):
    mode_str = results.get("mode", "heuristic").upper()
    print(f"\n================ EVALUATION RESULTS ({filename} | Mode: {mode_str}) ================")
    print(f"Total Prompts:                   {results['total_prompts']}")
    print(f"Overall Accuracy (Both correct): {results['metrics']['overall_accuracy'] * 100:.2f}%")
    print(f"Classification Accuracy:         {results['metrics']['class_accuracy'] * 100:.2f}%")
    print(f"Subtype Accuracy:                {results['metrics']['subtype_accuracy'] * 100:.2f}%")
    print(f"Latency p50 / p95:               {results['metrics']['latency_ms']['p50']}ms / {results['metrics']['latency_ms']['p95']}ms")
    if results['metrics'].get('total_tokens_consumed', 0) > 0:
        print(f"Total Tokens Consumed:           {results['metrics']['total_tokens_consumed']}")
    print(f"Total Misclassified:             {len(results['misclassified'])}")
    print("======================================================")
    
    class_labels = ["convergent", "divergent"]
    subtype_labels = ["factual_lookup", "computation", "code_debugging", "decision_making", "other", None]
    
    print("\n--- Classification Performance ---")
    for cls, met in results["metrics"]["classification"].items():
        print(f"{cls:<12} | P: {met['precision']:.4f} | R: {met['recall']:.4f} | F1: {met['f1']:.4f} (Support: {met['support']})")
        
    print("\n--- Subtype Performance ---")
    for sub, met in results["metrics"]["subtype"].items():
        print(f"{str(sub):<15} | P: {met['precision']:.4f} | R: {met['recall']:.4f} | F1: {met['f1']:.4f} (Support: {met['support']})")
        
    print("\n--- Classification Confusion Matrix ---")
    print_confusion_matrix(results["confusion_matrices"]["classification"], class_labels)
    
    print("\n--- Subtype Confusion Matrix ---")
    print_confusion_matrix(results["confusion_matrices"]["subtype"], subtype_labels)
    
    if traces_result:
        print("\n--- Overreliance Warning Performance ---")
        print(f"Alert Precision:    {traces_result['precision'] * 100:.2f}%")
        print(f"False Warning Rate: {traces_result['false_warning_rate'] * 100:.2f}%")
        print(f"Total Traces:       {traces_result['total_traces']}")
    
    if checks:
        print("\n--- Target Gate Check ---")
        for c in checks:
            status = "PASS" if c["passed"] else "FAIL"
            print(f"[{status}] {c['name']:<25} | Target: {c['target']:<10} | Actual: {c['actual']:<10}")

def main():
    parser = argparse.ArgumentParser(description="Evaluate Prompt Heuristics & LLM Classifier")
    parser.add_argument("--dataset", default="train.jsonl", help="Dataset path relative to evaluate.py or absolute")
    parser.add_argument("--mode", choices=["heuristic", "llm"], default="heuristic", help="Evaluation mode: heuristic fallback or real LLM classifier")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrency for LLM evaluation requests")
    parser.add_argument("--traces", default="session_traces.jsonl", help="Session traces dataset path")
    parser.add_argument("--check-targets", action="store_true", help="Fail with non-zero code if targets not met")
    args = parser.parse_args()
    
    target_filename = args.dataset
    if not os.path.isabs(target_filename):
        target_path = os.path.join(os.path.dirname(__file__), target_filename)
    else:
        target_path = target_filename
        target_filename = os.path.basename(target_filename)
        
    if not os.path.exists(target_path):
        target_path = os.path.join(os.path.dirname(__file__), "train.jsonl")
        target_filename = "train.jsonl"
        
    target_results = evaluate_file(target_path, mode=args.mode, concurrency=args.concurrency)
    
    traces_filename = args.traces
    if not os.path.isabs(traces_filename):
        traces_path = os.path.join(os.path.dirname(__file__), traces_filename)
    else:
        traces_path = traces_filename
    traces_result = evaluate_traces_file(traces_path) if os.path.exists(traces_path) else None
    
    targets_json_path = os.path.join(os.path.dirname(__file__), "targets.json")
    checks = verify_against_targets(target_results, targets_json_path)
    
    results_json_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump({
            "mode": args.mode,
            "metrics": target_results["metrics"],
            "traces": traces_result,
            "misclassified": target_results["misclassified"]
        }, f, indent=2)
        
    print_report(target_results, target_filename, checks, traces_result)
    print(f"\nResults saved to: {results_json_path}")
    
    if args.check_targets and checks and any(not c["passed"] for c in checks):
        print("\nFailure: One or more evaluation targets were not met.")
        sys.exit(1)

if __name__ == "__main__":
    main()


