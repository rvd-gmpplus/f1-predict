# F1 Predict — Design Specification

## Overview

A public-facing F1 race prediction web application where users submit predictions for each race weekend and compete against each other and an AI model on a season-long leaderboard. The AI model uses historical data (2025 season) and current season results (2026) to generate predictions that evolve throughout each race weekend as practice/qualifying session data becomes available.

## Goals

- Let users predict qualifying top 5, race top 5, fastest lap, constructor points, quickest pit stop, sprint top 5, teammate battles, safety car, DNFs, and tire strategy
- Provide AI-generated predictions that update after each session (FP1, FP2, FP3, Qualifying)
- Score predictions automatically and maintain a season-long leaderboard
- The AI competes on the leaderboard alongside human users
- Support public registration with both social login and email/password auth

## Tech Stack

| Layer | Technology | Hosting |
|-------|-----------|---------|
| Frontend | Next.js (React) | Vercel |
| Backend API | Python FastAPI | Railway |
| Background Jobs | APScheduler (in-process) | Railway (same service) |
| Database | PostgreSQL | Railway (managed) |
| Cache | Redis | Railway (managed) |
| ML Models | XGBoost, Random Forest, Linear Regression, Decision Tree | Trained on Railway, models stored in PostgreSQL/filesystem |
| Data Sources | Jolyon API, FastF1, OpenWeatherMap | External APIs |

## Architecture

Single FastAPI backend with APScheduler for background tasks. The scheduler handles:
- Data ingestion from Jolyon API and FastF1 after each session
- ML model retraining with new session data
- Prediction generation at each weekend stage
- Score calculation after qualifying and race
- Leaderboard cache refresh

The frontend communicates with the backend via REST API. Redis caches leaderboard rankings, current AI predictions, and session status.

### Why monolith + background workers over microservices

Starting with a single deployable unit keeps operational complexity low. APScheduler runs ML jobs asynchronously so they never block API requests. If scale demands it later, the scheduler jobs can be extracted into a separate worker service without changing the API.

## Data Model

### User
- id (PK), email, username, hashed_password (nullable for OAuth-only users), oauth_provider, oauth_id, avatar_url, created_at, total_score

### Team
- id (PK), name, short_name, color_hex, country, active

### Driver
- id (PK), code (e.g. "VER"), full_name, team_id (FK → Team), number, country, active

### RaceWeekend
- id (PK), season, round, name, circuit_id, country, is_sprint_weekend
- fp1_time, fp2_time, fp3_time, quali_time, race_time
- prediction_deadline (set to quali_time by default)
- status: upcoming | active | completed

### UserPrediction
- id (PK), user_id (FK → User), race_weekend_id (FK → RaceWeekend), submitted_at, locked (bool)
- One row per user per race weekend. Uniquely constrained on (user_id, race_weekend_id).

### PredictionDetail
- id (PK), prediction_id (FK → UserPrediction), category (enum), position (nullable), driver_id (FK, nullable), team_id (FK, nullable), value (string, nullable)
- Multiple rows per prediction, one per category slot.

### Category Enum
- QUALIFYING_TOP5, RACE_TOP5, SPRINT_TOP5
- FASTEST_LAP, CONSTRUCTOR_POINTS, QUICKEST_PITSTOP
- TEAMMATE_BATTLE, SAFETY_CAR, DNF, TIRE_STRATEGY

### ActualResult
- id (PK), race_weekend_id (FK → RaceWeekend), category (enum), position (nullable), driver_id (FK, nullable), team_id (FK, nullable), value (nullable)
- Mirrors PredictionDetail structure for straightforward scoring comparison.

### MLPrediction
- id (PK), race_weekend_id (FK → RaceWeekend), category (enum), position (nullable), driver_id (FK, nullable), team_id (FK, nullable), confidence (float 0-1), model_version (string), session_stage (enum: pre | fp1 | fp2 | fp3 | quali), generated_at
- New rows generated at each stage — historical stages preserved to show confidence evolution.

### UserScore
- id (PK), user_id (FK → User), race_weekend_id (FK → RaceWeekend), category (enum), points_earned (int), breakdown (JSON)
- Breakdown JSON contains per-position scoring detail for the UI.

## Scoring System

### Position-Based (Qualifying Top 5, Race Top 5, Sprint Top 5)

