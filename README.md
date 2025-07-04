# Google Drive Folder Copy Script

A fault-tolerant Python script to recursively copy a large, deeply-nested Google Drive shared folder into your own "My Drive".

## Features

* **Fault-Tolerant & Resumable**: You can stop and start the script at any time. It will pick up where it left off without creating duplicate files or folders.
* **Smart Progress Tracking**: Maintains a persistent record of processed items to avoid re-checking already processed files on subsequent runs, significantly improving performance for large transfers.
* **True Resumption**: When restarted, skips all previously processed items without making API calls to check their existence, saving time and API quota.
* **Data Integrity Check**: Compares file sizes and re-copies any files that don't match between the source and destination.
* **Secure**: Uses environment variables to keep your secret credentials separate from the code, making it safe to use with Git.
* **Progress Logging**: Displays detailed progress in the terminal and saves a complete log to `/data/log/` directory for later review.
* **Smart Caching**: Caches folder scan results to avoid re-scanning the same folder ID on subsequent runs, significantly improving startup time.
* **Server-Side Copy**: Copies files directly on Google's servers without downloading them to your computer, saving bandwidth.

## Prerequisites

* Python 3.6+
* A Google Account

## Setup Instructions

### Step 1: Get the Script

Clone this repository or download the `gdrive_transfer_script.py` file to a new project folder on your local machine.

### Step 2: Google Cloud Project Setup

First, you need to authorize the script to use the Google Drive API on your behalf.

1.  **Create a Google Cloud Project**:
    * Go to the [Google Cloud Console](https://console.cloud.google.com/).
    * Create a **New Project**.

2.  **Enable the Google Drive API**:
    * In the search bar, find and **Enable** the "Google Drive API".

3.  **Configure OAuth Consent Screen**:
    * Navigate to **APIs & Services > OAuth consent screen**.
    * Choose **External** and click Create.
    * Fill in the required fields (App name, support email, developer contact).
    * On the "Scopes" page, click **Save and Continue**.
    * On the "Test users" page, add your own Google email address.

4.  **Create Credentials**:
    * Navigate to **APIs & Services > Credentials**.
    * Click **+ Create Credentials > OAuth client ID**.
    * Select **Desktop app** as the application type.
    * Click **Create**. A window will pop up.
    * Click **DOWNLOAD JSON**. This will give you a `credentials.json` file. We will use its content in the next step.

### Step 3: Find the Source Folder ID

You need to tell the script which shared folder to copy.

1.  In Google Drive, open the shared folder.
2.  Look at the URL. The Folder ID is the long string after `.../folders/`.
    * *Example URL*: `https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j`
    * *Example ID*: `1a2b3c4d5e6f7g8h9i0j`

### Step 3.5: Find the Destination Folder ID (Optional)

By default, files will be copied to the root of your "My Drive". If you want to copy them to a specific folder:

1.  In Google Drive, navigate to or create the destination folder in your "My Drive".
2.  Open the destination folder.
3.  Look at the URL and extract the Folder ID the same way as in Step 3.
4.  Use this ID for the `GDRIVE_DESTINATION_PARENT_ID` environment variable.

### Step 4: Set Up Environment Variables (`.env` file)

This is the most secure way to configure the script.

1.  **Create a `.env` file** in the root of your project folder.
2.  **Create a `.gitignore` file** and add `.env` and `token.pickle` to it to prevent committing secrets.
    ```gitignore
    # Environment variables
    .env

    # Google OAuth token
    token.pickle
    ```
3.  **Add the following content** to your `.env` file:
    ```env
    GDRIVE_SOURCE_FOLDER_ID="your_folder_id_here"
    GDRIVE_CREDENTIALS_JSON='{"web":{"client_id":"...", ...}}'
    # Optional: Destination folder ID (defaults to 'root' if not set)
    # GDRIVE_DESTINATION_PARENT_ID="your_destination_folder_id_here"
    ```
4.  **Update the values**:
    * Replace `"your_folder_id_here"` with the Folder ID you found in Step 3.
    * Open the `credentials.json` file you downloaded, copy its **entire content**, and paste it inside the single quotes for `GDRIVE_CREDENTIALS_JSON`. It must be on a single line.
    * (Optional) If you want to copy files to a specific folder in your My Drive instead of the root, uncomment and set `GDRIVE_DESTINATION_PARENT_ID` to the target folder's ID.

### Step 5: Install Dependencies

#### Option A: Local Python Installation

Open your terminal or command prompt, navigate to your project folder, and run:
```bash
pip install -r requirements.txt
```

#### Option B: Docker (Recommended)

If you prefer not to install Python locally, you can use Docker instead:

1. Make sure Docker and Docker Compose are installed on your system
2. Run the setup script:
   ```bash
   ./start.sh
   ```
3. Follow the interactive prompts to configure and run the container

For detailed Docker instructions, see `DOCKER_README.md`.

## Running the Script

### Basic Usage

```bash
python gdrive_transfer_script.py
```

### Command Line Options

* `--force-rescan`: Force re-scanning of folder contents, ignoring any cached count data. Use this if the source folder contents have changed since the last run.
* `--fresh-start`: Clear all progress state and start fresh, ignoring any previous progress. Use this if you want to restart the entire transfer from the beginning.
* `--show-progress`: Display current progress state information and exit without running the transfer.

Examples:
```bash
# Normal run (resumes from where it left off)
python gdrive_transfer_script.py

# Force rescan of folder contents
python gdrive_transfer_script.py --force-rescan

# Start completely fresh (ignore previous progress)
python gdrive_transfer_script.py --fresh-start

# Check current progress state
python gdrive_transfer_script.py --show-progress
```

### Caching Behavior

The script automatically caches the total count of files and folders for each source folder ID. This means:

- **First run**: The script will scan the entire folder structure to count files (this can take time for large folders)
- **Subsequent runs**: The script will use the cached count, starting the copy process immediately
- **Changed folder contents**: Use `--force-rescan` to update the cache if files have been added/removed from the source folder

Cache files are stored in `./data/cache/folder_counts.json`.

## Progress Tracking and Resumption

The script now includes advanced progress tracking that dramatically improves performance for large transfers:

### How It Works

1. **First Run**: The script processes items normally, recording each processed item in a progress state file.
2. **Subsequent Runs**: The script loads the progress state and skips all previously processed items without making API calls to check their existence.
3. **True Resumption**: Only unprocessed items are checked and copied, saving significant time and API quota.

### Progress State Management

- **Progress State File**: `./data/cache/progress_state.json`
- **Automatic Saving**: Progress is saved every 10 items and at the end of each folder
- **Interruption Safe**: Progress is saved when the script is interrupted (Ctrl+C) or encounters errors

### Progress Status Types

- `existing`: Item already existed in destination with matching size
- `created`: New folder was created
- `copied`: File was successfully copied
- `error`: An error occurred during processing

### Performance Benefits

For large transfers (100,000+ files):
- **First run**: Normal processing time
- **Subsequent runs**: Only processes new/changed items
- **API calls reduced**: Up to 99% reduction in API calls for already processed items
- **Faster startup**: No need to check existence of previously processed items

### Managing Progress State

```bash
# Check current progress
python gdrive_transfer_script.py --show-progress

# Resume from where you left off (default behavior)
python gdrive_transfer_script.py

# Start completely fresh (clears all progress)
python gdrive_transfer_script.py --fresh-start
```
