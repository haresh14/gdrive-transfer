import os
import json
import pickle
import logging
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

# The ID of the folder you want to analyze.
SOURCE_FOLDER_ID = os.getenv('GDRIVE_SOURCE_FOLDER_ID')

# The content of your credentials.json file.
GDRIVE_CREDENTIALS_JSON = os.getenv('GDRIVE_CREDENTIALS_JSON')

print("\nENVIRONMENT VARIABLES:")
print(f"  GDRIVE_SOURCE_FOLDER_ID: {SOURCE_FOLDER_ID}")

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# Use data directory for token file
TOKEN_DIR = os.getenv('LOG_DIR', './data')
TOKEN_FILE = os.path.join(TOKEN_DIR, 'token.pickle')

# Generate timestamped log file name
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
LOG_DIR = '/data/log' if os.path.exists('/data') else './data/log'
LOG_FILE = os.path.join(LOG_DIR, f'gdrive_size_{timestamp}.log')

# Cache file for size calculations
CACHE_DIR = os.path.join(TOKEN_DIR, 'cache')
SIZE_CACHE_FILE = os.path.join(CACHE_DIR, 'folder_sizes.json')

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
            exit(1)
        except Exception as e:
            print(f"ERROR: Could not create {desc} {directory}: {e}")
            exit(1)

# Create directories at startup
ensure_directories()

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- Helper Functions ---

def format_size(size_bytes):
    """Convert bytes to human readable format."""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.2f} {size_names[i]}"

def load_size_cache():
    """Load the size cache from disk."""
    try:
        if os.path.exists(SIZE_CACHE_FILE):
            with open(SIZE_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"Could not load size cache: {e}")
    return {}

def save_size_cache(cache_data):
    """Save the size cache to disk."""
    try:
        with open(SIZE_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        logging.error(f"Could not save size cache: {e}")

def get_cached_folder_size(folder_id):
    """Get cached size for a folder ID, or None if not cached."""
    cache = load_size_cache()
    return cache.get(folder_id)

def cache_folder_size(folder_id, size_data):
    """Cache the size data for a folder ID."""
    cache = load_size_cache()
    cache[folder_id] = {
        'total_size': size_data['total_size'],
        'file_count': size_data['file_count'],
        'folder_count': size_data['folder_count'],
        'timestamp': datetime.now().isoformat()
    }
    save_size_cache(cache)

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
            # Use port 8426 for size calculator to avoid conflicts
            try:
                creds = flow.run_local_server(port=8426, bind_addr='0.0.0.0', open_browser=False)
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

def calculate_folder_size(service, folder_id, folder_name="Root", indent_level=0):
    """Recursively calculates the total size of a folder and its contents."""
    total_size = 0
    file_count = 0
    folder_count = 0
    page_token = None
    indent = "  " * indent_level

    logging.info(f"{indent}📂 Analyzing folder: {folder_name}")

    while True:
        try:
            response = service.files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                pageSize=1000,
                fields="nextPageToken, files(id, name, mimeType, size)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token
            ).execute()

            items = response.get('files', [])

            for item in items:
                item_name = item['name']
                item_id = item['id']
                item_mime_type = item['mimeType']
                item_size = item.get('size', 0)

                if item_mime_type == 'application/vnd.google-apps.folder':
                    folder_count += 1
                    # Recursively calculate subfolder size
                    subfolder_size, subfolder_files, subfolder_folders = calculate_folder_size(
                        service, item_id, item_name, indent_level + 1
                    )
                    total_size += subfolder_size
                    file_count += subfolder_files
                    folder_count += subfolder_folders
                else:
                    file_count += 1
                    if item_size:
                        file_size = int(item_size)
                        total_size += file_size
                        logging.debug(f"{indent}  📄 {item_name}: {format_size(file_size)} ({file_size:,} bytes)")
                    else:
                        # Google Docs, Sheets, etc. don't have size in bytes
                        logging.debug(f"{indent}  📄 {item_name}: (Google Doc/Sheet/etc.)")

            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        except HttpError as error:
            logging.error(f"An error occurred while analyzing folder '{folder_name}': {error}")
            break

    if indent_level == 0:
        logging.info(f"{indent}📊 Folder '{folder_name}' summary:")
    else:
        logging.info(f"{indent}📊 Subfolder '{folder_name}' summary:")

    logging.info(f"{indent}  Total size: {format_size(total_size)} ({total_size:,} bytes)")
    logging.info(f"{indent}  Files: {file_count}")
    logging.info(f"{indent}  Folders: {folder_count}")

    return total_size, file_count, folder_count

