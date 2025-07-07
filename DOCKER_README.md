# Google Drive Transfer Script - Docker Setup

This guide explains how to run the Google Drive transfer script using Docker and Docker Compose, eliminating the need to install Python locally.

## Prerequisites

- Docker and Docker Compose installed on your system
- A Google Account
- Google Cloud Project with Drive API enabled (see main README.md for setup)

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd gdrive-transfer
```

### 2. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp env.example .env
```

Edit the `.env` file with your actual values:

```env
GDRIVE_SOURCE_FOLDER_ID="your_actual_folder_id_here"
GDRIVE_CREDENTIALS_JSON='{"installed":{"client_id":"your_actual_client_id",...}}'
```

**Important Notes:**
- Get the `GDRIVE_SOURCE_FOLDER_ID` from the Google Drive URL of the folder you want to copy
- Get the `GDRIVE_CREDENTIALS_JSON` from your Google Cloud Console credentials.json file (paste the entire JSON as a single line)

### 3. Create Data Directory

Create a directory to persist logs and authentication tokens:

```bash
mkdir data
```

### 4. Build and Start Container

Build and start the container:

```bash
docker-compose up --build -d
```

The container will start and keep running without executing the Python script automatically. You can then run the script manually when needed.

## Authentication Process

### First Run (OAuth Setup)

On the first run, you'll need to authenticate with Google:

1. Start the container: `docker-compose up --build -d`
2. Run the script manually: `docker-compose exec gdrive-transfer python gdrive_transfer_script.py` or `docker-compose exec gdrive-transfer python gdrive_size_calculator.py`
3. The script will display a message about authentication
4. Since Docker doesn't have a browser, you'll see an authorization URL in the output
5. Copy the authorization URL from the output
6. Open the URL in your browser (on your host machine)
7. Complete the Google OAuth flow
8. After authorization, Google will redirect to a localhost URL (like `http://localhost:8425/?code=...`)
9. Copy the entire redirect URL and paste it back into the container when prompted
10. The authentication token will be saved in `./data/token.pickle`

**Example flow:**
```
Please visit the following URL to authorize the application:
Authorization URL: https://accounts.google.com/o/oauth2/auth?client_id=...
After authorization, the browser will redirect to a localhost URL.
Copy the entire redirect URL and paste it here:
Paste the full redirect URL here: http://localhost:8425/?code=4/0AdQt8qh...
```

### Subsequent Runs

After the first authentication, the script will reuse the saved token automatically.

## Docker Commands

### Execute Python Script
Since the container runs continuously without executing the script automatically, you need to run it manually:

```bash
# Run the transfer script inside the running container
docker-compose exec gdrive-transfer python gdrive_transfer_script.py
```

### Access Container Shell
```bash
# Access the container shell for interactive use
docker-compose exec gdrive-transfer bash
```

### View Logs
```bash
# View real-time logs
docker-compose logs -f

# View logs for specific container
docker logs gdrive-transfer -f
```

### Stop the Container
```bash
docker-compose down
```

### Restart the Container
```bash
docker-compose restart
```

### Command Line Options

You can pass command line arguments to the script when running it manually inside the container:

```bash
# Normal run (resumes from where it left off)
docker-compose exec gdrive-transfer python gdrive_transfer_script.py

# Force rescan of folder contents
docker-compose exec gdrive-transfer python gdrive_transfer_script.py --force-rescan

# Start completely fresh (ignore previous progress)
docker-compose exec gdrive-transfer python gdrive_transfer_script.py --fresh-start

# Check current progress state
docker-compose exec gdrive-transfer python gdrive_transfer_script.py --show-progress
```

## File Structure

```
gdrive-transfer/
├── Dockerfile                 # Docker image definition
├── docker-compose.yml        # Docker Compose configuration
├── .dockerignore             # Files to exclude from Docker build
├── env.example               # Example environment variables
├── .env                      # Your actual environment variables (create this)
├── data/                     # Persistent data directory
│   ├── token.pickle          # Google OAuth token (auto-generated)
│   └── gdrive_copy_*.log     # Transfer logs
├── gdrive_transfer_script.py # Main Python script
├── requirements.txt          # Python dependencies
└── README.md                 # Main documentation
```