| Accuracy | Points |
|----------|--------|
| Exact position | 25 |
| Off by 1 | 15 |
| Off by 2 | 8 |
| In top 5, wrong position (off by 3+) | 3 |
| Not in top 5 | 0 |

- Per category max: 5 positions × 25 = 125 points
- Sprint scoring uses same scale but weighted ×0.5 (max 62.5, rounded down to 62)
- Bonus: if a user predicts all 5 positions exactly correct in any top-5 category, award 10 bonus points ("Perfect 5")

### Single-Pick Categories

| Category | Correct | Close | Close Definition |
|----------|---------|-------|-----------------|
| Fastest Lap | 30 | 10 | Same team as actual FL holder |
| Constructor Points | 30 | 10 | Picked the team that finished 2nd in race points |
| Quickest Pit Stop | 30 | 10 | Picked a team within 0.3s of fastest pit time |

### Special Categories

| Category | Format | Points |
|----------|--------|--------|
| Teammate Battle | Pick winner per team pair (10 pairs) | 5 per correct pick (max 50) |
| Safety Car | Yes/No + count | 10 for yes/no correct, +10 for exact count (max 20) |
| DNF | Pick 0-3 drivers to retire | 15 per correct DNF (max 45) |
| Tire Strategy | Winner's pit stop count | 20 for correct |

### Max Points Per Weekend

- Regular weekend: 125 + 125 + 30 + 30 + 30 + 50 + 20 + 45 + 20 = **475 points**
- Sprint weekend: 475 + 62 = **537 points**

## ML Prediction Pipeline

### Weekend Timeline

1. **Pre-Weekend (Tuesday)** — Baseline predictions using historical data, standings, driver/team form, weather forecast. All categories predicted.
2. **After FP1 (Friday)** — FastF1 auto-fetch. Retrain with FP1 lap times, sector splits, long-run pace, tire wear rates.
3. **After FP2 (Friday)** — Refine with race sim pace, tire strategy signals, updated weather.
4. **After FP3 (Saturday morning)** — Final qualifying prediction update using qualifying sim runs. **User prediction deadline.**
5. **After Qualifying (Saturday)** — Score qualifying predictions. Update race predictions using actual grid positions, Q1/Q2/Q3 sector times, penalties.
6. **After Race (Sunday)** — Score all remaining categories, update leaderboard, store results for future training.

### Models by Category

| Prediction | Model | Key Features |
|-----------|-------|-------------|
| Qualifying positions | XGBoost Ranker | Practice pace, track history, team performance, weather, sector times |
| Race positions | XGBoost Ranker | Grid position, race pace, tire degradation, pit history, overtaking record |
| Fastest lap | XGBoost Classifier | Raw pace, fresh tire strategy, historical FL %, track type |
| Constructor points | Ensemble | Both drivers' predicted positions, reliability, points trend |
| Pit stop speed | Linear Regression | Team avg pit time, recent trend, track pit lane length |
| Safety car | Random Forest | Track SC history, weather, race start incidents, field spread |
| DNF | Random Forest | Reliability record, PU age, weather, track abrasiveness |
| Tire strategy | Decision Tree | Track degradation, compound gaps, race length, weather, historical strategies |

### Training Data

- Full 2025 season (all races)
- 2026 season races held so far (Australia, China)
- Growing dataset: each completed race adds to training data for future predictions

### Data Sources

- **Jolyon API**: Race results, qualifying results, standings, pit stop times, race schedules, driver/team info
- **FastF1**: Practice/qualifying/race telemetry, sector times, tire compound data, weather conditions per session
- **OpenWeatherMap**: Pre-race weather forecasts for prediction stages before session data is available

## Authentication

- **Email + password**: Standard registration with hashed passwords (bcrypt)
- **Google OAuth**: Social login via Google
- **GitHub OAuth**: Social login via GitHub
- JWT tokens for API authentication, stored in httpOnly cookies
- Users who sign up via OAuth can optionally set a password later

## Frontend Pages

### 1. Dashboard (Race Weekend Hub)
- Current weekend header: race name, circuit, round, dates
- Countdown timer to prediction deadline
- User stats: season rank, total points, weekend session status, prediction status
- AI predictions panel: current top 5 for quali/race, specials, with confidence percentages
- Confidence stage indicator: shows which session stage the AI predictions reflect

