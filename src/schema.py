"""Build a prompt-ready description of the database schema for the LLM.

Table structure (names, types, keys) is read live from the database with
SQLAlchemy. Human-written notes in TABLE_NOTES / COLUMN_NOTES / GENERAL_NOTES
add the meaning and quirks the LLM cannot infer from names alone.

Try it from the project root:
    python -m src.schema
"""
from pathlib import Path

from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "ipl.db"

TABLE_NOTES = {
    "matches": "One row per IPL match (seasons 2008-2017).",
    "deliveries": "One row per ball bowled. Join to matches with deliveries.match_id = matches.id.",
}

COLUMN_NOTES = {
    "matches": {
        "id": "Primary key of the match.",
        "season": "Year of the IPL season, e.g. 2016.",
        "city": "City of the match. NULL for a few matches.",
        "date": "Match date as text, YYYY-MM-DD.",
        "team1": "First team listed.",
        "team2": "Second team listed.",
        "toss_winner": "Team that won the toss.",
        "toss_decision": "'bat' or 'field': what the toss winner chose.",
        "result": "'normal', 'tie' or 'no result'.",
        "dl_applied": "1 if Duckworth-Lewis was applied, else 0.",
        "winner": "Winning team. NULL when result is 'no result'.",
        "win_by_runs": "Margin in runs when the team batting first won, else 0.",
        "win_by_wickets": "Margin in wickets when the chasing team won, else 0.",
        "player_of_match": "Player of the match award winner.",
        "venue": "Stadium name.",
        "umpire1": "On-field umpire.",
        "umpire2": "On-field umpire.",
        "umpire3": "Always NULL; ignore.",
    },
    "deliveries": {
        "match_id": "Foreign key to matches.id.",
        "inning": "1 or 2 for regular innings; 3 or 4 only for super overs.",
        "batting_team": "Team batting on this ball.",
        "bowling_team": "Team bowling on this ball.",
        "over": "Over number, 1 to 20.",
        "ball": "Ball number within the over (can exceed 6 when wides/no-balls were bowled).",
        "batsman": "Batsman facing the ball.",
        "non_striker": "Batsman at the other end.",
        "bowler": "Bowler of the ball.",
        "is_super_over": "1 if the ball was bowled in a super over, else 0.",
        "wide_runs": "Runs from a wide.",
        "bye_runs": "Runs from byes.",
        "legbye_runs": "Runs from leg byes.",
        "noball_runs": "Runs from a no-ball.",
        "penalty_runs": "Penalty runs awarded.",
        "batsman_runs": "Runs scored off the bat (credited to the batsman).",
        "extra_runs": "Total extras on the ball.",
        "total_runs": "batsman_runs + extra_runs. Use this for team totals.",
        "player_dismissed": "Name of the player dismissed on this ball. NULL if no wicket.",
        "dismissal_kind": (
            "How the wicket fell: bowled, caught, caught and bowled, lbw, run out, "
            "stumped, hit wicket, retired hurt, obstructing the field. NULL if no wicket."
        ),
        "fielder": "Fielder involved in the dismissal (catch, run out, stumping). May be NULL.",
    },
}

GENERAL_NOTES = [
    "Database is SQLite; use SQLite SQL syntax.",
    "Super-over balls are in deliveries with is_super_over = 1. Exclude them "
    "(is_super_over = 0) for normal batting/bowling statistics unless asked.",
    "A bowler is credited with a wicket only for dismissal_kind other than "
    "'run out', 'retired hurt' and 'obstructing the field'.",
    "Team names are exact strings. 'Rising Pune Supergiant' and "
    "'Rising Pune Supergiants' both exist and refer to the same franchise.",
    "Tied matches (result = 'tie') still have a winner, decided by super over, "
    "with win_by_runs = 0 and win_by_wickets = 0.",
    "Player names are abbreviated, e.g. 'V Kohli', 'MS Dhoni', 'DA Warner'.",
]


def get_schema_description(db_path: Path = DB_PATH) -> str:
    """Return the schema, notes and rules as a single string for the LLM prompt."""
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)

    lines: list[str] = []
    for table in inspector.get_table_names():
        lines.append(f"Table: {table}")
        if table in TABLE_NOTES:
            lines.append(f"  {TABLE_NOTES[table]}")
        lines.append("  Columns:")
        notes = COLUMN_NOTES.get(table, {})
        for col in inspector.get_columns(table):
            note = notes.get(col["name"])
            suffix = f" - {note}" if note else ""
            lines.append(f"    {col['name']} ({col['type']}){suffix}")
        lines.append("")

    lines.append("Notes:")
    lines.extend(f"  - {note}" for note in GENERAL_NOTES)
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_schema_description())
