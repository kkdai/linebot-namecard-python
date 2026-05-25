import os
import asyncio
from google.adk import Agent, Runner
from google.adk.sessions.in_memory_session_service import (
    InMemorySessionService
)


async def main():
    print("Initializing ADK Environment Verification...")

    # Check required environments
    project_id = os.getenv("PROJECT_ID", "line-vertex")
    location = os.getenv("LOCATION", "global")

    print(f"Project ID: {project_id}")
    print(f"Location: {location}")

    # 1. Initialize ADK Agent
    try:
        agent = Agent(
            name="verification_agent",
            model="gemini-3-flash-preview",
            instruction=(
                "You are a verification assistant. "
                "Respond with a concise greeting."
            ),
        )
        print("ADK Agent created successfully.")
    except Exception as e:
        print(f"Error creating Agent: {e}")
        return

    # 2. Initialize ADK Runner
    try:
        runner = Runner(
            app_name="env_verification_app",
            agent=agent,
            session_service=InMemorySessionService(),
        )
        print("ADK Runner created successfully.")
    except Exception as e:
        print(f"Error creating Runner: {e}")
        return

    # 3. Execute basic turn
    try:
        print("Sending message to agent...")
        events = await runner.run_debug("Verification message: Hello!")

        final_text = ""
        for event in events:
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text

        print("\n--- Agent Response ---")
        print(final_text)
        print("----------------------\n")
        print("ADK Environment Verification Successful!")
    except Exception as e:
        print(f"Error executing Runner: {e}")


if __name__ == "__main__":
    asyncio.run(main())
