# LINE Bot Namecard Manager

This repository contains a LINE Bot application built using FastAPI, Firebase, and the Gemini Pro API. The bot can handle text and image messages, parse namecard information from images, and store/retrieve namecard data from Firebase.

## Features

- Parse namecard information from images using the Gemini Pro API.
- Store and retrieve namecard data from Firebase Realtime Database.
- Handle various text commands to list, add, and remove namecard data.

## Prerequisites

- Python 3.7+
- LINE Developer Account
- Firebase Account
- Gemini Pro API Key

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/linebot-namecard-manager.git
    cd linebot-namecard-manager
    ```

2. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

3. Set up environment variables:

    ```bash
    export ChannelSecret='YOUR_CHANNEL_SECRET'
    export ChannelAccessToken='YOUR_CHANNEL_ACCESS_TOKEN'
    export GEMINI_API_KEY='YOUR_GEMINI_API_KEY'
    export FIREBASE_URL='YOUR_FIREBASE_URL'
    ```

## Usage

1. Run the FastAPI application:

    ```bash
    uvicorn main:app --reload
    ```

2. Set up your LINE webhook URL to point to your FastAPI server.

3. Interact with the bot using the following commands:
    - `test`: Generate a sample namecard.
    - `list`: List all namecards in the database.
    - `remove`: Remove redundant namecard data.
    - Send an image of a namecard to parse and store its information.

## Code Overview

### Main Components

- **FastAPI**: The web framework used to handle incoming requests from LINE.
- **Firebase**: Used to store and retrieve namecard data.
- **Gemini Pro API**: Used to parse namecard information from images.

## Contributing

Feel free to submit issues or pull requests if you have any improvements or bug fixes.

## License

This project is licensed under the MIT License.
