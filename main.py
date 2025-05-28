import json
import sys
import os
import aiohttp
from dotenv import load_dotenv

# Import necessary libraries
from fastapi import Request, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool  # For running synchronous ADK engine


from linebot.models import MessageEvent, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from linebot.aiohttp_async_http_client import AiohttpAsyncHttpClient
from linebot import AsyncLineBotApi, WebhookParser

# ADK and GenAI imports
from google.adk.runners import Runner
from google.genai import types
from google.adk.sessions import InMemorySessionService  # Add this import

from tools_agents.namecard_agent import namecard_agent  # The ADK agent

# Import specific tools needed by the webhook handler directly
from tools_agents.namecard_tools import (
    parse_namecard_from_image_tool,
    send_text_message_tool,
)

# Load environment variables
load_dotenv()

# Configuration
channel_secret = os.getenv("ChannelSecret")
channel_access_token = os.getenv("ChannelAccessToken")

# Firebase and Google GenAI configuration
FIREBASE_URL = os.getenv("FIREBASE_URL")  # For Firebase tools used by agent
USE_VERTEX = os.getenv("GOOGLE_GENAI_USE_VERTEXAI") or "False"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or ""

# Validate environment variables
if channel_secret is None:
    print("Specify ChannelSecret as environment variable.")
    sys.exit(1)
if channel_access_token is None:
    print("Specify ChannelAccessToken as environment variable.")
    sys.exit(1)
if USE_VERTEX == "True":  # Check if USE_VERTEX is true as a string
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
    if not GOOGLE_CLOUD_PROJECT:
        raise ValueError(
            "Please set GOOGLE_CLOUD_PROJECT via env var or code when USE_VERTEX is true."
        )
    if not GOOGLE_CLOUD_LOCATION:
        raise ValueError(
            "Please set GOOGLE_CLOUD_LOCATION via env var or code when USE_VERTEX is true."
        )
elif not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY via env var or code.")


# Initialize InMemorySessionService
session_service = InMemorySessionService()
active_sessions = {}  # Cache for active session IDs per user

# Initialize the FastAPI app for LINEBot
app = FastAPI()
client_session = aiohttp.ClientSession()
async_http_client = AiohttpAsyncHttpClient(client_session)
line_bot_api = AsyncLineBotApi(channel_access_token, async_http_client)
parser = WebhookParser(channel_secret)

APP_NAME = "linebot_adk_app"

# Key Concept: Runner orchestrates the agent execution loop.
runner = Runner(
    agent=namecard_agent,  # The agent we want to run
    app_name=APP_NAME,  # Associates runs with our app
    session_service=session_service,  # Uses our session manager
)
print(f"Runner created for agent '{runner.agent.name}'.")


async def get_or_create_session(user_id):
    if user_id not in active_sessions:
        # Create a new session for this user
        session_id = f"session_{user_id}"
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
        active_sessions[user_id] = session_id
        print(
            f"New session created: App='{APP_NAME}', User='{user_id}', Session='{session.id}'"
        )
    else:
        # Use existing session
        session_id = active_sessions[user_id]
        print(
            f"Using existing session: App='{APP_NAME}', User='{user_id}', Session='{session_id}'"
        )

    return session_id


