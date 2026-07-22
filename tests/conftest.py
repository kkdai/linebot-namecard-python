import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

os.environ.setdefault("ChannelSecret", "test-channel-secret")
os.environ.setdefault("ChannelAccessToken", "test-channel-access-token")
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault(
    "FIREBASE_URL", "https://test-project.firebaseio.com/"
)
