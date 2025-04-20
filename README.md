# Supabase Agent

A powerful agent that combines Supabase with AI capabilities for handling SQL queries, receipt processing, and audio transcription.

## Features

- 🤖 Natural Language to SQL conversion using Groq LLM
- 📷 Receipt image processing and total amount extraction using Google's Gemini Vision
- 🎙️ Audio transcription using Whisper
- 🗄️ Seamless integration with Supabase database
- 📊 Beautiful table formatting for query results
- 💬 Interactive command-line interface

## Prerequisites

- Python 3.x
- Supabase account and project
- API keys for:
  - Supabase
  - Google Gemini
  - Groq

## Environment Variables

The following environment variables need to be set:

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```

## Installation

1. Clone the repository
2. Install the required dependencies:
```bash
pip install supabase google-generativeai pillow requests tabulate
```

## Usage

Run the main script:
```bash
python main.py
```

The agent provides an interactive CLI where you can:
1. Enter natural language queries that get converted to SQL
2. Process receipt images to extract totals
3. Transcribe audio files
4. View results in a nicely formatted table

### Example Commands

```
💬 Enter your request: Show all refund requests
💬 Enter your request: Get the total amount from receipt with ID 123
💬 Enter your request: Transcribe the audio from the latest meeting
```

## Components

- `main.py`: Core agent logic and CLI interface
- `gemini_vision.py`: Receipt processing using Gemini Vision API
- `audio_transcriber.py`: Audio transcription functionality
- `supabase_helper.py`: Supabase query execution utilities
- `groq_agent.py`: Natural language to SQL conversion

## Database Schema

The application works with a Supabase database that includes tables for:
- `refund_requests` (with columns for image_url and amount)
- Support for audio transcription (with audio_url column)

## Error Handling

The agent includes comprehensive error handling for:
- Invalid SQL queries
- Image processing failures
- Audio transcription issues
- Database connection problems

## Contributing

Feel free to submit issues and enhancement requests!

## License

[MIT License](LICENSE)
