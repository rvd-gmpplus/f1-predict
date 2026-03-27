from app.services.scoring import score_position_based
from app.services.scoring import score_fastest_lap, score_constructor, score_pitstop
from app.services.scoring import score_teammate_battles, score_safety_car, score_dnf, score_tire_strategy


class TestPositionBasedScoring:
    def test_exact_match_all_five(self):
        predicted = [10, 20, 30, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 135  # 125 + 10 bonus
        assert result["bonus"] is True

    def test_exact_match_single(self):
        predicted = [10, 20, 30, 40, 50]
        actual = [10, 99, 98, 97, 96]
        result = score_position_based(predicted, actual)
        assert result["total"] == 25

    def test_off_by_one(self):
        predicted = [20, 10, 30, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 15 + 15 + 75
        assert result["bonus"] is False

    def test_off_by_two(self):
        predicted = [30, 20, 10, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 8 + 25 + 8 + 50

    def test_in_top5_wrong_position(self):
        predicted = [50, 40, 30, 20, 10]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 3 + 8 + 25 + 8 + 3

    def test_not_in_top5(self):
        predicted = [90, 91, 92, 93, 94]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 0

    def test_sprint_half_weight(self):
        predicted = [10, 20, 30, 40, 50]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual, is_sprint=True)
        assert result["total"] == 67  # floor(135 * 0.5)

    def test_partial_predictions(self):
        predicted = [10, 20]
        actual = [10, 20, 30, 40, 50]
        result = score_position_based(predicted, actual)
        assert result["total"] == 50


class TestSinglePickScoring:
    def test_fastest_lap_exact(self):
        assert score_fastest_lap(10, 10, 1, 1) == {"total": 30, "close": False}

    def test_fastest_lap_same_team(self):
        assert score_fastest_lap(11, 10, 1, 1) == {"total": 10, "close": True}

    def test_fastest_lap_wrong(self):
        assert score_fastest_lap(20, 10, 2, 1) == {"total": 0, "close": False}

    def test_constructor_exact(self):
        assert score_constructor(1, 1, 2) == {"total": 30, "close": False}

    def test_constructor_second(self):
        assert score_constructor(2, 1, 2) == {"total": 10, "close": True}

    def test_constructor_wrong(self):
        assert score_constructor(3, 1, 2) == {"total": 0, "close": False}

    def test_pitstop_exact(self):
        assert score_pitstop(1, 1, None, 2.1) == {"total": 30, "close": False}

    def test_pitstop_close(self):
        assert score_pitstop(2, 1, None, 2.1, 2.3) == {"total": 10, "close": True}

    def test_pitstop_wrong(self):
        assert score_pitstop(2, 1, None, 2.1, 3.0) == {"total": 0, "close": False}


class TestSpecialCategoryScoring:
    def test_teammate_battles_all_correct(self):
        result = score_teammate_battles({1: 10, 2: 30}, {1: 10, 2: 30})
        assert result["total"] == 10

    def test_teammate_battles_mixed(self):
        result = score_teammate_battles({1: 10, 2: 30}, {1: 10, 2: 40})
        assert result["total"] == 5

    def test_safety_car_yes_correct(self):
        result = score_safety_car(True, True, 2, 2)
        assert result["total"] == 20

    def test_safety_car_yes_wrong_count(self):
        result = score_safety_car(True, True, 3, 2)
        assert result["total"] == 10

    def test_safety_car_wrong(self):
        result = score_safety_car(False, True, 0, 2)
        assert result["total"] == 0

    def test_dnf_all_correct(self):
        result = score_dnf([10, 20], [10, 20, 30])
        assert result["total"] == 30

    def test_dnf_partial(self):
        result = score_dnf([10, 20, 30], [10, 50])
        assert result["total"] == 15

    def test_dnf_none_correct(self):
        result = score_dnf([10, 20], [30, 40])
        assert result["total"] == 0

    def test_tire_strategy_correct(self):
        result = score_tire_strategy(2, 2)
        assert result["total"] == 20

    def test_tire_strategy_wrong(self):
        result = score_tire_strategy(1, 2)
        assert result["total"] == 0
