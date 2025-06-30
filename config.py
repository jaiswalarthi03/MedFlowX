# AWS Configuration
# Set your AWS credentials here or use environment variables for security
AWS_ACCESS_KEY_ID = ''  # e.g., 'AKIA...'
AWS_SECRET_ACCESS_KEY = ''  # e.g., 'your-aws-secret-key'
AWS_REGION = 'us-east-1'  # e.g., 'us-east-1'

# Flask Configuration
SECRET_KEY = ''  # Set a strong secret key for Flask sessions
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
UPLOAD_FOLDER = 'uploads'

# Ultravox API Configuration
ULTRAVOX_API_KEY = ''  # e.g., 'your-ultravox-api-key'
ULTRAVOX_API_URL = 'https://api.ultravox.ai/api'

# Logging Configuration
LOG_LEVEL = 'INFO'
SUPPRESS_BOTO_DEBUG = True

# Default voice for Cynthia (Joanna)
DEFAULT_VOICE = 'Joanna' 