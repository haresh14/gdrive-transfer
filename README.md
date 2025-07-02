# Google Drive Folder Copy Script

A fault-tolerant Python script to recursively copy a large, deeply-nested Google Drive shared folder into your own "My Drive".

## Features

* **Fault-Tolerant & Resumable**: You can stop and start the script at any time. It will pick up where it left off without creating duplicate files or folders.
* **Data Integrity Check**: Compares file sizes and re-copies any files that don't match between the source and destination.
* **Secure**: Uses environment variables to keep your secret credentials separate from the code, making it safe to use with Git.
* **Progress Logging**: Displays detailed progress in the terminal and saves a complete log to `copy_log.txt` for later review.
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
    ```
4.  **Update the values**:
    * Replace `"your_folder_id_here"` with the Folder ID you found in Step 3.
    * Open the `credentials.json` file you downloaded, copy its **entire content**, and paste it inside the single quotes for `GDRIVE_CREDENTIALS_JSON`. It must be on a single line.

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
