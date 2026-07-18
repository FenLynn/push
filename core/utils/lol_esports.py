"""Small client for the public LoL Esports web schedule used by lolesports.com."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, Iterable, List, Optional

import requests


LOL_ESPORTS_ENDPOINT = "https://lolesports.com/api/gql"
LOL_LIVE_WINDOW_ENDPOINT = "https://feed.lolesports.com/livestats/v1/window"
HOME_EVENTS_QUERY_ID = "7246add6f577cf30b304e651bf9e25fc6a41fe49aeafb0754c16b5778060fc0a"
WATCHED_TEAM_CODES = ("T1", "HLE", "GEN", "BLG")
BEIJING_TZ = timezone(timedelta(hours=8))


def _https_url(value: Any) -> str:
    text = str(value or "").strip()
    return "https://" + text[7:] if text.lower().startswith("http://") else text


def _parse_time(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalize_team(team: Dict[str, Any]) -> Dict[str, Any]:
    result = team.get("result") if isinstance(team.get("result"), dict) else {}
    code = str(team.get("code") or "").strip().upper()
    raw_id = str(team.get("id") or "").strip()
    team_name = re.sub(r'\bEsports\b', '', str(team.get("name") or code), flags=re.IGNORECASE)
    team_name = re.sub(r'\s{2,}', ' ', team_name).strip()
    return {
        "id": raw_id,
        "provider_id": raw_id.rsplit(":", 1)[-1],
        "name": team_name or code,
        "code": code,
        "image": _https_url(team.get("image") or team.get("lightImage")),
        "score": int(result.get("gameWins") or 0),
        "outcome": str(result.get("outcome") or "").strip(),
    }


def _resolve_completed_game_winner(
    game: Dict[str, Any],
    teams: List[Dict[str, Any]],
    now: datetime,
    match_start: Any = None,
    session: Any = requests,
) -> str:
    """Resolve a completed game's winner from the official live-data final frame."""
    game_id = str(game.get("id") or "").strip()
    if not game_id or str(game.get("state") or "").strip().lower() != "completed":
        return ""

    query_time = now.astimezone(timezone.utc)
    parsed_match_start = _parse_time(match_start)
    if parsed_match_start:
        game_number = max(1, int(game.get("number") or 1))
        latest_useful_time = parsed_match_start + timedelta(minutes=game_number * 90)
        query_time = min(query_time, latest_useful_time)
    query_time = query_time.replace(second=0, microsecond=0)
    payload: Dict[str, Any] = {}
    for offset_minutes in (0, 10, 30):
        starting_time = (query_time - timedelta(minutes=offset_minutes)).isoformat(timespec="seconds").replace("+00:00", "Z")
        try:
            response = session.get(
                f"{LOL_LIVE_WINDOW_ENDPOINT}/{game_id}",
                params={"startingTime": starting_time},
                headers={
                    "Origin": "https://lolesports.com",
                    "Referer": "https://lolesports.com/",
                    "User-Agent": "Push-Game-Snapshot/1.0",
                },
                timeout=10,
            )
            response.raise_for_status()
            candidate = response.json()
            if isinstance(candidate, dict) and candidate.get("frames"):
                payload = candidate
                break
        except Exception:
            continue

    frames = payload.get("frames") if isinstance(payload, dict) else []
    if not isinstance(frames, list) or not frames:
        return ""
    final_frame = frames[-1] if isinstance(frames[-1], dict) else None
    if not final_frame:
        return ""

    blue_towers = int((final_frame.get("blueTeam") or {}).get("towers") or 0)
    red_towers = int((final_frame.get("redTeam") or {}).get("towers") or 0)
    if blue_towers == 11 and red_towers != 11:
        side = "blueTeamMetadata"
    elif red_towers == 11 and blue_towers != 11:
        side = "redTeamMetadata"
    else:
        return ""

    metadata = payload.get("gameMetadata") if isinstance(payload.get("gameMetadata"), dict) else {}
    winner_id = str((metadata.get(side) or {}).get("esportsTeamId") or "").strip()
    winner = next((team for team in teams if team.get("provider_id") == winner_id), None)
    return str((winner or {}).get("code") or "").strip().upper()


def enrich_live_game_winners(match: Dict[str, Any], now: datetime, session: Any = requests) -> Dict[str, Any]:
    if not match.get("live"):
        return match
    teams = [
        {"provider_id": match.get("teamAProviderId"), "code": match.get("teamACode")},
        {"provider_id": match.get("teamBProviderId"), "code": match.get("teamBCode")},
    ]
    for game in match.get("games") if isinstance(match.get("games"), list) else []:
        if not game.get("winner"):
            game["winner"] = _resolve_completed_game_winner(
                game,
                teams,
                now,
                match_start=match.get("startedAt") or match.get("startTime") or match.get("scheduledAt"),
                session=session,
            )
    completed_games = [game for game in match.get("games", []) if game.get("state") == "completed"]
    unresolved_games = [game for game in completed_games if not game.get("winner")]
    team_a_code = str(match.get("teamACode") or "").strip().upper()
    team_b_code = str(match.get("teamBCode") or "").strip().upper()
    team_a_wins = int(match.get("scoreA") or 0)
    team_b_wins = int(match.get("scoreB") or 0)
    known_a_wins = sum(1 for game in completed_games if game.get("winner") == team_a_code)
    known_b_wins = sum(1 for game in completed_games if game.get("winner") == team_b_code)
    remaining_a_wins = team_a_wins - known_a_wins
    remaining_b_wins = team_b_wins - known_b_wins
    if unresolved_games and remaining_a_wins >= 0 and remaining_b_wins >= 0 \
            and remaining_a_wins + remaining_b_wins == len(unresolved_games):
        if remaining_a_wins == len(unresolved_games):
            for game in unresolved_games:
                game["winner"] = team_a_code
        elif remaining_b_wins == len(unresolved_games):
            for game in unresolved_games:
                game["winner"] = team_b_code
        elif len(unresolved_games) == 1:
            unresolved_games[0]["winner"] = team_a_code if remaining_a_wins == 1 else team_b_code
    return match


