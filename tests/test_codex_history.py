import json
from pathlib import Path

from agent_handoff.codex_history import extract_codex_transcript, find_recent_codex_rollout


def _line(data: dict) -> str:
    return json.dumps(data) + "\n"


def test_finds_repo_rollout_and_extracts_dialogue(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / ".codex"
    sessions = home / "sessions" / "2026" / "08" / "21"
    sessions.mkdir(parents=True)
    rollout = sessions / "rollout-2026-08-21T12-00-00-00000000-0000-0000-0000-000000000001.jsonl"
    rollout.write_text(
        _line({"type": "session_meta", "payload": {"meta": {"cwd": str(repo)}}})
        + _line(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "fix the retry bug"}],
                },
            }
        )
        + _line(
            {
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "fix the retry bug"},
            }
        )
        + _line(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "I found the likely race."}],
                },
            }
        ),
        encoding="utf-8",
    )

    assert find_recent_codex_rollout(repo, codex_home=home) == rollout
    transcript = extract_codex_transcript(rollout)
    assert transcript.count("fix the retry bug") == 1
    assert "### assistant" in transcript
    assert "I found the likely race." in transcript
