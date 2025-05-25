import os
import json
from io import BytesIO
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.concurrency import run_in_threadpool # For running synchronous ADK engine

from linebot.v3.webhook import WebhookParser
from linebot.v3.messaging import (
    AsyncLineBotApi,
    Configuration,
    TextSendMessage, # Though agent tools will send most messages
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

# ADK and project imports
from google.adk.engine import Engine
from namecard_agent import namecard_agent # The ADK agent
# Import specific tools needed by the webhook handler directly
from namecard_tools import parse_namecard_from_image_tool, send_text_message_tool

# Load environment variables
load_dotenv()

# Configuration
CHANNEL_SECRET = os.getenv("ChannelSecret")
CHANNEL_ACCESS_TOKEN = os.getenv("ChannelAccessToken")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # For parse_namecard_from_image_tool
FIREBASE_URL = os.getenv("FIREBASE_URL") # For Firebase tools used by agent

if not CHANNEL_SECRET:
    raise ValueError("ChannelSecret not found in environment variables.")
if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("ChannelAccessToken not found in environment variables.")
if not GEMINI_API_KEY:
    # parse_namecard_from_image_tool requires this.
    print("Warning: GEMINI_API_KEY not found. Image processing will fail.")
if not FIREBASE_URL:
    # Firebase tools used by the agent require this.
    print("Warning: FIREBASE_URL not found. Agent's Firebase tools may fail.")


# Initialize LINE SDK
line_config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
line_bot_api = AsyncLineBotApi(configuration=line_config)
parser = WebhookParser(channel_secret=CHANNEL_SECRET)

# Initialize ADK Engine
adk_engine = Engine()

# Initialize FastAPI app
app = FastAPI()

@app.post("/webhook")
async def handle_callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    if signature is None:
        raise HTTPException(status_code=400, detail="X-Line-Signature header missing")
    
    body = await request.body()
    body_str = body.decode('utf-8')

    try:
        events = parser.parse(body_str, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel secret.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Error parsing webhook: {e}")
        raise HTTPException(status_code=400, detail=f"Error parsing webhook: {e}")

    for event in events:
        if isinstance(event, MessageEvent):
            user_id = event.source.user_id
            print(f"Processing event for user_id: {user_id}")

            if isinstance(event.message, TextMessageContent):
                user_text = event.message.text
                print(f"Received text message: {user_text}")
                
                # Invoke ADK Agent for text messages
                try:
                    print(f"Invoking ADK agent for user {user_id} with text: {user_text}")
                    # ADK engine.stream is synchronous, run in threadpool
                    # The agent's tools are responsible for sending replies.
                    # We consume the generator to ensure it runs.
                    # TODO: Confirm how user_id is best passed to tools via ADK.
                    # For now, passing user_id and session_id to stream method.
                    # The agent's instruction should guide it to use user_id with its tools.
                    
                    # ADK Engine methods are synchronous
                    def run_agent_stream():
                        responses = []
                        for response_part in adk_engine.stream(
                            namecard_agent,
                            query=user_text,
                            user_id=user_id, # Custom kwarg for context
                            session_id=user_id # ADK standard session tracking
                        ):
                            responses.append(response_part) # Collect responses if any are directly returned
                        return "".join(str(r) for r in responses)

                    await run_in_threadpool(run_agent_stream)
                    print(f"ADK Agent text processing complete for user {user_id}.")

                except Exception as e:
                    print(f"Error invoking ADK agent for text: {e}")
                    # Optionally send an error message back to the user
                    # Using the synchronous send_text_message_tool from namecard_tools
                    error_report_status = await run_in_threadpool(
                        send_text_message_tool,
                        user_id,
                        f"Sorry, an error occurred while processing your text: {str(e)[:100]}" # Truncate error
                    )
                    print(f"Error report status to user {user_id}: {error_report_status}")


            elif isinstance(event.message, ImageMessageContent):
                print(f"Received image message from user {user_id}")
                message_id = event.message.id
                
                # Get image bytes from LINE
                try:
                    # Note: linebot.v3.messaging.AsyncApiClient has no .get_message_content directly
                    # Need to use the line_bot_api (AsyncLineBotApi instance)
                    message_content = await line_bot_api.get_message_content(message_id=message_id)
                    image_bytes = b""
                    # The response object itself is the content if it's small, or a stream.
                    # For linebot v3, get_message_content returns the bytes directly if successful.
                    if hasattr(message_content, 'read'): # If it's a stream-like object
                         image_bytes = message_content.read()
                    elif isinstance(message_content, bytes): # If it's already bytes
                         image_bytes = message_content
                    else:
                        # Fallback for older/different line-bot-sdk versions or unexpected types
                        async for chunk in message_content.iter_content(): # iter_content might not exist
                           image_bytes += chunk
                    
                    if not image_bytes:
                        raise ValueError("Failed to retrieve image bytes.")
                    print(f"Image bytes retrieved successfully (length: {len(image_bytes)}).")

                except Exception as e:
                    print(f"Error getting image content from LINE: {e}")
                    await run_in_threadpool(
                        send_text_message_tool,
                        user_id,
                        "Sorry, I couldn't retrieve the image you sent. Please try again."
                    )
                    continue # Skip to next event

                # Directly call parse_namecard_from_image_tool (utility function)
                print("Calling parse_namecard_from_image_tool...")
                # This tool is synchronous, run in threadpool
                parsed_card_data = await run_in_threadpool(parse_namecard_from_image_tool, image_bytes)

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
                        print(f"Invoking ADK agent for user {user_id} with parsed image data.")
                        def run_agent_stream_image_data():
                            responses = []
                            for response_part in adk_engine.stream(
                                namecard_agent,
                                query=agent_query_for_image_data,
                                user_id=user_id, # Custom kwarg for context
                                session_id=user_id # ADK standard session tracking
                            ):
                                responses.append(response_part)
                            return "".join(str(r) for r in responses)

                        await run_in_threadpool(run_agent_stream_image_data)
                        print(f"ADK Agent image data processing complete for user {user_id}.")

                    except Exception as e:
                        print(f"Error invoking ADK agent with parsed image data: {e}")
                        await run_in_threadpool(
                            send_text_message_tool,
                            user_id,
                            f"Sorry, an error occurred while processing the extracted card data: {str(e)[:100]}"
                        )
                else:
                    error_detail = parsed_card_data.get("details", "Unknown error during parsing.") if parsed_card_data else "Parsing returned no data."
                    print(f"Failed to parse image: {error_detail}")
                    await run_in_threadpool(
                        send_text_message_tool,
                        user_id,
                        f"Sorry, I couldn't understand the content of the namecard image. Details: {error_detail[:100]}"
                    )
            else:
                print(f"Received unhandled message type: {event.message.type}")
        else:
            print(f"Received unhandled event type: {type(event)}")

    return "OK"

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    print(f"Starting Uvicorn server on host 0.0.0.0 port {port}")
    # Make sure to use the correct variable name for the app, which is `app`
    uvicorn.run("adk_webhook_main:app", host="0.0.0.0", port=port, reload=True) # reload=True for dev
