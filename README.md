# YouTube Transcript to PDF Converter

A lightweight Python application built with a Graphical User Interface (GUI) to automatically extract native transcripts from single YouTube videos or entire public playlists and compile them neatly into structured PDF files.

## Features
- **GUI Controls:** Input fields with built-in native right-click support (`Copy`, `Paste`, `Cut`).
- **Asynchronous Execution:** Built with native multi-threading (`threading`) to keep the interface smooth during long batch operations.
- **Playlist Sorting:** Detects playlist URLs natively and groups processed video scripts cleanly into independent folders.
- **Optional Timestamps:** Checkbox flag to toggle embedded chronological indicators (`[MM:SS]`) line by line.
- **Native-First Captions:** Automatically identifies and parses the video creator's native language data.

## Installation & Setup
Ensure you have Python installed, then run the following command to download the dependencies:
```bash
pip install youtube-transcript-api reportlab