## Troubleshooting

### Port Already in Use
If port 8425 is already in use, modify the `docker-compose.yml` file:

```yml
ports:
  - "8426:8425"  # Change 8426 to any available port
```

### Permission Issues
If you encounter permission issues with the data directory:

```bash
sudo chown -R $USER:$USER data/
chmod 755 data/
```

### Authentication Issues
If authentication fails:

1. Delete the token file: `rm data/token.pickle`
2. Restart the container: `docker-compose restart`
3. Check your credentials in the `.env` file

### Container Won't Start
Check the logs for errors:

```bash
docker-compose logs gdrive-transfer
```

Common issues:
- Missing or invalid `.env` file
- Invalid JSON in `GDRIVE_CREDENTIALS_JSON`
- Missing `data` directory

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GDRIVE_SOURCE_FOLDER_ID` | ID of the Google Drive folder to copy | Yes |
| `GDRIVE_CREDENTIALS_JSON` | JSON credentials from Google Cloud Console | Yes |
| `LOG_DIR` | Directory for logs and tokens (default: ./data) | No |

### Updating Environment Variables

If you need to change environment variables (like switching to a different folder):

1. **Edit the `.env` file** with your new values
2. **Restart the container** to pick up the new environment variables:
   ```bash
   docker-compose restart
   ```
3. **Run the script manually** with the updated environment variables:
   ```bash
   docker-compose exec gdrive-transfer python gdrive_transfer_script.py
   ```

**Important Notes:**
- Environment variables update automatically - no rebuild required
- If you change Google credentials, delete the old token: `rm data/token.pickle`
- Each run creates a new timestamped log file in `data/`
- Only environment variables update, not the Python code (unless you rebuild)

**Example:**
```bash
# 1. Change folder ID in .env file
GDRIVE_SOURCE_FOLDER_ID="new_folder_id_here"

# 2. Restart container to pick up new environment variables
docker-compose restart

# 3. Run script with new folder ID
docker-compose exec gdrive-transfer python gdrive_transfer_script.py
```

### Updating Python Code

If you modify the Python script (`gdrive_transfer_script.py`), you need to rebuild the Docker image:

1. **Make your changes** to `gdrive_transfer_script.py`
2. **Rebuild the Docker image**:
   ```bash
   docker-compose build
   ```
3. **Restart the container** with the updated code:
   ```bash
   docker-compose up --build -d
   ```
4. **Run the script manually** with the updated code:
   ```bash
   docker-compose exec gdrive-transfer python gdrive_transfer_script.py
   ```

**Development Tip:**
The `docker-compose.yml` includes a development volume mount that allows you to edit the Python file without rebuilding:
```yml
# This line in docker-compose.yml enables live code updates
- ./gdrive_transfer_script.py:/app/gdrive_transfer_script.py:ro
```

With this mount active, you can:
1. Edit `gdrive_transfer_script.py` locally
2. Run `docker-compose exec gdrive-transfer python gdrive_transfer_script.py` (no rebuild needed)
3. The container uses your updated code immediately

**For production**, comment out or remove the development volume mount and always rebuild after code changes.

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file contains sensitive credentials
- The `data/token.pickle` file contains authentication tokens
- Both files are excluded from Docker builds via `.dockerignore`

## Performance Tips

- The script runs server-side copies (no local downloads)
- Large transfers can take hours or days
- The script is resumable - you can stop and restart safely
- Logs are preserved in the `data` directory
- Progress is shown in real-time via Docker logs

## Production Deployment

For production use:

1. Remove the development volume mount from `docker-compose.yml`:
   ```yml
   # Comment out or remove this line:
   # - ./gdrive_transfer_script.py:/app/gdrive_transfer_script.py:ro
   ```

2. Use environment variables instead of `.env` file for better security

3. Consider using Docker secrets for sensitive data

4. Set up proper log rotation for the `data` directory 