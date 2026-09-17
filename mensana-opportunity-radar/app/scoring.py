"""Transparent scoring rules used before enough feedback exists for ML."""
from __future__ import annotations

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def calculate(features: dict, company: dict) -> tuple[dict, list[dict]]:
    """Return component scores and plain-English evidence for one company."""
    signals: list[dict] = []
    def add(category: str, label: str, points: float, evidence: str):
        if points > 0:
            signals.append({"category": category, "label": label, "points": round(points, 1), "evidence": evidence})

    margin = float(features.get("margin_change") or 0)
    expense = float(features.get("expense_growth") or 0)
    growth = float(features.get("revenue_growth") or 0)
    financial = clamp(max(0, -margin) * 3 + max(0, expense - growth) * 0.8, 0, 30)
    add("Financial", "Margin deterioration", clamp(max(0, -margin) * 3, 0, 15), f"Operating margin changed {margin:+.1f} points")
    add("Financial", "Expenses outpacing revenue", clamp(max(0, expense-growth)*0.8, 0, 15), f"Expenses {expense:+.1f}% versus revenue {growth:+.1f}%")

    efficiency = int(features.get("efficiency_mentions") or 0)
    costs = int(features.get("cost_mentions") or 0)
    operational = clamp(efficiency * 2 + costs * 2, 0, 20)
    add("Operational", "Operational-efficiency language", min(efficiency*2, 10), f"Found {efficiency} relevant efficiency mentions")
    add("Operational", "Cost-pressure language", min(costs*2, 10), f"Found {costs} relevant cost mentions")

    acquisition = bool(features.get("recent_acquisition"))
    restructuring = bool(features.get("restructuring"))
    management = bool(features.get("management_change"))
    transformation = min((9 if acquisition else 0)+(8 if restructuring else 0)+(5 if management else 0), 20)
    add("Transformation", "Recent acquisition", 9 if acquisition else 0, "A recent acquisition may create integration complexity")
    add("Transformation", "Restructuring", 8 if restructuring else 0, "The company disclosed restructuring activity")
    add("Transformation", "Management change", 5 if management else 0, "A senior management change was detected")

    nlp = clamp((efficiency + costs) * 1.2, 0, 20)
    target_industries = {"manufacturing", "logistics", "food & beverage", "automotive", "healthcare", "construction"}
    fit = 6 if str(company.get("industry", "")).lower() in target_industries else 3
    if (company.get("employee_count") or 0) >= 100: fit += 2
    if (company.get("revenue") or 0) >= 10_000_000: fit += 2
    fit = min(fit, 10)
    total = round(financial + operational + transformation + nlp + fit, 1)
    return ({"financial_score": round(financial,1), "operational_score": round(operational,1),
             "transformation_score": round(transformation,1), "nlp_score": round(nlp,1),
             "fit_score": round(fit,1), "heuristic_score": total, "final_score": total}, signals)
