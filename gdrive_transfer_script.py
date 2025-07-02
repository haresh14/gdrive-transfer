import os
import json
import pickle
import time
import logging
import atexit
import argparse
from datetime import datetime
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configuration from Environment Variables ---
# Load environment variables from a .env file if it exists
load_dotenv()

# The ID of the shared folder you want to copy.
SOURCE_SHARED_FOLDER_ID = os.getenv('GDRIVE_SOURCE_FOLDER_ID')

# The content of your credentials.json file.
# It's recommended to store this as a single-line string in your .env file.
GDRIVE_CREDENTIALS_JSON = os.getenv('GDRIVE_CREDENTIALS_JSON')

# Destination folder in 'My Drive'. 'root' is the top level.
# Can be overridden with GDRIVE_DESTINATION_PARENT_ID environment variable.
_dest_env_var = os.getenv('GDRIVE_DESTINATION_PARENT_ID')
DESTINATION_PARENT_ID = _dest_env_var.strip() if _dest_env_var and _dest_env_var.strip() else 'root'

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive']
# Use data directory for token file in Docker environment
TOKEN_DIR = os.getenv('LOG_DIR', './data')
TOKEN_FILE = os.path.join(TOKEN_DIR, 'token.pickle')

# Generate timestamped log file name
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
# Use /data/log directory for logs
LOG_DIR = '/data/log'
LOG_FILE = os.path.join(LOG_DIR, f'gdrive_copy_{timestamp}.log')

# Cache file for folder scan counts
CACHE_DIR = os.path.join(TOKEN_DIR, 'cache')
FOLDER_COUNT_CACHE_FILE = os.path.join(CACHE_DIR, 'folder_counts.json')

