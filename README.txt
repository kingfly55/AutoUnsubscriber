# Auto Unsubscriber

A Python utility that scans your email for newsletters and spam, finds unsubscribe links, and helps you bulk-unsubscribe and delete old emails.



## Features

* **Universal IMAP Support:** Auto-detects major providers (Gmail, Yahoo, Outlook, Zoho, etc.) and supports **manual entry** for custom domains or private servers.
* **Smart Parsing:** Scans email bodies for unsubscribe links using `BeautifulSoup`.
* **Safety First:**
    * Runs in "Read Only" mode during the scanning phase.
    * Requires explicit `DELETE` confirmation before removing any data.
    * Opens links in small batches to prevent browser crashes.
* **High Performance:**
    * Uses **Batch Fetching** (50 emails at a time) to prevent server timeouts.
    * Uses **Batch Deletion** and single-pass `EXPUNGE` for maximum speed.
* **Interactive:** Review senders one by one or process them all in bulk.

## Prerequisites

* **Python 3.8+**
* **uv** (Recommended for dependency management) or `pip`.
* **App Password:** If you use 2FA (Gmail, Zoho, Yahoo, etc.), you must use an App-Specific Password, not your regular login password.

## Usage with `uv` (Recommended)

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, isolated execution without needing to create manual virtual environments.

### 1. Clone or Download
Clone the repo

### 2. Install requirements
uv add -r requirements.txt

### 3. Run
uv run AutoUnsubscriber.py