def normalize_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if event.get("__typename") != "EventMatch":
        return None
    raw_teams = event.get("matchTeams")
    if not isinstance(raw_teams, list) or len(raw_teams) != 2:
        return None
    teams = [_normalize_team(team if isinstance(team, dict) else {}) for team in raw_teams]
    if not any(team["code"] in WATCHED_TEAM_CODES for team in teams):
        return None

    match = event.get("match") if isinstance(event.get("match"), dict) else {}
    strategy = match.get("strategy") if isinstance(match.get("strategy"), dict) else {}
    start = _parse_time(event.get("startTime"))
    local_start = start.astimezone(BEIJING_TZ) if start else None
    state = str(event.get("state") or match.get("state") or "").strip()
    games = []
    for raw_game in match.get("games") if isinstance(match.get("games"), list) else []:
        if not isinstance(raw_game, dict) or raw_game.get("state") == "unneeded":
            continue
        games.append({
            "id": str(raw_game.get("id") or "").strip(),
            "number": int(raw_game.get("number") or 0),
            "state": str(raw_game.get("state") or "").strip(),
        })
    active = next((game for game in games if game["state"].lower() == "inprogress"), None)
    completed = sum(1 for game in games if game["state"] == "completed")
    best_of = int(strategy.get("count") or 0)
    current_game = active["number"] if active else (0 if state == "completed" else min(completed + 1, best_of or completed + 1))
    league = event.get("league") if isinstance(event.get("league"), dict) else {}
    tournament = event.get("tournament") if isinstance(event.get("tournament"), dict) else {}
    match_id = str(match.get("id") or event.get("id") or "").strip()

    return {
        "provider": "lol-esports",
        "providerId": match_id,
        "id": match_id,
        "date": local_start.strftime("%Y-%m-%d") if local_start else "",
        "time": local_start.strftime("%H:%M") if local_start else "",
        "startTime": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if start else "",
        "scheduledAt": start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if start else "",
        "league": str(league.get("name") or "").strip(),
        "leagueSlug": str(league.get("slug") or "").strip(),
        "leagueLogo": _https_url(league.get("image")),
        "stage": str(event.get("blockName") or tournament.get("name") or "").strip(),
        "status": state,
        "live": state.lower() == "inprogress",
        "watched": True,
        "highlight": True,
        "bestOf": best_of,
        "currentGame": current_game,
        "scoreA": teams[0]["score"],
        "scoreB": teams[1]["score"],
        "scoreText": f'{teams[0]["score"]}:{teams[1]["score"]}',
        "teamA": teams[0]["name"],
        "teamB": teams[1]["name"],
        "teamACode": teams[0]["code"],
        "teamBCode": teams[1]["code"],
        "teamAProviderId": teams[0]["provider_id"],
        "teamBProviderId": teams[1]["provider_id"],
        "teamALogo": teams[0]["image"],
        "teamBLogo": teams[1]["image"],
        "games": games,
        "streamUrl": f'https://lolesports.com/en-US?leagues={league.get("slug")}' if league.get("slug") else "https://lolesports.com/en-US",
    }


def fetch_watched_matches(
    now: Optional[datetime] = None,
    days_before: int = 1,
    days_after: int = 14,
    session: Any = requests,
) -> List[Dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    body = {
        "operationName": "homeEvents",
        "variables": {
            "hl": "en-US",
            "sport": ["lol"],
            "eventDateStart": (now - timedelta(days=days_before)).strftime("%Y-%m-%d"),
            "eventDateEnd": (now + timedelta(days=days_after)).strftime("%Y-%m-%d"),
            "eventState": ["inProgress", "unstarted", "completed"],
            "pageSize": 200,
        },
        "extensions": {
            "persistedQuery": {"version": 1, "sha256Hash": HOME_EVENTS_QUERY_ID},
        },
    }
    response = session.post(
        LOL_ESPORTS_ENDPOINT,
        json=body,
        headers={
            "Content-Type": "application/json",
            "apollographql-client-name": "Esports Web",
            "apollographql-client-version": "1.0.0",
            "Origin": "https://lolesports.com",
            "Referer": "https://lolesports.com/",
            "User-Agent": "Push-Game-Snapshot/1.0",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(str(payload["errors"][0].get("message") or "LoL Esports query failed"))
    events: Iterable[Dict[str, Any]] = (((payload.get("data") or {}).get("esports") or {}).get("events") or [])
    matches = [normalized for normalized in (normalize_event(event) for event in events) if normalized]
    matches = [enrich_live_game_winners(match, now, session=session) for match in matches]
    return sorted(matches, key=lambda item: item.get("startTime") or "")
