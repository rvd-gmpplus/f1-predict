from app.services.scoring import (
    score_position_based, score_fastest_lap, score_constructor, score_pitstop,
    score_teammate_battles, score_safety_car, score_dnf, score_tire_strategy,
)


def calculate_user_race_score(
    prediction_details: list[dict], actual_results: dict, is_sprint_weekend: bool = False,
) -> dict:
    by_category: dict[str, list[dict]] = {}
    for detail in prediction_details:
        by_category.setdefault(detail["category"], []).append(detail)

    scores = {}
    grand_total = 0

    for cat, is_sprint in [("qualifying_top5", False), ("race_top5", False), ("sprint_top5", True)]:
        if cat in by_category and cat in actual_results:
            predicted = sorted(by_category[cat], key=lambda d: d.get("position", 99))
            predicted_ids = [d["driver_id"] for d in predicted]
            result = score_position_based(predicted_ids, actual_results[cat], is_sprint=is_sprint)
            scores[cat] = result
            grand_total += result["total"]

    if "fastest_lap" in by_category and "fastest_lap" in actual_results:
        pred = by_category["fastest_lap"][0]
        actual = actual_results["fastest_lap"]
        result = score_fastest_lap(pred["driver_id"], actual["driver_id"], pred.get("team_id", 0), actual.get("team_id", 0))
        scores["fastest_lap"] = result
        grand_total += result["total"]

    if "constructor_points" in by_category and "constructor_points" in actual_results:
        pred = by_category["constructor_points"][0]
        actual = actual_results["constructor_points"]
        result = score_constructor(pred["team_id"], actual["first_id"], actual["second_id"])
        scores["constructor_points"] = result
        grand_total += result["total"]

    if "quickest_pitstop" in by_category and "quickest_pitstop" in actual_results:
        pred = by_category["quickest_pitstop"][0]
        actual = actual_results["quickest_pitstop"]
        result = score_pitstop(pred["team_id"], actual["team_id"], None, actual["fastest_time"], actual.get("predicted_team_time"))
        scores["quickest_pitstop"] = result
        grand_total += result["total"]

    if "teammate_battle" in by_category and "teammate_battle" in actual_results:
        predicted_winners = {}
        for d in by_category["teammate_battle"]:
            if d.get("team_id") and d.get("driver_id"):
                predicted_winners[d["team_id"]] = d["driver_id"]
        result = score_teammate_battles(predicted_winners, actual_results["teammate_battle"])
        scores["teammate_battle"] = result
        grand_total += result["total"]

    if "safety_car" in by_category and "safety_car" in actual_results:
        pred = by_category["safety_car"][0]
        actual = actual_results["safety_car"]
        pred_yes = pred.get("value", "").lower() == "yes"
        pred_count = int(pred.get("position") or 0)
        result = score_safety_car(pred_yes, actual["yes"], pred_count, actual["count"])
        scores["safety_car"] = result
        grand_total += result["total"]

    if "dnf" in by_category and "dnf" in actual_results:
        predicted_ids = [d["driver_id"] for d in by_category["dnf"] if d.get("driver_id")]
        result = score_dnf(predicted_ids, actual_results["dnf"])
        scores["dnf"] = result
        grand_total += result["total"]

    if "tire_strategy" in by_category and "tire_strategy" in actual_results:
        pred = by_category["tire_strategy"][0]
        pred_stops = int(pred.get("value") or pred.get("position") or 0)
        result = score_tire_strategy(pred_stops, actual_results["tire_strategy"])
        scores["tire_strategy"] = result
        grand_total += result["total"]

    scores["grand_total"] = grand_total
    return scores