# Ensure all required directories exist
def ensure_directories():
    """Create all required directories if they don't exist."""
    directories = {
        'Token directory': TOKEN_DIR,
        'Log directory': LOG_DIR,
        'Cache directory': CACHE_DIR
    }

    for desc, directory in directories.items():
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                print(f"Created {desc}: {directory}")
            else:
                print(f"{desc} already exists: {directory}")

            # Test write permissions
            test_file = os.path.join(directory, '.write_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except Exception:
                print(f"ERROR: {desc} is not writable: {directory}")
                print(f"Please ensure you have write permissions to this directory.")
                exit(1)

        except PermissionError:
            print(f"ERROR: Permission denied creating {desc}: {directory}")
            print(f"Please ensure you have write permissions to create this directory.")
            exit(1)
        except Exception as e:
            print(f"ERROR: Could not create {desc} {directory}: {e}")
            exit(1)

# Create directories at startup
ensure_directories()

# --- Global variables for progress tracking ---
total_items = 0
processed_items = 0

# --- Setup Logging ---
# Configure logger to output to both console and a file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Function to log script termination
def log_script_end():
    """Log when script ends (normally or unexpectedly)."""
    logging.info("--- Script execution ended ---")
    logging.info(f"Log file saved as: {LOG_FILE}")

# Register the cleanup function to run on script exit
atexit.register(log_script_end)

# --- Helper Functions ---

def load_folder_count_cache():
    """Load the folder count cache from disk."""
    try:
        if os.path.exists(FOLDER_COUNT_CACHE_FILE):
            with open(FOLDER_COUNT_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"Could not load folder count cache: {e}")
    return {}

def save_folder_count_cache(cache_data):
    """Save the folder count cache to disk."""
    try:
        with open(FOLDER_COUNT_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        logging.error(f"Could not save folder count cache: {e}")

def get_cached_folder_count(folder_id):
    """Get cached count for a folder ID, or None if not cached."""
    cache = load_folder_count_cache()
    return cache.get(folder_id)

def cache_folder_count(folder_id, count):
    """Cache the count for a folder ID."""
    cache = load_folder_count_cache()
    cache[folder_id] = {
        'count': count,
        'timestamp': datetime.now().isoformat()
    }
    save_folder_count_cache(cache)

def authenticate_account():
    """Authenticates the user and returns a Drive API service object."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logging.info("Refreshing access token...")
            creds.refresh(Request())
        else:
            logging.info("\nPlease authenticate your Google account.")
            # Load credentials from environment variable
            client_config = json.loads(GDRIVE_CREDENTIALS_JSON)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            # Use port 8425 for Docker compatibility and bind to all interfaces
            # Don't try to open browser automatically in Docker environment
            try:
                creds = flow.run_local_server(port=8425, bind_addr='0.0.0.0', open_browser=False)
            except Exception as e:
                logging.error(f"Failed to run local server: {e}")
                logging.info("Please visit the following URL to authorize the application:")
                auth_url, _ = flow.authorization_url(prompt='consent')
                logging.info(f"Authorization URL: {auth_url}")
                logging.info("After authorization, the browser will redirect to a localhost URL.")
                logging.info("Copy the entire redirect URL and paste it here:")
                authorization_response = input("Paste the full redirect URL here: ")
                flow.fetch_token(authorization_response=authorization_response)
                creds = flow.credentials

        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
            logging.info("Authentication successful. Token saved.")

    return build('drive', 'v3', credentials=creds)

def find_existing_item(service, name, parent_id, mime_type):
    """Finds an existing file or folder by name and parent."""
    # Validate parent_id
    if not parent_id or parent_id.strip() == '':
        logging.error(f"Invalid parent_id provided: '{parent_id}' for item '{name}'")
        return None

    # Escape single quotes in the name for the query
    sanitized_name = name.replace("'", "\\'")
    query = f"'{parent_id}' in parents and name = '{sanitized_name}' and mimeType = '{mime_type}' and trashed = false"
    try:
        response = service.files().list(
            q=query,
            fields='files(id, size)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        files = response.get('files', [])
        return files[0] if files else None
    except HttpError as error:
        logging.error(f"An error occurred while searching for item '{name}' in parent '{parent_id}': {error}")
        return None

def count_total_items(service, folder_id):
    """Recursively counts the total number of files and folders."""
    count = 0
    page_token = None
    while True:
        try:
            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                pageSize=1000,
                fields="nextPageToken, files(id, mimeType)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token
            ).execute()
            items = response.get('files', [])
            count += len(items)
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    count += count_total_items(service, item['id'])
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break
        except HttpError as error:
            logging.error(f"An error occurred during item count: {error}")
            break
    return count

def copy_folder_recursively(service, source_folder_id, dest_parent_folder_id, indent_level=0):
    """Recursively and fault-tolerantly copies a folder and its contents."""
    global processed_items
    page_token = None
    while True:
        try:
            results = service.files().list(
                q=f"'{source_folder_id}' in parents and trashed=false",
                pageSize=200,
                fields="nextPageToken, files(id, name, mimeType, size)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token
            ).execute()

            items = results.get('files', [])
            indent = "  " * indent_level

            for item in items:
                processed_items += 1
                progress = (processed_items / total_items) * 100 if total_items > 0 else 0
                progress_str = f"[{progress:6.2f}%]"

                item_name = item['name']
                item_id = item['id']
                item_mime_type = item['mimeType']
                source_size = item.get('size')

                if item_mime_type == 'application/vnd.google-apps.folder':
                    logging.info(f"{progress_str} {indent}📂 Processing folder: {item_name}")
                    existing_folder = find_existing_item(service, item_name, dest_parent_folder_id, item_mime_type)

                    if existing_folder:
                        new_folder_id = existing_folder['id']
                        logging.info(f"{progress_str} {indent}  -> Found existing folder. Skipping creation.")
                    else:
                        new_folder_metadata = {'name': item_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [dest_parent_folder_id]}
                        new_folder = service.files().create(body=new_folder_metadata, fields='id', supportsAllDrives=True).execute()
                        new_folder_id = new_folder.get('id')
                        logging.info(f"{progress_str} {indent}  -> ✅ Created new folder in your My Drive.")

                    copy_folder_recursively(service, item_id, new_folder_id, indent_level + 1)

                else: # It's a file
                    logging.info(f"{progress_str} {indent}📄 Processing file: {item_name}...")
                    existing_file = find_existing_item(service, item_name, dest_parent_folder_id, item_mime_type)

                    should_copy = True
                    if existing_file:
                        # Convert sizes to integers for comparison
                        existing_size_int = int(existing_file.get('size', 0))
                        source_size_int = int(source_size or 0)

                        if existing_size_int == source_size_int:
                            logging.info(f"{progress_str} {indent}  -> File already exists with matching size. Skipping.")
                            should_copy = False
                        else:
                            logging.warning(f"{progress_str} {indent}  -> File exists with different size. Deleting and re-copying.")
                            try:
                                service.files().delete(fileId=existing_file['id'], supportsAllDrives=True).execute()
                            except HttpError as e:
                                logging.error(f"Error deleting file: {e}")

                    if should_copy:
                        try:
                            copied_file = service.files().copy(
                                fileId=item_id,
                                body={'parents': [dest_parent_folder_id], 'name': item_name},
                                supportsAllDrives=True,
                                fields='id'
                            ).execute()
                            logging.info(f"{progress_str} {indent}  -> ✅ Copied file to your My Drive.")
                        except HttpError as error:
                            logging.error(f"{progress_str} {indent}  -> ❌ An error occurred copying file: {error}")

            page_token = results.get('nextPageToken', None)
            if page_token is None:
                break
        except HttpError as error:
            logging.error(f"An error occurred: {error}")
            time.sleep(5) # Wait before retrying on error

def main():
    """Main function to orchestrate the Drive transfer."""
    global total_items

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Google Drive Fault-Tolerant Copy Script')
    parser.add_argument('--force-rescan', action='store_true',
                       help='Force re-scanning of folder contents (ignore cache)')
    args = parser.parse_args()

    logging.info("--- Google Drive Fault-Tolerant Copy Script (Env-Friendly) ---")
    logging.info(f"Log file: {LOG_FILE}")
    logging.info(f"Script started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Debug environment variables
    logging.info(f"Environment variables loaded:")
    logging.info(f"  GDRIVE_SOURCE_FOLDER_ID: {'SET' if SOURCE_SHARED_FOLDER_ID else 'NOT SET'}")
    logging.info(f"  GDRIVE_CREDENTIALS_JSON: {'SET' if GDRIVE_CREDENTIALS_JSON else 'NOT SET'}")
    logging.info(f"  GDRIVE_DESTINATION_PARENT_ID: '{os.getenv('GDRIVE_DESTINATION_PARENT_ID')}' -> resolved to '{DESTINATION_PARENT_ID}'")

    try:
        if not all([SOURCE_SHARED_FOLDER_ID, GDRIVE_CREDENTIALS_JSON]):
            logging.error("\nERROR: Missing required environment variables.")
            logging.error("Please ensure 'GDRIVE_SOURCE_FOLDER_ID' and 'GDRIVE_CREDENTIALS_JSON' are set in your .env file.")
            return

        # Validate destination parent ID
        if not DESTINATION_PARENT_ID or DESTINATION_PARENT_ID.strip() == '':
            logging.error("ERROR: DESTINATION_PARENT_ID is empty or invalid.")
            logging.error("Please check your GDRIVE_DESTINATION_PARENT_ID environment variable.")
            return

        logging.info(f"Source folder ID: {SOURCE_SHARED_FOLDER_ID}")
        logging.info(f"Destination parent ID: {DESTINATION_PARENT_ID} {'(root = My Drive top level)' if DESTINATION_PARENT_ID == 'root' else ''}")

        service = authenticate_account()
        logging.info("\nAccount authenticated successfully.")

        # Check if we have a cached count for this folder (unless force rescan is requested)
        cached_data = get_cached_folder_count(SOURCE_SHARED_FOLDER_ID) if not args.force_rescan else None
        if cached_data and not args.force_rescan:
            total_items = cached_data['count']
            cached_time = cached_data['timestamp']
            logging.info(f"\n--- Using cached count from {cached_time} ---")
            logging.info(f"Found {total_items} total items to process (from cache).")
            logging.info("Use --force-rescan to force a new count if folder contents have changed.")
        else:
            if args.force_rescan:
                logging.info("\n--- Force rescan requested ---")
            logging.info("\n--- Pre-scan: Counting total files and folders... ---")
            total_items = count_total_items(service, SOURCE_SHARED_FOLDER_ID)
            logging.info(f"Found {total_items} total items to process.")
            # Cache the count for future runs
            cache_folder_count(SOURCE_SHARED_FOLDER_ID, total_items)
            logging.info("Count cached for future runs.")

        logging.info("\n--- Starting Resumable File and Folder Copy ---")

        copy_folder_recursively(service, SOURCE_SHARED_FOLDER_ID, DESTINATION_PARENT_ID)

        logging.info("\n--- Copy Complete! ---")

    except KeyboardInterrupt:
        logging.warning("\n--- Script interrupted by user (Ctrl+C) ---")
        logging.info(f"Progress: {processed_items}/{total_items} items processed")
    except Exception as e:
        logging.error(f"\n--- Unexpected error occurred ---")
        logging.error(f"Error: {str(e)}")
        logging.error(f"Progress: {processed_items}/{total_items} items processed")
        raise

if __name__ == '__main__':
    main()
