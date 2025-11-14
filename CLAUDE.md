# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- **Run locally**: `uvicorn app.main:app --host=0.0.0.0 --port=8080`
- **Lint**: `flake8 .` (configured in GitHub Actions)
- **Install dependencies**: `pip install -r requirements.txt`

### Docker
- **Build image**: `docker build -t linebot-namecard .`
- **Run container**: `docker run -p 8080:8080 linebot-namecard`

### Google Cloud Platform Deployment
- **Build and push to GCP**: `gcloud builds submit --tag gcr.io/{PROJECT_ID}/{IMAGE_NAME}`
- **Deploy to Cloud Run**:
  ```bash
  gcloud run deploy {IMAGE_NAME} \
    --image gcr.io/{PROJECT_ID}/{IMAGE_NAME} \
    --platform managed \
    --region asia-east1 \
    --allow-unauthenticated \
    --set-env-vars "ChannelSecret=YOUR_CHANNEL_SECRET,ChannelAccessToken=YOUR_CHANNEL_ACCESS_TOKEN,GEMINI_API_KEY=YOUR_GEMINI_API_KEY,FIREBASE_URL=YOUR_FIREBASE_URL,FIREBASE_STORAGE_BUCKET=YOUR_PROJECT_ID.firebasestorage.app,GOOGLE_APPLICATION_CREDENTIALS_JSON=YOUR_FIREBASE_SERVICE_ACCOUNT_JSON"
  ```

## Architecture

This is a LINE Bot application that processes business card images using Google's Gemini Pro Vision API and stores extracted data in Firebase Realtime Database.

### Core Components

- **app/main.py**: FastAPI entry point with webhook handler for LINE Bot
- **app/line_handlers.py**: Handles different LINE message types (text, image, postback)
- **app/gemini_utils.py**: Gemini Pro API integration for image OCR and text processing
- **app/firebase_utils.py**: Firebase Realtime Database and Storage operations
- **app/qrcode_utils.py**: vCard QR Code generation utilities
- **app/flex_messages.py**: LINE Flex Message templates for rich card displays
- **app/bot_instance.py**: LINE Bot API client and session management
- **app/config.py**: Environment configuration and validation

### Data Flow

1. **Image Processing**: Images → Gemini Pro Vision → JSON extraction
2. **Data Storage**: Structured namecard data → Firebase Realtime Database under `namecard/{user_id}/`
3. **Smart Query**: Text queries → Gemini Pro text model → relevant namecard search
4. **Interactive Editing**: Postback events → field editing states → database updates
5. **QR Code Generation**: Namecard data → vCard format → QR Code image → Firebase Storage → LINE ImageMessage

### Key Features

- **Business Card OCR**: Extracts name, title, company, address, phone, email from images
- **Duplicate Detection**: Checks existing cards by email before adding new ones
- **Interactive Editing**: Users can edit individual fields through LINE interface
- **Smart Search**: Natural language queries to find relevant business cards
- **Memo System**: Add notes to business cards
- **vCard QR Code Export**: Generate QR Code for direct import to phone contacts (iPhone/Android)
- **State Management**: Tracks user interaction states for multi-step operations

### Environment Variables

Required for deployment:
- `ChannelSecret`: LINE Channel secret
- `ChannelAccessToken`: LINE Channel access token
- `GEMINI_API_KEY`: Google Gemini API key
- `FIREBASE_URL`: Firebase Realtime Database URL
- `FIREBASE_STORAGE_BUCKET`: Firebase Storage bucket name (e.g., `project-id.firebasestorage.app`)
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`: Firebase service account JSON (as string)

### Database Structure

**Firebase Realtime Database** stores namecard data:
```
namecard/
  {user_id}/
    {card_id}/
      name: string
      title: string
      company: string
      address: string
      phone: string
      email: string
      memo?: string
```

**Firebase Storage** stores QR Code images:
```
qrcodes/
  {user_id}/
    {card_id}.png
```

### QR Code Implementation

**vCard Format** (app/qrcode_utils.py):
- Generates vCard 3.0 format string from namecard data
- Handles special character escaping (newlines, commas, semicolons)
- Includes all fields: name, title, company, phone, email, address, memo

**QR Code Generation**:
- Uses `qrcode` Python library
- Parameters: `version=None` (auto), `error_correction=L`, `box_size=10`, `border=2`
- Returns BytesIO object containing PNG image

**Firebase Storage Upload** (app/firebase_utils.py):
- Uploads QR Code to `qrcodes/{user_id}/{card_id}.png`
- Sets image as publicly readable via `blob.make_public()`
- Returns public URL for LINE ImageMessage

**Storage Rules**:
```javascript
allow read: if true;   // Public read for QR Code images
allow write: if false; // Only Admin SDK can write
```

### Testing Commands

- `test`: Generates sample namecard for UI testing
- `list`: Shows total number of stored namecards
- `remove`: Removes duplicate entries by email