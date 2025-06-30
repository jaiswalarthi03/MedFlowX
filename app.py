import os
import logging
import requests
import sys
import importlib.util
from flask import Flask
from config import *

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Suppress boto debug messages
if SUPPRESS_BOTO_DEBUG:
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = [
        'flask', 'requests', 'boto3', 'google.generativeai', 
        'xmltodict', 'jinja2', 'werkzeug'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            logger.info(f"✅ {package} is available")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"❌ {package} is missing")
    
    if missing_packages:
        logger.error(f"Missing packages: {', '.join(missing_packages)}")
        logger.info("Install missing packages with: pip install -r requirements.txt")
        return False
    
    logger.info("All required dependencies are available")
    return True

def check_aws_configuration():
    """Check AWS configuration"""
    try:
        import boto3
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        logger.info(f"✅ AWS configured successfully! Account: {identity['Account']}")
        return True
    except Exception as e:
        logger.warning(f"AWS not configured: {e}")
        logger.info("AWS services will not be available. Configure AWS credentials to enable advanced features.")
        return False

def check_upload_directory():
    """Check if upload directory exists"""
    if os.path.exists(UPLOAD_FOLDER):
        logger.info(f"Upload directory exists: {UPLOAD_FOLDER}")
        return True
    else:
        try:
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            logger.info(f"Created upload directory: {UPLOAD_FOLDER}")
            return True
        except Exception as e:
            logger.error(f"Failed to create upload directory: {e}")
            return False

def initialize_aws_service():
    """Initialize AWS service"""
    try:
        from utils.aws_service import aws_service
        if aws_service.is_available():
            logger.info("AWS healthcare service initialized successfully")
            return True
        else:
            logger.warning("AWS healthcare service not available")
            return False
    except Exception as e:
        logger.error(f"Failed to initialize AWS service: {e}")
        return False

# Set AWS credentials from config
os.environ['AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
os.environ['AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY
os.environ['AWS_DEFAULT_REGION'] = AWS_REGION

# Create the app
app = Flask(__name__)
app.secret_key = SECRET_KEY

# Configure upload settings
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Import routes
from routes import *

def main():
    """Main startup function"""
    logger.info("Starting CDA-to-FHIR Converter with Advanced AWS Integration")
    logger.info("=" * 80)
    
    # Check dependencies
    if not check_dependencies():
        logger.error("Dependency check failed. Please install missing packages.")
        sys.exit(1)
    
    # Check AWS configuration
    aws_configured = check_aws_configuration()
    
    # Check upload directory
    if not check_upload_directory():
        logger.error("Upload directory check failed.")
        sys.exit(1)
    
    # Initialize AWS service
    logger.info("Initializing AWS healthcare service...")
    initialize_aws_service()
    
    # Start Flask application
    logger.info("Starting Flask web server...")
    logger.info("=" * 80)
    
    try:
        logger.info("Application started successfully!")
        logger.info(f"Web Interface: http://localhost:5000")
        logger.info(f"Dashboard: http://localhost:5000/dashboard")
        logger.info(f"Features: http://localhost:5000/features")
        logger.info("=" * 80)
        
        if not aws_configured:
            logger.info("AWS not configured - basic features only")
        
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
