# This file originally contained the main LINE Bot application logic using FastAPI.
# The application has been refactored to use the Google Agent Development Kit (ADK).
#
# The new components are:
# - Webhook handling (FastAPI): adk_webhook_main.py
# - ADK Agent definition: namecard_agent.py
# - ADK Tools (Firebase, Gemini, LINE senders): namecard_tools.py
#
# To run the application, execute: uvicorn adk_webhook_main:app --host 0.0.0.0 --port 8080 --reload
# (or as per your deployment strategy, ensure the port matches what's expected, e.g., from PORT env var)
#
# This file can be removed or repurposed if no longer needed for other project tasks.

# Any remaining imports below this line are likely unused after refactoring.
# If this file is kept, these should be cleaned up.
# For example:
# from linebot.models import FlexSendMessage
# from linebot.models import MessageEvent, TextSendMessage
# ... and so on for all original imports.
# Since the file's purpose is now just a placeholder/explanatory note,
# these imports are no longer functionally necessary here.
# Consider removing them if this file is to be kept lean.
# If this file is deleted, this comment is moot.