@app.post("/")
async def handle_callback(request: Request):
    signature = request.headers["X-Line-Signature"]

    # get request body as text
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue

        if event.message.type == "text":
            # Process text message
            msg = event.message.text
            user_id = event.source.user_id
            print(f"Received message: {msg} from user: {user_id}")

            # Use the user's prompt directly with the agent
            response = await call_agent_async(msg, user_id)
            reply_msg = TextSendMessage(text=response)
            await line_bot_api.reply_message(event.reply_token, reply_msg)
        elif event.message.type == "image":
            print(f"Received image message from user {user_id}")
            message_id = event.message.id

            # Get image bytes from LINE
            try:
                # Note: linebot.v3.messaging.AsyncApiClient has no .get_message_content directly
                # Need to use the line_bot_api (AsyncLineBotApi instance)
                message_content = await line_bot_api.get_message_content(
                    message_id=message_id
                )
                image_bytes = b""
                # The response object itself is the content if it's small, or a stream.
                # For linebot v3, get_message_content returns the bytes directly if successful.
                if hasattr(message_content, "read"):  # If it's a stream-like object
                    image_bytes = message_content.read()
                elif isinstance(message_content, bytes):  # If it's already bytes
                    image_bytes = message_content
                else:
                    # Fallback for older/different line-bot-sdk versions or unexpected types
                    async for (
                        chunk
                    ) in message_content.iter_content():  # iter_content might not exist
                        image_bytes += chunk

                if not image_bytes:
                    raise ValueError("Failed to retrieve image bytes.")
                print(
                    f"Image bytes retrieved successfully (length: {len(image_bytes)})."
                )

            except Exception as e:
                print(f"Error getting image content from LINE: {e}")
                await run_in_threadpool(
                    send_text_message_tool,
                    user_id,
                    "Sorry, I couldn't retrieve the image you sent. Please try again.",
                )
                continue  # Skip to next event

            # Directly call parse_namecard_from_image_tool (utility function)
            print("Calling parse_namecard_from_image_tool...")
            # This tool is synchronous, run in threadpool
            parsed_card_data = await run_in_threadpool(
                parse_namecard_from_image_tool, image_bytes
            )

            if parsed_card_data and not parsed_card_data.get("error"):
                print(f"Image parsed successfully: {parsed_card_data}")
                # Construct a new prompt for the agent with the parsed data
                agent_query_for_image_data = (
                    f"A namecard image was processed. Here is the extracted data: "
                    f"{json.dumps(parsed_card_data)}. "
                    f"Please add this namecard information for user {user_id} "
                    f"and confirm with the user."
                )

                try:
                    print(
                        f"Invoking ADK agent for user {user_id} with parsed image data."
                    )

                    async def run_agent_stream_image_data():
                        # Use agent_query_for_image_data instead of msg
                        return await call_agent_async(
                            agent_query_for_image_data, user_id
                        )

                    response = await run_in_threadpool(run_agent_stream_image_data)
                    print(
                        f"ADK Agent image data processing complete for user {user_id}."
                    )

                except Exception as e:
                    print(f"Error invoking ADK agent with parsed image data: {e}")
                    await run_in_threadpool(
                        send_text_message_tool,
                        user_id,
                        f"Sorry, an error occurred while processing the extracted card data: {str(e)[:100]}",
                    )
            else:
                error_detail = (
                    parsed_card_data.get("details", "Unknown error during parsing.")
                    if parsed_card_data
                    else "Parsing returned no data."
                )
                print(f"Failed to parse image: {error_detail}")
                await run_in_threadpool(
                    send_text_message_tool,
                    user_id,
                    f"Sorry, I couldn't understand the content of the namecard image. Details: {error_detail[:100]}",
                )
        else:
            print(f"Received unhandled event type: {type(event)}")

    return "OK"


async def call_agent_async(query: str, user_id: str) -> str:
    """Sends a query to the agent and prints the final response."""
    print(f"\n>>> User Query: {query}")

    # Get or create a session for this user
    session_id = await get_or_create_session(user_id)

    # Prepare the user's message in ADK format
    content = types.Content(role="user", parts=[types.Part(text=query)])

    final_response_text = "Agent did not produce a final response."  # Default

    try:
        # Key Concept: run_async executes the agent logic and yields Events.
        # We iterate through events to find the final answer.
        async for event in runner.run_async(
            user_id=user_id, session_id=session_id, new_message=content
        ):
            # You can uncomment the line below to see *all* events during execution
            # print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")

            # Key Concept: is_final_response() marks the concluding message for the turn.
            if event.is_final_response():
                if event.content and event.content.parts:
                    # Assuming text response in the first part
                    final_response_text = event.content.parts[0].text
                elif (
                    event.actions and event.actions.escalate
                ):  # Handle potential errors/escalations
                    final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                # Add more checks here if needed (e.g., specific error codes)
                break  # Stop processing events once the final response is found
    except ValueError as e:
        if "Session not found" in str(e):
            print(
                f"Initial 'Session not found' error: {str(e)}. Attempting to recreate session and retry."
            )
            active_sessions.pop(user_id, None)
            new_session_id = await get_or_create_session(
                user_id
            )  # Renamed to avoid confusion
            print(f"Retrying with new session: {new_session_id}")
            try:
                # Initialize final_response_text for the retry attempt
                retry_final_response_text = (
                    "Agent did not produce a final response on retry."
                )
                async for event in runner.run_async(
                    user_id=user_id, session_id=new_session_id, new_message=content
                ):
                    if event.is_final_response():
                        if event.content and event.content.parts:
                            retry_final_response_text = event.content.parts[0].text
                        elif event.actions and event.actions.escalate:
                            retry_final_response_text = f"Agent escalated on retry: {event.error_message or 'No specific message.'}"
                        break
                final_response_text = (
                    retry_final_response_text  # Assign retry result here
                )
            except Exception as e2:
                print(f"Error during retry attempt: {str(e2)}")
                final_response_text = (
                    f"Sorry, I encountered an error after a session issue: {str(e2)}"
                )
        else:
            # This is for ValueErrors not related to "Session not found"
            print(
                f"Error processing request (non-session related ValueError): {str(e)}"
            )
            final_response_text = f"Sorry, I encountered an error: {str(e)}"
    except Exception as ex:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred: {str(ex)}")
        final_response_text = f"Sorry, an unexpected error occurred: {str(ex)}"

    print(f"<<< Agent Response: {final_response_text}")
    return final_response_text
