# agent-handoff

**Keep the work when the model changes.**

`agent-handoff` packages the state of a coding task — goal, git status/diff, project instructions,
selected files, and recent failures — into a portable bundle that can be handed to another LLM
backend and later resumed locally.

It is deliberately a **context continuity layer**, not a quota-bypass tool. Backends are explicit,
user-configured transports. The browser adapter delegates to an external bridge command rather than
scraping or authenticating to a web service itself.
