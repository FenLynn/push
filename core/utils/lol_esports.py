"""Small client for the public LoL Esports web schedule used by lolesports.com."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import requests


LOL_ESPORTS_ENDPOINT = "https://lolesports.com/api/gql"
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
    return {
        "id": str(team.get("id") or "").strip(),
        "name": str(team.get("name") or code).strip(),
        "code": code,
        "image": _https_url(team.get("image") or team.get("lightImage")),
        "score": int(result.get("gameWins") or 0),
        "outcome": str(result.get("outcome") or "").strip(),
    }


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
    return sorted(matches, key=lambda item: item.get("startTime") or "")
