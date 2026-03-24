"""
Codebase agent powered by Claude.

Uses the Claude Agent SDK to read, edit, search files, and run shell commands.
"""

import sys
import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, SystemMessage


async def run_agent(prompt: str, cwd: str = ".") -> None:
    print(f"Running agent with prompt: {prompt!r}\n")

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            model="claude-opus-4-6",
            cwd=cwd,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            max_turns=50,
        ),
    ):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            session_id = message.data.get("session_id")
            print(f"Session: {session_id}\n")

        elif isinstance(message, ResultMessage):
            print("\n--- Result ---")
            print(message.result)
            print(f"\nStop reason: {message.stop_reason}")


def main() -> None:
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    if not prompt:
        print("Usage: python agent.py <prompt>")
        print('Example: python agent.py "Explain what this codebase does"')
        sys.exit(1)

    anyio.run(run_agent, prompt)


if __name__ == "__main__":
    main()
