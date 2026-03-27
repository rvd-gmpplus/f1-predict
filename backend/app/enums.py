import enum


class PredictionCategory(str, enum.Enum):
    QUALIFYING_TOP5 = "qualifying_top5"
    RACE_TOP5 = "race_top5"
    SPRINT_TOP5 = "sprint_top5"
    FASTEST_LAP = "fastest_lap"
    CONSTRUCTOR_POINTS = "constructor_points"
    QUICKEST_PITSTOP = "quickest_pitstop"
    TEAMMATE_BATTLE = "teammate_battle"
    SAFETY_CAR = "safety_car"
    DNF = "dnf"
    TIRE_STRATEGY = "tire_strategy"


class SessionStage(str, enum.Enum):
    PRE = "pre"
    FP1 = "fp1"
    FP2 = "fp2"
    FP3 = "fp3"
    QUALI = "quali"


class RaceStatus(str, enum.Enum):
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"
