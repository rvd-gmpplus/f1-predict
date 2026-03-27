import math


def score_position_based(
    predicted_driver_ids: list[int],
    actual_driver_ids: list[int],
    is_sprint: bool = False,
) -> dict:
    points_map = {0: 25, 1: 15, 2: 8}  # offset → points
    in_top5_points = 3

    actual_pos = {driver_id: pos for pos, driver_id in enumerate(actual_driver_ids[:5])}
    breakdown = []
    total = 0

    for pred_pos, driver_id in enumerate(predicted_driver_ids[:5]):
        if driver_id in actual_pos:
            offset = abs(pred_pos - actual_pos[driver_id])
            pts = points_map.get(offset, in_top5_points)
        else:
            pts = 0
        breakdown.append({"position": pred_pos + 1, "driver_id": driver_id, "points": pts})
        total += pts

    all_exact = (
        len(predicted_driver_ids) >= 5
        and len(actual_driver_ids) >= 5
        and all(predicted_driver_ids[i] == actual_driver_ids[i] for i in range(5))
    )
    bonus = all_exact

    if bonus:
        total += 10

    if is_sprint:
        total = math.floor(total * 0.5)

    return {"total": total, "breakdown": breakdown, "bonus": bonus}


def score_fastest_lap(
    predicted_driver_id: int, actual_driver_id: int,
    predicted_team_id: int, actual_team_id: int,
) -> dict:
    if predicted_driver_id == actual_driver_id:
        return {"total": 30, "close": False}
    if predicted_team_id == actual_team_id:
        return {"total": 10, "close": True}
    return {"total": 0, "close": False}


def score_constructor(
    predicted_team_id: int, actual_first_id: int, actual_second_id: int,
) -> dict:
    if predicted_team_id == actual_first_id:
        return {"total": 30, "close": False}
    if predicted_team_id == actual_second_id:
        return {"total": 10, "close": True}
    return {"total": 0, "close": False}


def score_pitstop(
    predicted_team_id: int, actual_team_id: int,
    predicted_time: float | None, actual_fastest_time: float,
    predicted_team_time: float | None = None,
) -> dict:
    if predicted_team_id == actual_team_id:
        return {"total": 30, "close": False}
    if predicted_team_time is not None and abs(predicted_team_time - actual_fastest_time) <= 0.3:
        return {"total": 10, "close": True}
    return {"total": 0, "close": False}


def score_teammate_battles(
    predicted_winners: dict[int, int], actual_winners: dict[int, int],
) -> dict:
    total = 0
    breakdown = []
    for team_id, predicted_driver in predicted_winners.items():
        correct = actual_winners.get(team_id) == predicted_driver
        pts = 5 if correct else 0
        total += pts
        breakdown.append({"team_id": team_id, "correct": correct, "points": pts})
    return {"total": total, "breakdown": breakdown}


def score_safety_car(
    predicted_yes: bool, actual_yes: bool,
    predicted_count: int, actual_count: int,
) -> dict:
    total = 0
    yes_no_correct = predicted_yes == actual_yes
    count_correct = predicted_count == actual_count
    if yes_no_correct:
        total += 10
    if yes_no_correct and predicted_yes and count_correct:
        total += 10
    return {"total": total, "yes_no_correct": yes_no_correct, "count_correct": count_correct}


def score_dnf(
    predicted_driver_ids: list[int], actual_driver_ids: list[int],
) -> dict:
    actual_set = set(actual_driver_ids)
    correct = [d for d in predicted_driver_ids if d in actual_set]
    total = len(correct) * 15
    return {"total": total, "correct_drivers": correct}


def score_tire_strategy(predicted_stops: int, actual_stops: int) -> dict:
    correct = predicted_stops == actual_stops
    return {"total": 20 if correct else 0, "correct": correct}
