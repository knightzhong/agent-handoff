from agent_handoff.backends.command import CommandBackend


def test_command_backend_stdin_roundtrip() -> None:
    backend = CommandBackend("python -c 'import sys; print(sys.stdin.read().upper())'")
    response = backend.ask("hello")
    assert response.text == "HELLO"