### 2. Predict (Submission Form)
- Driver dropdowns for qualifying top 5 and race top 5 (drag-and-drop reorder)
- Driver picker for fastest lap
- Team pickers for constructor points and quickest pit stop
- Teammate battle: toggle per team pair
- Safety car: yes/no toggle + count selector
- DNF: multi-select up to 3 drivers
- Tire strategy: pit stop count selector
- Sprint top 5 (shown only on sprint weekends)
- Lock button with confirmation dialog and deadline warning
- Form disabled after deadline with "locked" state display

### 3. Leaderboard
- Three tabs: Season, Last Race, vs AI
- Season: cumulative points, participation count, personal best weekend, trend indicator
- Last Race: single-race breakdown with per-category scores
- vs AI: head-to-head comparison showing which races users beat the AI
- AI model listed as a participant in the leaderboard

### 4. AI Insights
- Confidence evolution chart: bar/line chart showing how AI confidence for each prediction changed across weekend stages (Pre → FP1 → FP2 → FP3 → Quali)
- Explanation text: why the model changed its mind (e.g., "VER's FP2 long-run pace was 0.3s faster than NOR")
- Model accuracy tracker: how the AI has performed across the season
- Category breakdown: which prediction types the AI is best/worst at

### 5. Calendar
- Season schedule with all race weekends
- Status badges: completed, active, upcoming
- Links to each weekend's predictions and results
- Sprint weekend indicators

### 6. My History
- Personal prediction accuracy over time
- Best/worst categories
- Season progression chart
- Head-to-head record vs AI
- Per-race breakdown with expandable scoring details

## API Endpoints (Key Routes)

### Auth
- `POST /auth/register` — email/password registration
- `POST /auth/login` — email/password login
- `GET /auth/google` — Google OAuth redirect
- `GET /auth/github` — GitHub OAuth redirect
- `POST /auth/refresh` — refresh JWT
- `GET /auth/me` — current user profile

### Predictions
- `GET /races` — list race weekends (with filters for season, status)
- `GET /races/{id}` — race weekend detail including AI predictions
- `POST /races/{id}/predict` — submit/update user prediction (before deadline)
- `GET /races/{id}/my-prediction` — get user's prediction for a race
- `GET /races/{id}/results` — actual results and scoring

### Leaderboard
- `GET /leaderboard/season` — season standings
- `GET /leaderboard/race/{id}` — single race standings
- `GET /leaderboard/vs-ai` — user vs AI comparison

### AI Insights
- `GET /races/{id}/ai-predictions` — AI predictions with all stage history
- `GET /ai/accuracy` — AI model accuracy stats

### User
- `GET /users/{id}/history` — prediction history and stats
- `GET /users/{id}/stats` — aggregated accuracy metrics

## Error Handling

- API returns standard HTTP status codes with JSON error bodies
- Form validation on both frontend (immediate feedback) and backend (authoritative)
- Deadline enforcement server-side: prediction submissions rejected after quali_time
- Graceful degradation if external APIs (Jolyon, FastF1) are unavailable: show cached data, retry in background
- ML pipeline failures don't affect user-facing API: if retraining fails, the last successful prediction remains visible

## Testing Strategy

- **Backend unit tests**: Scoring logic, deadline enforcement, prediction validation
- **Backend integration tests**: API endpoints with test database, auth flows
- **ML pipeline tests**: Model training on sample data, prediction format validation
- **Frontend component tests**: Prediction form, leaderboard rendering, countdown timer
- **E2E tests**: Full prediction flow from login → submit → score → leaderboard update

## Sprint Weekend Handling

Sprint weekends have a modified schedule: FP1 → Sprint Qualifying → Sprint → FP2 (removed) → Qualifying → Race. The ML pipeline adapts:
- Sprint Qualifying replaces FP2 as a data source
- Sprint results feed into race predictions (grid position changes, car damage, reliability signals)
- Sprint Top 5 predictions lock before Sprint Qualifying
- Main Qualifying/Race predictions still lock before Qualifying

## Scheduler Trigger Strategy

The APScheduler does not run on a fixed cron. Instead it uses event-driven scheduling:
- After each session ends (based on race_time fields in RaceWeekend), a job triggers 30 minutes later to allow data to become available on Jolyon/FastF1
- If data fetch fails, retry with exponential backoff (30min, 1h, 2h) up to 3 retries
- Manual trigger endpoint `POST /admin/trigger-pipeline/{race_id}/{stage}` for admin override
