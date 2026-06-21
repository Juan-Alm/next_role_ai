# ============================================================
#  main_chat.py — Phase D entry point
#
#  A terminal chat loop where you talk to the agent directly.
#  Try things like:
#    "Find me data analyst jobs in Christchurch"
#    "Any data scientist roles in Auckland from the last day?"
#
#  Commands:
#    clear  — start a fresh conversation (job memory is unaffected)
#    stats  — show how many jobs the agent has seen in total
#    exit   — quit
# ============================================================

from app.ollama_client import is_ollama_running
from app.agent import agent_loop
from app.memory import seen_count

# Conversation history beyond this many messages gets trimmed —
# keeps requests fast and avoids ever-growing context sent to Qwen3.
MAX_HISTORY_MESSAGES = 20


def trim_history(history: list[dict]) -> list[dict]:
    """
    Keeps the conversation from growing forever. If it gets too long,
    drop the oldest messages but always keep the most recent ones —
    that's what's actually relevant to follow-up questions.
    """
    if len(history) <= MAX_HISTORY_MESSAGES:
        return history
    return history[-MAX_HISTORY_MESSAGES:]


def print_stats():
    total = seen_count()
    print(f"\n📊 Total jobs seen across all sessions: {total}\n")


def main():
    print("\n🤖 SEEK Job Agent — Phase D (chat mode)")
    print("Commands: 'clear' to reset conversation, 'stats' for job memory, 'exit' to quit.\n")

    if not is_ollama_running():
        print("❌ Ollama is not running. Start it with: ollama serve")
        return

    history = []

    while True:
        user_input = input("You: ").strip()
        command = user_input.lower()

        if command in ("exit", "quit"):
            print("Goodbye!")
            break

        if command == "clear":
            history = []
            print("\n🧹 Conversation cleared. Job memory is untouched.\n")
            continue

        if command == "stats":
            print_stats()
            continue

        if not user_input:
            continue

        reply, history = agent_loop(user_input, history)
        history = trim_history(history)
        print(f"\nAgent: {reply}\n")


if __name__ == "__main__":
    main()