def get_folder_info(service, folder_id):
    """Get basic information about a folder."""
    try:
        folder = service.files().get(
            fileId=folder_id,
            fields='name, mimeType, owners, createdTime, modifiedTime',
            supportsAllDrives=True
        ).execute()
        return folder
    except HttpError as error:
        logging.error(f"Error getting folder info: {error}")
        return None

def main():
    """Main function to orchestrate the Drive size calculation."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Google Drive Folder Size Calculator')
    parser.add_argument('--force-rescan', action='store_true',
                       help='Force re-scanning of folder contents (ignore cache)')
    parser.add_argument('--folder-id', type=str,
                       help='Override folder ID from command line')
    parser.add_argument('--detailed', action='store_true',
                       help='Show detailed file-by-file breakdown')
    args = parser.parse_args()

    logging.info("--- Google Drive Folder Size Calculator ---")
    logging.info(f"Log file: {LOG_FILE}")
    logging.info(f"Script started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Use command line folder ID if provided, otherwise use environment variable
    folder_id = args.folder_id or SOURCE_FOLDER_ID

    if not folder_id:
        logging.error("\nERROR: No folder ID provided.")
        logging.error("Please set GDRIVE_SOURCE_FOLDER_ID in your .env file or use --folder-id argument.")
        return

    if not GDRIVE_CREDENTIALS_JSON:
        logging.error("\nERROR: Missing GDRIVE_CREDENTIALS_JSON environment variable.")
        logging.error("Please set this in your .env file.")
        return

    # Set detailed logging if requested
    if args.detailed:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        logging.info(f"Analyzing folder ID: {folder_id}")

        service = authenticate_account()
        logging.info("Account authenticated successfully.")

        # Get folder information
        folder_info = get_folder_info(service, folder_id)
        if folder_info:
            logging.info(f"\n--- Folder Information ---")
            logging.info(f"Name: {folder_info.get('name', 'Unknown')}")
            logging.info(f"Created: {folder_info.get('createdTime', 'Unknown')}")
            logging.info(f"Modified: {folder_info.get('modifiedTime', 'Unknown')}")
            if 'owners' in folder_info:
                owners = [owner.get('displayName', owner.get('emailAddress', 'Unknown')) 
                         for owner in folder_info['owners']]
                logging.info(f"Owners: {', '.join(owners)}")

        # Check if we have cached data (unless force rescan is requested)
        cached_data = get_cached_folder_size(folder_id) if not args.force_rescan else None
        if cached_data and not args.force_rescan:
            cached_time = cached_data['timestamp']
            logging.info(f"\n--- Using cached data from {cached_time} ---")
            logging.info(f"Total size: {format_size(cached_data['total_size'])} ({cached_data['total_size']:,} bytes)")
            logging.info(f"Files: {cached_data['file_count']}")
            logging.info(f"Folders: {cached_data['folder_count']}")
            logging.info("Use --force-rescan to force a new calculation.")
        else:
            if args.force_rescan:
                logging.info("\n--- Force rescan requested ---")

            logging.info("\n--- Starting Size Calculation ---")

            folder_name = folder_info.get('name', 'Unknown') if folder_info else 'Unknown'
            total_size, file_count, folder_count = calculate_folder_size(
                service, folder_id, folder_name
            )

            # Cache the results
            size_data = {
                'total_size': total_size,
                'file_count': file_count,
                'folder_count': folder_count
            }
            cache_folder_size(folder_id, size_data)

            logging.info("\n--- Final Results ---")
            logging.info(f"Total size: {format_size(total_size)} ({total_size:,} bytes)")
            logging.info(f"Total files: {file_count:,}")
            logging.info(f"Total folders: {folder_count:,}")
            logging.info("Results cached for future runs.")

    except KeyboardInterrupt:
        logging.warning("\n--- Script interrupted by user (Ctrl+C) ---")
    except Exception as e:
        logging.error(f"\n--- Unexpected error occurred ---")
        logging.error(f"Error: {str(e)}")
        raise

    logging.info("--- Script execution completed ---")

if __name__ == '__main__':
    main()