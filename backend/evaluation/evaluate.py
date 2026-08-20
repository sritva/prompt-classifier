import os
import sys
import json
import argparse

# Ensure parent directory is in sys.path to import app.classifier
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.classifier import classify_heuristically

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

def evaluate_file(dataset_path):
    if not os.path.exists(dataset_path):
        return None

    prompts = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                prompts.append(json.loads(line))

    y_true_class = []
    y_pred_class = []
    y_true_subtype = []
    y_pred_subtype = []
    
    misclassified = []
    
    for item in prompts:
        prompt_text = item["prompt"]
        expected_class = item["expected_classification"]
        expected_subtype = item["expected_subtype"]
        
        result = classify_heuristically(prompt_text)
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
                    "subtype": pred_subtype
                }
            })
            
    # Calculate overall accuracy
    correct_class = sum(1 for t, p in zip(y_true_class, y_pred_class) if t == p)
    correct_subtype = sum(1 for t, p in zip(y_true_subtype, y_pred_subtype) if t == p)
    correct_overall = sum(
        1 for tc, pc, ts, ps in zip(y_true_class, y_pred_class, y_true_subtype, y_pred_subtype)
        if tc == pc and ts == ps
    )
    
    overall_accuracy = correct_overall / len(prompts)
    class_accuracy = correct_class / len(prompts)
    subtype_accuracy = correct_subtype / len(prompts)
    
    class_labels = ["convergent", "divergent"]
    subtype_labels = ["factual_lookup", "computation", "code_debugging", "decision_making", "other", None]
    
    class_metrics = calculate_metrics(y_true_class, y_pred_class, class_labels)
    subtype_metrics = calculate_metrics(y_true_subtype, y_pred_subtype, subtype_labels)
    
    class_cm = build_confusion_matrix(y_true_class, y_pred_class, class_labels)
    subtype_cm = build_confusion_matrix(y_true_subtype, y_pred_subtype, subtype_labels)
    
    return {
        "metrics": {
            "overall_accuracy": round(overall_accuracy, 4),
            "class_accuracy": round(class_accuracy, 4),
            "subtype_accuracy": round(subtype_accuracy, 4),
            "classification": class_metrics,
            "subtype": subtype_metrics
        },
        "confusion_matrices": {
            "classification": class_cm,
            "subtype": subtype_cm
        },
        "misclassified": misclassified,
        "total_prompts": len(prompts)
    }

def print_report(results, filename):
    print(f"\n================ EVALUATION RESULTS ({filename}) ================")
    print(f"Total Prompts:                   {results['total_prompts']}")
    print(f"Overall Accuracy (Both correct): {results['metrics']['overall_accuracy'] * 100:.2f}%")
    print(f"Classification Accuracy:         {results['metrics']['class_accuracy'] * 100:.2f}%")
    print(f"Subtype Accuracy:                {results['metrics']['subtype_accuracy'] * 100:.2f}%")
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

def main():
    parser = argparse.ArgumentParser(description="Evaluate Prompt Heuristics")
    parser.add_argument("--dataset", default="dataset.jsonl", help="Dataset path relative to evaluate.py or absolute")
    args = parser.parse_args()
    
    # Resolve target dataset path
    target_filename = args.dataset
    if not os.path.isabs(target_filename):
        target_path = os.path.join(os.path.dirname(__file__), target_filename)
    else:
        target_path = target_filename
        target_filename = os.path.basename(target_filename)
        
    if not os.path.exists(target_path):
        print(f"Error: Target dataset file not found at {target_path}")
        sys.exit(1)
        
    target_results = evaluate_file(target_path)
    
    # Save target results to results.json
    results_json_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(target_results, f, indent=2)
        
    # Print target dataset report
    print_report(target_results, target_filename)
    print(f"\nResults saved to: {results_json_path}")
    print(f"Misclassified examples count: {len(target_results['misclassified'])}")
    
    # Check if we can display side-by-side comparison of train vs holdout
    train_path = os.path.join(os.path.dirname(__file__), "dataset_train.jsonl")
    if not os.path.exists(train_path):
        train_path = os.path.join(os.path.dirname(__file__), "dataset.jsonl")
    holdout_path = os.path.join(os.path.dirname(__file__), "dataset_holdout.jsonl")
    
    if os.path.exists(train_path) and os.path.exists(holdout_path):
        train_results = evaluate_file(train_path)
        holdout_results = evaluate_file(holdout_path)
        
        print("\n=================== DATASET COMPARISON ===================")
        print(f"{'Metric / Subtype':<25} | {'Original (Train) (' + str(train_results['total_prompts']) + ')':<20} | {'Holdout (' + str(holdout_results['total_prompts']) + ')':<20}")
        print("-" * 75)
        
        # Overall accuracy
        train_acc = train_results["metrics"]["overall_accuracy"]
        holdout_acc = holdout_results["metrics"]["overall_accuracy"]
        print(f"{'Overall Accuracy':<25} | {train_acc * 100:.2f}% | {holdout_acc * 100:.2f}%")
        
        # Factual lookup metrics
        train_fl = train_results["metrics"]["subtype"].get("factual_lookup", {"precision": 0, "recall": 0, "f1": 0})
        holdout_fl = holdout_results["metrics"]["subtype"].get("factual_lookup", {"precision": 0, "recall": 0, "f1": 0})
        
        print(f"{'Factual Precision':<25} | {train_fl['precision']:.4f} | {holdout_fl['precision']:.4f}")
        print(f"{'Factual Recall':<25} | {train_fl['recall']:.4f} | {holdout_fl['recall']:.4f}")
        print(f"{'Factual F1-Score':<25} | {train_fl['f1']:.4f} | {holdout_fl['f1']:.4f}")
        print("==========================================================")

if __name__ == "__main__":
    main()
