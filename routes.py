import os
import json
import uuid
import requests
import time
from datetime import datetime, timedelta
from flask import render_template, request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from app import app
from config import ULTRAVOX_API_KEY, ULTRAVOX_API_URL
from utils.cda_processor import CDAProcessor
from utils.fhir_converter import FHIRConverter
from utils.aws_service import aws_service
from utils.mongodb_store import mongodb_store
import copy

# Global MongoDB store instance
data_store = mongodb_store
import random

# Allowed file extensions
ALLOWED_EXTENSIONS = {'xml', 'cda', 'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def upload():
    """Main upload screen for CDA documents and images"""
    return render_template('upload.html')

@app.route('/dashboard')
def dashboard():
    """Analytics dashboard showing FHIR conversion results"""
    return render_template('dashboard.html')

@app.route('/features')
def features():
    """Features and USP page showing unique advantages"""
    return render_template('features.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """UNIFIED UPLOAD ENDPOINT - Handles all processing modes with real-time status"""
    start_time = time.time()
    
    # Ensure patient_data is always present in response_data
    response_data = {
        'id': str(uuid.uuid4()),
        'file_id': None,
        'file_type': None,
        'processing_mode': None,
        'processing_timestamp': datetime.now().isoformat(),
        'status_updates': [],
        'aws_resources_created': False,
        'cleanup_available': False,
        'patient_data': {
            'patient_id': None,
            'name': None,
            'gender': None,
            'birth_date': None,
            'address': None,
            'phone': None,
            'medical_record_number': None,
            'medical_conditions': [],
            'medications': [],
            'phi_detected': []
        },
        'processing_time': 0,
        'api_gateway_status': None,
        's3_status': None,
        'cloudwatch_status': None,
        'secrets_manager_status': None,
        'success': True
    }
    
    try:
        # Initialize status updates list early
        status_updates = []
        
        # API Gateway Integration - Create infrastructure if needed
        app.logger.info("🔗 Initializing API Gateway integration...")
        status_updates.append({
            'step': 'API Gateway',
            'status': '🔗 Initializing API Gateway integration...',
            'timestamp': datetime.now().isoformat()
        })
        
        api_gateway_result = aws_service.create_api_gateway_infrastructure()
        
        if api_gateway_result['success']:
            app.logger.info(f"✅ API Gateway ready: {api_gateway_result['api_url']}")
            status_updates.append({
                'step': 'API Gateway',
                'status': f'✅ Created API Gateway: {api_gateway_result["api_name"]} (ID: {api_gateway_result["api_id"]})',
                'timestamp': datetime.now().isoformat()
            })
            status_updates.append({
                'step': 'API Gateway',
                'status': f'✅ API Gateway deployed successfully: {api_gateway_result["api_url"]}',
                'timestamp': datetime.now().isoformat()
            })
            status_updates.append({
                'step': 'API Gateway',
                'status': f'✅ API Gateway ready: {api_gateway_result["api_url"]}',
                'timestamp': datetime.now().isoformat()
            })
            # Log API Gateway invocation
            aws_service.log_api_gateway_invocation('/api/upload', 'POST', 'INITIALIZED')
            status_updates.append({
                'step': 'API Gateway',
                'status': '🔗 API Gateway: POST /api/upload - INITIALIZED',
                'timestamp': datetime.now().isoformat()
            })
        else:
            app.logger.warning(f"⚠️ API Gateway setup: {api_gateway_result['message']}")
            status_updates.append({
                'step': 'API Gateway',
                'status': f'⚠️ API Gateway setup: {api_gateway_result["message"]}',
                'timestamp': datetime.now().isoformat()
            })
        
        # CloudWatch Alarms Integration - Set up monitoring
        app.logger.info("🚨 Setting up CloudWatch alarms for monitoring...")
        status_updates.append({
            'step': 'CloudWatch',
            'status': '🚨 Setting up CloudWatch alarms for monitoring...',
            'timestamp': datetime.now().isoformat()
        })
        
        cloudwatch_result = aws_service.create_cloudwatch_alarms()
        
        if cloudwatch_result['success']:
            app.logger.info(f"✅ CloudWatch alarms created: {cloudwatch_result['message']}")
            status_updates.append({
                'step': 'CloudWatch',
                'status': f'✅ CloudWatch alarms created: {cloudwatch_result["message"]}',
                'timestamp': datetime.now().isoformat()
            })
        else:
            app.logger.warning(f"⚠️ CloudWatch alarms setup: {cloudwatch_result['message']}")
            status_updates.append({
                'step': 'CloudWatch',
                'status': f'⚠️ CloudWatch alarms setup: {cloudwatch_result["message"]}',
                'timestamp': datetime.now().isoformat()
            })
        
        # Secrets Manager Integration - Set up and load secrets
        app.logger.info("🔐 Setting up Secrets Manager and loading secrets...")
        status_updates.append({
            'step': 'Secrets Manager',
            'status': '🔐 Setting up Secrets Manager and loading secrets...',
            'timestamp': datetime.now().isoformat()
        })
        
        secrets_result = aws_service.create_secrets_manager_secrets()
        
        if secrets_result['success']:
            app.logger.info(f"✅ Secrets Manager setup: {secrets_result['message']}")
            status_updates.append({
                'step': 'Secrets Manager',
                'status': f'✅ Secrets Manager setup: {secrets_result["message"]}',
                'timestamp': datetime.now().isoformat()
            })
            
            # Load API keys from Secrets Manager
            api_keys_result = aws_service.get_secret_from_manager('healthcare-api-keys')
            if api_keys_result['success']:
                app.logger.info("✅ API keys loaded from Secrets Manager")
                status_updates.append({
                    'step': 'Secrets Manager',
                    'status': '✅ API keys loaded from Secrets Manager',
                    'timestamp': datetime.now().isoformat()
                })
            else:
                app.logger.warning(f"⚠️ API keys loading: {api_keys_result['message']}")
                status_updates.append({
                    'step': 'Secrets Manager',
                    'status': f'⚠️ API keys loading: {api_keys_result["message"]}',
                    'timestamp': datetime.now().isoformat()
                })
        else:
            app.logger.warning(f"⚠️ Secrets Manager setup: {secrets_result['message']}")
            status_updates.append({
                'step': 'Secrets Manager',
                'status': f'⚠️ Secrets Manager setup: {secrets_result["message"]}',
                'timestamp': datetime.now().isoformat()
            })
        
        # Get processing mode
        processing_mode = request.form.get('processing_mode', 'basic')
        
        # Validate file
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename or not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Save uploaded file locally first
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Get file extension
        file_ext = filename.rsplit('.', 1)[1].lower()
        
        # Initialize response data
        response_data = {
            'id': str(uuid.uuid4()),
            'file_id': unique_filename,
            'file_type': file_ext,
            'processing_mode': processing_mode,
            'processing_timestamp': datetime.now().isoformat(),
            'status_updates': status_updates,
            'aws_resources_created': False,
            'cleanup_available': False,
            'patient_data': {},
            'processing_time': 0,
            'api_gateway_status': api_gateway_result,
            's3_status': None,
            'cloudwatch_status': cloudwatch_result,
            'secrets_manager_status': secrets_result,
            'success': True
        }
        
        # Step 1: S3 Upload Integration
        app.logger.info("☁️ Starting S3 upload integration...")
        status_updates.append({
            'step': 'S3 Upload',
            'status': '☁️ Starting S3 upload integration...',
            'timestamp': datetime.now().isoformat()
        })
        
        # Upload file to S3
        s3_result = aws_service.upload_file_to_s3(filepath)
        if s3_result['success']:
            app.logger.info(f"✅ File uploaded to S3: {s3_result['bucket_name']}/{s3_result['s3_key']}")
            status_updates.append({
                'step': 'S3 Upload',
                'status': f'✅ File uploaded to S3: {s3_result["bucket_name"]}/{s3_result["s3_key"]}',
                'timestamp': datetime.now().isoformat()
            })
            response_data['s3_status'] = s3_result
            
            # Store initial processing record and convert ObjectId to string
            record_id = data_store.add_processing_record(copy.deepcopy(response_data))
            if record_id:
                response_data['record_id'] = str(record_id)
        else:
            app.logger.error(f"❌ S3 upload failed: {s3_result['error']}")
            status_updates.append({
                'step': 'S3 Upload',
                'status': f'❌ S3 upload failed: {s3_result["error"]}',
                'timestamp': datetime.now().isoformat()
            })
            response_data['s3_status'] = s3_result
            record_id = data_store.add_processing_record(copy.deepcopy(response_data))
            if record_id:
                response_data['record_id'] = str(record_id)
            return jsonify({
                'error': 'S3 upload failed',
                'details': s3_result['error']
            }), 500
        
        # Step 2: Process based on mode
        try:
            if processing_mode == 'basic':
                processing_result = process_basic_mode(filepath, file_ext, response_data)
            elif processing_mode == 'advanced':
                processing_result = process_advanced_mode(filepath, file_ext, response_data)
            else:  # image mode
                processing_result = process_image_mode(filepath, file_ext, response_data)
                
            # Update processing record with results
            response_data.update(processing_result)
            record_id = data_store.add_processing_record(copy.deepcopy(response_data))
            if record_id:
                response_data['record_id'] = str(record_id)
        except Exception as e:
            app.logger.error(f"❌ Processing failed: {str(e)}")
            response_data['success'] = False
            response_data['error'] = str(e)
            record_id = data_store.add_processing_record(copy.deepcopy(response_data))
            if record_id:
                response_data['record_id'] = str(record_id)
            # Convert any ObjectIds to strings for JSON serialization
            response_data = data_store.convert_objectid_to_str(response_data)
            return jsonify(response_data), 500
        
        # Calculate processing time
        processing_time = time.time() - start_time
        response_data['processing_time'] = round(processing_time, 2)
        
        # Convert any ObjectIds to strings for JSON serialization
        response_data = data_store.convert_objectid_to_str(response_data)
        
        # Log successful API Gateway invocation
        aws_service.log_api_gateway_invocation('/api/upload', 'POST', 'COMPLETED')
        
        return jsonify(response_data)
            
    except Exception as e:
        app.logger.error(f"Upload error: {str(e)}")
        # Ensure patient_data is present in error response
        if 'patient_data' not in response_data:
            response_data['patient_data'] = {
                'patient_id': None,
                'name': None,
                'gender': None,
                'birth_date': None,
                'address': None,
                'phone': None,
                'medical_record_number': None,
                'medical_conditions': [],
                'medications': [],
                'phi_detected': []
            }
        # Log failed API Gateway invocation
        aws_service.log_api_gateway_invocation('/api/upload', 'POST', 'FAILED')
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

def process_basic_mode(filepath, file_ext, response_data):
    """Process file in basic mode - standard CDA to FHIR"""
    # Always define patient_data at the top
    patient_data = {
        'patient_id': None,
        'name': None,
        'gender': None,
        'birth_date': None,
        'address': None,
        'phone': None,
        'medical_record_number': None,
        'medical_conditions': [],
        'medications': [],
        'phi_detected': []
    }
    response_data['status_updates'].append({
        'step': 'Basic Processing',
        'status': 'Processing CDA document...',
        'timestamp': datetime.now().isoformat()
    })

    if file_ext in ['xml', 'cda']:
        # Process CDA document
        processor = CDAProcessor()
        processing_result = processor.process_cda_file(filepath)

        # Extract patient data
        patient_data = extract_patient_data(processing_result)
        response_data['patient_data'] = patient_data

        # Convert to FHIR
        converter = FHIRConverter()
        fhir_result = converter.convert_to_fhir(processing_result)

        response_data.update({
            'processing_result': processing_result,
            'fhir_result': fhir_result,
            'status_updates': response_data['status_updates'] + [{
                'step': 'Basic Processing',
                'status': 'Completed successfully',
                'timestamp': datetime.now().isoformat()
            }]
        })
    else:
        response_data.update({
            'message': 'File uploaded successfully (basic mode)',
            'status_updates': response_data['status_updates'] + [{
                'step': 'Basic Processing',
                'status': 'File uploaded (no processing needed)',
                'timestamp': datetime.now().isoformat()
            }]
        })
    # Always set patient_data in response_data
    response_data['patient_data'] = patient_data
    return response_data

def process_advanced_mode(filepath, file_ext, response_data):
    """Process file in advanced mode - AWS Comprehend Medical + Gemini (Bedrock)"""
    response_data['status_updates'].append({
        'step': 'Advanced Processing',
        'status': 'Initializing AWS services...',
        'timestamp': datetime.now().isoformat()
    })

    # Initialize patient_data to avoid scope issues
    patient_data = {
        'patient_id': None,
        'name': None,
        'gender': None,
        'birth_date': None,
        'address': None,
        'phone': None,
        'medical_record_number': None,
        'medical_conditions': [],
        'medications': [],
        'phi_detected': []
    }

    if file_ext in ['xml', 'cda']:
        # First, extract patient data using CDA processor
        response_data['status_updates'].append({
            'step': 'Advanced Processing',
            'status': 'Extracting patient data from CDA...',
            'timestamp': datetime.now().isoformat()
        })

        # Process CDA document first to get patient data
        processor = CDAProcessor()
        cda_result = processor.process_cda_file(filepath)

        # Extract patient data from CDA processing
        patient_data = extract_patient_data(cda_result)
        response_data['patient_data'] = patient_data

        # Advanced CDA processing with AWS service
        response_data['status_updates'].append({
            'step': 'Advanced Processing',
            'status': 'Processing with AWS Comprehend Medical...',
            'timestamp': datetime.now().isoformat()
        })
        
        # Add Comprehend Medical chatter
        response_data['status_updates'].append({
            'step': 'Comprehend Medical',
            'status': '🧠 Comprehend Medical: Analyzing medical text for entities...',
            'timestamp': datetime.now().isoformat()
        })
        
        response_data['status_updates'].append({
            'step': 'Lambda',
            'status': '⚡ Lambda: Invoking Comprehend Medical API...',
            'timestamp': datetime.now().isoformat()
        })

        result = aws_service.process_cda_advanced(filepath)
        if result['success']:
            # Add Comprehend Medical success chatter
            response_data['status_updates'].append({
                'step': 'Comprehend Medical',
                'status': '✅ Comprehend Medical: Medical entities extracted successfully',
                'timestamp': datetime.now().isoformat()
            })
            
            # Add Gemini AI chatter
            response_data['status_updates'].append({
                'step': 'Gemini (Bedrock)',
                'status': '🤖 Gemini AI: Processing medical insights with advanced AI...',
                'timestamp': datetime.now().isoformat()
            })
            
            response_data['status_updates'].append({
                'step': 'Lambda',
                'status': '⚡ Lambda: Invoking Gemini (Bedrock) AI for medical analysis...',
                'timestamp': datetime.now().isoformat()
            })
            
            # Merge patient data with comprehend results
            comprehend_results = result.get('comprehend_results', {})

            # Add any additional entities found by Comprehend
            if 'entities' in comprehend_results:
                for entity in comprehend_results['entities']:
                    category = entity.get('Category', '').lower()
                    text = entity.get('Text', '')
                    if 'condition' in category and text not in patient_data.get('medical_conditions', []):
                        if 'medical_conditions' not in patient_data:
                            patient_data['medical_conditions'] = []
                        patient_data['medical_conditions'].append(text)
                    elif 'medication' in category and text not in patient_data.get('medications', []):
                        if 'medications' not in patient_data:
                            patient_data['medications'] = []
                        patient_data['medications'].append(text)

            # Update patient data with merged results
            response_data['patient_data'] = patient_data
            
            # Add DynamoDB chatter
            response_data['status_updates'].append({
                'step': 'DynamoDB',
                'status': '📊 DynamoDB: Storing enhanced patient data and medical entities...',
                'timestamp': datetime.now().isoformat()
            })
            
            response_data['status_updates'].append({
                'step': 'Lambda',
                'status': '⚡ Lambda: DynamoDB write operation for patient data completed',
                'timestamp': datetime.now().isoformat()
            })

            response_data.update({
                'comprehend_results': comprehend_results,
                'gemini_results': result.get('gemini_results'),
                'fhir_resources': result.get('fhir_resources'),
                'aws_resources_created': True,
                'cleanup_available': True,
                'status_updates': response_data['status_updates'] + [{
                    'step': 'Advanced Processing',
                    'status': 'Completed with AWS services',
                'timestamp': datetime.now().isoformat()
                }]
            })
            
            # Add final success messages
            response_data['status_updates'].append({
                'step': 'Gemini (Bedrock)',
                'status': '✅ Gemini AI: Medical insights generated successfully',
                'timestamp': datetime.now().isoformat()
            })
            
            response_data['status_updates'].append({
                'step': 'Lambda',
                'status': '🎉 Lambda: Advanced processing orchestration completed successfully!',
                'timestamp': datetime.now().isoformat()
            })
        else:
            response_data['status_updates'].append({
                'step': 'Comprehend Medical',
                'status': f'❌ Comprehend Medical processing failed: {result["error"]}',
                'timestamp': datetime.now().isoformat()
            })
            
            response_data.update({
                'error': result['error'],
                'status_updates': response_data['status_updates'] + [{
                    'step': 'Advanced Processing',
                    'status': f'Failed: {result["error"]}',
                    'timestamp': datetime.now().isoformat()
                }]
            })
    else:
        response_data.update({
            'message': 'File uploaded successfully (advanced mode)',
            'status_updates': response_data['status_updates'] + [{
                'step': 'Advanced Processing',
                'status': 'File uploaded (no CDA processing needed)',
                'timestamp': datetime.now().isoformat()
            }]
        })
    
    # Always set patient_data in response_data
    response_data['patient_data'] = patient_data
    return response_data

def process_image_mode(filepath, file_ext, response_data):
    """Process medical image with Gemini (Bedrock) AI"""
    response_data['status_updates'].append({
        'step': 'Image Analysis',
        'status': 'Initializing Gemini (Bedrock) AI...',
        'timestamp': datetime.now().isoformat()
    })

    if file_ext in ['png', 'jpg', 'jpeg', 'gif']:
        # Medical image processing with Gemini (Bedrock) AI
        patient_mrn = request.form.get('patient_mrn', '12345')
        
        response_data['status_updates'].append({
            'step': 'Image Analysis',
            'status': 'Analyzing medical image with Gemini (Bedrock) AI...',
            'timestamp': datetime.now().isoformat()
        })
        
        # Add Gemini AI chatter
        response_data['status_updates'].append({
            'step': 'Gemini (Bedrock)',
            'status': '🤖 Gemini AI: Loading medical image for analysis...',
            'timestamp': datetime.now().isoformat()
        })
        
        response_data['status_updates'].append({
            'step': 'Lambda',
            'status': '⚡ Lambda: Invoking Gemini (Bedrock) AI for medical image processing...',
            'timestamp': datetime.now().isoformat()
        })

        result = aws_service.process_medical_image(filepath, patient_mrn)
        if result['success']:
            # Add Gemini AI success chatter
            response_data['status_updates'].append({
                'step': 'Gemini (Bedrock)',
                'status': '✅ Gemini AI: Medical image analysis completed successfully',
                'timestamp': datetime.now().isoformat()
            })
            
            # Add DynamoDB chatter
            response_data['status_updates'].append({
                'step': 'DynamoDB',
                'status': '📊 DynamoDB: Storing medical image analysis results...',
                'timestamp': datetime.now().isoformat()
            })
            
            response_data['status_updates'].append({
                'step': 'Lambda',
                'status': '⚡ Lambda: DynamoDB write operation for image analysis completed',
                'timestamp': datetime.now().isoformat()
            })
            
            # Create patient data for image analysis
            patient_data = {
                'mrn': patient_mrn,
                'image_analysis': True,
                'fhir_observation': result.get('fhir_observation')
            }
            response_data['patient_data'] = patient_data

            response_data.update({
                'fhir_observation': result.get('fhir_observation'),
                'patient_mrn': result.get('patient_mrn'),
                'aws_resources_created': True,
                'cleanup_available': True,
                'status_updates': response_data['status_updates'] + [{
                    'step': 'Image Analysis',
                    'status': 'Completed with Gemini (Bedrock) AI',
                    'timestamp': datetime.now().isoformat()
                }]
            })
            
            # Add final success messages
            response_data['status_updates'].append({
                'step': 'Lambda',
                'status': '🎉 Lambda: Medical image processing orchestration completed successfully!',
                'timestamp': datetime.now().isoformat()
            })
        else:
            response_data['status_updates'].append({
                'step': 'Gemini (Bedrock)',
                'status': f'❌ Gemini AI processing failed: {result["error"]}',
                'timestamp': datetime.now().isoformat()
            })
            
            response_data.update({
                'error': result['error'],
                'status_updates': response_data['status_updates'] + [{
                    'step': 'Image Analysis',
                    'status': f'Failed: {result["error"]}',
                    'timestamp': datetime.now().isoformat()
                }]
            })
    else:
        response_data.update({
            'error': 'File must be an image (PNG, JPG, JPEG, GIF) for image analysis mode',
            'status_updates': response_data['status_updates'] + [{
                'step': 'Image Analysis',
                'status': 'Invalid file type for image analysis',
                'timestamp': datetime.now().isoformat()
            }]
        })
    return response_data

@app.route('/api/test-mongo')
def test_mongo():
    """Test MongoDB connection"""
    try:
        # Test connection
        data_store.client.admin.command('ping')
        # Get analytics collection info
        analytics_info = {
            'collection': str(data_store.analytics_col),
            'count': data_store.analytics_col.count_documents({})
        }
        return jsonify({
            'mongo_connection': 'success',
            'analytics_info': analytics_info
        })
    except Exception as e:
        return jsonify({
            'mongo_connection': 'failed',
            'error': str(e)
        }), 500

@app.route('/api/analytics')
def get_analytics():
    """Get analytics data from MongoDB"""
    try:
        # Get real analytics from data store
        analytics = data_store.get_analytics()
        app.logger.info(f"📈 Analytics loaded: {analytics}")
        
        # Extract PII analysis from analytics or get separately
        pii_analysis_raw = analytics.get('pii_analysis') or data_store.get_pii_analysis()
        app.logger.info(f"🔒 PII analysis raw: {pii_analysis_raw}")
        pii_analysis = {
            'total_phi': pii_analysis_raw.get('total_phi', 0),
            'unique_patients': pii_analysis_raw.get('unique_patients', 0),
            'phi_types': pii_analysis_raw.get('phi_types', []),
            'phi_breakdown': pii_analysis_raw.get('phi_breakdown', {})
        }
        
        # Extract medical insights from analytics or get separately
        medical_insights_raw = analytics.get('medical_insights') or data_store.get_medical_insights()
        app.logger.info(f"💊 Medical insights raw: {medical_insights_raw}")
        
        # Map medical insights to expected format
        medical_insights = {
            'top_conditions': medical_insights_raw.get('top_conditions', []),
            'top_medications': medical_insights_raw.get('top_medications', []),
            'total_conditions': len(medical_insights_raw.get('top_conditions', [])),
            'total_medications': len(medical_insights_raw.get('top_medications', []))
        }
        
        return jsonify({
            'analytics': analytics,
            'pii_analysis': pii_analysis,
            'medical_insights': medical_insights
        })
        
    except Exception as e:
        app.logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({'error': str(e)}), 500


def extract_patient_data(processing_result):
    
    # Extract from processing result
    if 'patient' in processing_result:
        patient = processing_result['patient']
        # Map patient_id to mrn, with fallbacks
        patient_data['mrn'] = (
            patient.get('patient_id') or 
            patient.get('medical_record_number') or 
            patient.get('mrn', 'unknown')
        )
        patient_data['name'] = patient.get('name', 'Unknown')
        patient_data['dob'] = patient.get('birth_date', 'Unknown')
        patient_data['gender'] = patient.get('gender', 'Unknown')
    
    # Extract medical conditions from clinical data
    if 'clinical_data' in processing_result:
        clinical = processing_result['clinical_data']
        if 'conditions' in clinical:
            for condition in clinical['conditions']:
                if isinstance(condition, dict):
                    condition_name = condition.get('display_name', condition.get('name', str(condition)))
                    if condition_name:
                        patient_data['medical_conditions'].append(condition_name)
        else:
                    patient_data['medical_conditions'].append(str(condition))
    
    # Extract medications
    if 'medications' in processing_result:
        medications = processing_result['medications']
        for medication in medications:
            if isinstance(medication, dict):
                med_name = medication.get('name', str(medication))
                if med_name:
                    patient_data['medications'].append(med_name)
        else:
                patient_data['medications'].append(str(medication))
    
    return patient_data

def extract_patient_data_from_comprehend(comprehend_results):
    """Extract patient data from AWS Comprehend results"""
    patient_data = {
        'mrn': 'unknown',
        'medical_conditions': [],
        'medications': [],
        'phi_detected': []
    }
    
    # Extract entities
    entities = comprehend_results.get('entities', [])
    for entity in entities:
        category = entity.get('Category', '').lower()
        text = entity.get('Text', '')
        
        if 'condition' in category:
            patient_data['medical_conditions'].append(text)
        elif 'medication' in category:
            patient_data['medications'].append(text)
    
    # Extract PHI
    phi = comprehend_results.get('phi', [])
    for phi_item in phi:
        patient_data['phi_detected'].append({
            'text': phi_item.get('Text', ''),
            'Category': phi_item.get('Category', ''),
            'Type': phi_item.get('Type', '')
        })
    
    return patient_data

@app.route('/api/cleanup-aws', methods=['POST'])
def cleanup_aws_resources():
    """Clean up AWS resources created during processing"""
    try:
        app.logger.info("🧹 Starting AWS cleanup process...")
        result = aws_service.cleanup_resources()
        app.logger.info(f"✅ AWS cleanup completed: {result}")
        
        response_data = {
            'success': result.get('success', False),
            'message': result.get('message', ''),
            'cleanup_results': result.get('cleanup_results', {}),
            'timestamp': result.get('timestamp', datetime.now().isoformat())
        }
        
        app.logger.info(f"📤 Sending cleanup response: {response_data}")
        return jsonify(response_data)
            
    except Exception as e:
        app.logger.error(f"❌ Cleanup error: {str(e)}")
        error_response = {
            'success': False, 
            'error': f'Cleanup failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }
        app.logger.error(f"📤 Sending cleanup error response: {error_response}")
        return jsonify(error_response), 500

@app.route('/api/service-status')
def get_service_status():
    """Get AWS service status"""
    try:
        status = aws_service.get_service_status()
        return jsonify(status)
    except Exception as e:
        app.logger.error(f"Status check error: {str(e)}")
        return jsonify({
            'available': False,
            'aws_configured': False,
            'services': {}
        })

@app.route('/api/dashboard-data')
def get_dashboard_data():
    """Get comprehensive dashboard data including AWS integration status"""
    try:
        # API Gateway Integration - Log invocation
        aws_service.log_api_gateway_invocation('/api/dashboard-data', 'GET', 'REQUESTED')
        
        app.logger.info("📊 Loading dashboard data...")
        
        # Get real analytics from data store
        analytics = data_store.get_analytics()
        app.logger.info(f"📈 Analytics loaded: {analytics}")
        
        # Extract PII analysis from analytics or get separately
        pii_analysis_raw = analytics.get('pii_analysis') or data_store.get_pii_analysis()
        app.logger.info(f"🔒 PII analysis raw: {pii_analysis_raw}")
        pii_analysis = {
            'total_phi': pii_analysis_raw.get('total_phi', 0),
            'unique_patients': pii_analysis_raw.get('unique_patients', 0),
            'phi_types': pii_analysis_raw.get('phi_types', []),
            'phi_breakdown': pii_analysis_raw.get('phi_breakdown', {})
        }
        
        # Extract medical insights from analytics or get separately
        medical_insights_raw = analytics.get('medical_insights') or data_store.get_medical_insights()
        app.logger.info(f"💊 Medical insights raw: {medical_insights_raw}")
        
        # Map medical insights to expected format
        medical_insights = {
            'top_conditions': medical_insights_raw.get('top_conditions', []),
            'top_medications': medical_insights_raw.get('top_medications', []),
            'total_conditions': len(medical_insights_raw.get('top_conditions', [])),
            'total_medications': len(medical_insights_raw.get('top_medications', []))
        }
        
        # Get patients as a dict (for dashboard compatibility)
        patients_data = data_store.get_all_patients()
        app.logger.info(f"👥 Patients data type: {type(patients_data)}, content: {patients_data}")
        
        # Extract patients from the returned structure
        if isinstance(patients_data, dict) and 'patients' in patients_data:
            patients = patients_data['patients']
        else:
            patients = patients_data
        
        # Ensure patients is a dict or list
        if not isinstance(patients, (dict, list)):
            app.logger.error(f"❌ Patients is not a dict or list! Type: {type(patients)}, Value: {patients}")
            patients = {}
        
        # Ensure all patients have the correct structure
        data_store.ensure_patient_structure()
        patients_data = data_store.get_all_patients()  # Get updated data
        
        # Extract patients from the returned structure again
        if isinstance(patients_data, dict) and 'patients' in patients_data:
            patients = patients_data['patients']
        else:
            patients = patients_data
        
        # Calculate PII analysis from actual patient data
        total_phi = 0
        phi_types = set()
        phi_breakdown = {'names': 0, 'phone_numbers': 0, 'addresses': 0, 'dates_of_birth': 0, 'medical_record_numbers': 0}
        
        # Handle both dict and list structures
        if isinstance(patients, dict):
            patient_items = patients.items()
        elif isinstance(patients, list):
            patient_items = [(i, patient) for i, patient in enumerate(patients)]
        else:
            patient_items = []
        
        for patient_id, patient_data in patient_items:
            # Check for phi_detected directly in patient_data (not nested)
            if 'phi_detected' in patient_data:
                phi_list = patient_data['phi_detected']
                if isinstance(phi_list, list):
                    total_phi += len(phi_list)
                    for phi_item in phi_list:
                        if isinstance(phi_item, dict):
                            phi_type = phi_item.get('Type', '').upper()
                            phi_types.add(phi_type)
                            if 'NAME' in phi_type:
                                phi_breakdown['names'] += 1
                            elif 'PHONE' in phi_type:
                                phi_breakdown['phone_numbers'] += 1
                            elif 'ADDRESS' in phi_type:
                                phi_breakdown['addresses'] += 1
                            elif 'DATE' in phi_type:
                                phi_breakdown['dates_of_birth'] += 1
                            elif 'RECORD' in phi_type or 'MRN' in phi_type:
                                phi_breakdown['medical_record_numbers'] += 1
            
            # Also check in nested patient_data if it exists
            if 'patient_data' in patient_data and isinstance(patient_data['patient_data'], dict):
                nested_patient = patient_data['patient_data']
                if 'phi_detected' in nested_patient:
                    phi_list = nested_patient['phi_detected']
                    if isinstance(phi_list, list):
                        total_phi += len(phi_list)
                        for phi_item in phi_list:
                            if isinstance(phi_item, dict):
                                phi_type = phi_item.get('Type', '').upper()
                                phi_types.add(phi_type)
                                if 'NAME' in phi_type:
                                    phi_breakdown['names'] += 1
                                elif 'PHONE' in phi_type:
                                    phi_breakdown['phone_numbers'] += 1
                                elif 'ADDRESS' in phi_type:
                                    phi_breakdown['addresses'] += 1
                                elif 'DATE' in phi_type:
                                    phi_breakdown['dates_of_birth'] += 1
                                elif 'RECORD' in phi_type or 'MRN' in phi_type:
                                    phi_breakdown['medical_record_numbers'] += 1
        
        # Update PII analysis with calculated values
        pii_analysis = {
            'total_phi': total_phi,
            'unique_patients': len(patients) if isinstance(patients, (dict, list)) else 0,
            'phi_types': list(phi_types),
            'phi_breakdown': phi_breakdown
        }
        
        # Calculate medical insights from actual patient data
        all_conditions = []
        all_medications = []
        
        for patient_id, patient_data in patient_items:
            # Check for medical_conditions directly in patient_data
            if 'medical_conditions' in patient_data:
                conditions = patient_data['medical_conditions']
                if isinstance(conditions, list):
                    all_conditions.extend(conditions)
            
            # Check for medications directly in patient_data
            if 'medications' in patient_data:
                medications = patient_data['medications']
                if isinstance(medications, list):
                    all_medications.extend(medications)
            
            # Also check in nested patient_data if it exists
            if 'patient_data' in patient_data and isinstance(patient_data['patient_data'], dict):
                nested_patient = patient_data['patient_data']
                
                if 'medical_conditions' in nested_patient:
                    conditions = nested_patient['medical_conditions']
                    if isinstance(conditions, list):
                        all_conditions.extend(conditions)
                
                if 'medications' in nested_patient:
                    medications = nested_patient['medications']
                    if isinstance(medications, list):
                        all_medications.extend(medications)
        
        # Count occurrences
        from collections import Counter
        condition_counts = Counter(all_conditions)
        medication_counts = Counter(all_medications)
        
        # Get top conditions and medications
        top_conditions = [(condition, count) for condition, count in condition_counts.most_common(5)]
        top_medications = [(medication, count) for medication, count in medication_counts.most_common(5)]
        
        # Update medical insights with calculated values
        medical_insights = {
            'top_conditions': top_conditions,
            'top_medications': top_medications,
            'total_conditions': len(all_conditions),
            'total_medications': len(all_medications)
        }
        
        # Calculate FHIR resources from actual patient data
        fhir_resources = {
            'patients': len(patients) if isinstance(patients, (dict, list)) else 0,
            'observations': len(patients) if isinstance(patients, (dict, list)) else 0,  # One observation per patient
            'conditions': len(all_conditions),
            'medication_requests': len(all_medications),
            'procedures': 0  # No procedure data in current structure
        }
        
        # Generate real processing timeline from processing history
        processing_history = data_store.get_processing_history(100)  # Get last 100 records
        timeline_data = {}
        
        for record in processing_history:
            if 'processing_timestamp' in record:
                try:
                    # Parse the timestamp
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(record['processing_timestamp'].replace('Z', '+00:00'))
                    date_key = timestamp.strftime('%Y-%m-%d')
                    
                    if date_key not in timeline_data:
                        timeline_data[date_key] = 0
                    timeline_data[date_key] += 1
                except Exception as e:
                    app.logger.warning(f"Could not parse timestamp: {record.get('processing_timestamp')} - {e}")
        
        # Convert to sorted list format for dashboard
        processing_timeline = []
        for date, count in sorted(timeline_data.items()):
            processing_timeline.append({
                'date': date,
                'documents': count
            })
        
        # Generate recent activity from processing history
        recent_activity = []
        for record in processing_history[:20]:  # Last 20 records
            if 'processing_timestamp' in record and 'file_id' in record:
                try:
                    from datetime import datetime
                    timestamp = datetime.fromisoformat(record['processing_timestamp'].replace('Z', '+00:00'))
                    
                    activity = {
                        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'action': f"Processed {record.get('file_type', 'document').upper()} Document",
                        'patient': f"Patient: {record.get('patient_data', {}).get('name', 'Unknown')}",
                        'status': 'success' if record.get('success', False) else 'failed',
                        'file_type': record.get('file_type', 'unknown'),
                        'processing_time': round(record.get('processing_time', 0), 2)
                    }
                    recent_activity.append(activity)
                except Exception as e:
                    app.logger.warning(f"Could not create activity from record: {e}")
        
        # Generate conversion success rate data
        conversion_success_rate = []
        if processing_history:
            # Group by month and calculate success rates
            monthly_data = {}
            for record in processing_history:
                if 'processing_timestamp' in record:
                    try:
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(record['processing_timestamp'].replace('Z', '+00:00'))
                        month_key = timestamp.strftime('%Y-%m')
                        
                        if month_key not in monthly_data:
                            monthly_data[month_key] = {'total': 0, 'success': 0}
                        
                        monthly_data[month_key]['total'] += 1
                        if record.get('success', False):
                            monthly_data[month_key]['success'] += 1
                    except Exception as e:
                        app.logger.warning(f"Could not parse timestamp for success rate: {e}")
            
            # Convert to dashboard format
            for month, data in sorted(monthly_data.items()):
                success_rate = (data['success'] / data['total'] * 100) if data['total'] > 0 else 0
                conversion_success_rate.append({
                    'month': datetime.strptime(month, '%Y-%m').strftime('%b'),
                    'success_rate': round(success_rate, 1)
                })
        
        dashboard_data = {
            'processing_stats': {
                'total_documents': analytics.get('total_documents', 0),
                'successful_conversions': analytics.get('successful_conversions', 0),
                'failed_conversions': analytics.get('failed_conversions', 0),
                'processing_time_avg': round(analytics.get('processing_time_avg', 0), 2),
                'conversion_success_rate': round((analytics.get('successful_conversions', 0) / max(analytics.get('total_documents', 1), 1)) * 100, 1)
            },
            'entity_extraction': {
                'medical_conditions': analytics.get('entity_extraction', {}).get('medical_conditions', 0),
                'medications': analytics.get('entity_extraction', {}).get('medications', 0),
                'procedures': analytics.get('entity_extraction', {}).get('procedures', 0),
                'lab_results': analytics.get('entity_extraction', {}).get('lab_results', 0),
                'phi_detected': analytics.get('entity_extraction', {}).get('phi_detected', 0)
            },
            'fhir_resources': fhir_resources,
            'processing_timeline': processing_timeline,
            'conversion_success_rate': conversion_success_rate,
            'recent_activity': recent_activity,
            'pii_analysis': pii_analysis,
            'medical_insights': medical_insights,
            'patients': patients
        }
        
        # Add API Gateway logs to dashboard data
        if hasattr(data_store, 'api_gateway_logs'):
            dashboard_data['api_gateway_logs'] = data_store.api_gateway_logs[-10:]  # Last 10 logs
        else:
            dashboard_data['api_gateway_logs'] = []
        
        # Add S3 logs to dashboard data
        if hasattr(data_store, 's3_logs'):
            dashboard_data['s3_logs'] = data_store.s3_logs[-10:]  # Last 10 logs
        else:
            dashboard_data['s3_logs'] = []
        
        # Add EventBridge logs to dashboard data
        if hasattr(data_store, 'eventbridge_logs'):
            dashboard_data['eventbridge_logs'] = data_store.eventbridge_logs[-10:]  # Last 10 logs
        else:
            dashboard_data['eventbridge_logs'] = []
        
        # Add Step Functions logs to dashboard data
        if hasattr(data_store, 'step_functions_logs'):
            dashboard_data['step_functions_logs'] = data_store.step_functions_logs[-10:]  # Last 10 logs
        else:
            dashboard_data['step_functions_logs'] = []
        
        # Add CloudWatch alarms to dashboard data
        if hasattr(data_store, 'cloudwatch_alarms'):
            dashboard_data['cloudwatch_alarms'] = data_store.cloudwatch_alarms[-10:]  # Last 10 alarms
        else:
            dashboard_data['cloudwatch_alarms'] = []
        
        # Add Secrets Manager logs to dashboard data
        if hasattr(data_store, 'secrets_manager_logs'):
            dashboard_data['secrets_manager_logs'] = data_store.secrets_manager_logs[-10:]  # Last 10 logs
        else:
            dashboard_data['secrets_manager_logs'] = []
        
        app.logger.info(f"✅ Dashboard data prepared successfully")
        
        # Log successful API Gateway invocation
        aws_service.log_api_gateway_invocation('/api/dashboard-data', 'GET', 'COMPLETED')
        
        return jsonify(dashboard_data)
        
    except Exception as e:
        app.logger.error(f"❌ Dashboard data error: {str(e)}")
        app.logger.error(f"❌ Error type: {type(e)}")
        import traceback
        app.logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        # Log failed API Gateway invocation
        aws_service.log_api_gateway_invocation('/api/dashboard-data', 'GET', 'FAILED')
        
        return jsonify({
            'error': f'Failed to get dashboard data: {str(e)}',
            'patients': {},
            'analytics': {},
            'processing_history': [],
            'api_gateway_logs': [],
            's3_logs': [],
            'eventbridge_logs': [],
            'step_functions_logs': [],
            'cloudwatch_alarms': [],
            'secrets_manager_logs': []
        }), 500

@app.route('/api/processing-history')
def get_processing_history():
    """Get real processing history"""
    try:
        limit = request.args.get('limit', 50, type=int)
        history = data_store.get_processing_history(limit)
        return jsonify(history)
    except Exception as e:
        app.logger.error(f"Processing history error: {str(e)}")
        return jsonify({'error': 'Failed to load processing history'}), 500

@app.route('/api/patient-details/<patient_id>')
def get_patient_details(patient_id):
    """Get detailed patient information"""
    try:
        patient_data = data_store.get_patient_details(patient_id)
        return jsonify(patient_data)
    except Exception as e:
        app.logger.error(f"Patient details error: {str(e)}")
        return jsonify({'error': 'Failed to load patient details'}), 500

@app.route('/api/file-preview/<file_id>')
def file_preview(file_id):
    """Get file preview information"""
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404
        
        file_stats = os.stat(filepath)
        file_info = {
            'filename': file_id,
            'size': file_stats.st_size,
            'modified': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
            'type': file_id.rsplit('.', 1)[1].lower() if '.' in file_id else 'unknown'
        }
        
        return jsonify(file_info)
        
    except Exception as e:
        app.logger.error(f"File preview error: {str(e)}")
        return jsonify({'error': 'Failed to get file preview'}), 500

@app.errorhandler(413)
def file_too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(404)
def not_found(e):
    return render_template('upload.html'), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f"Internal error: {str(e)}")
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/reset-database', methods=['POST'])
def reset_database():
    """Reset the database, cleanup AWS resources, and populate with fresh demo data"""
    try:
        app.logger.info("🔄 Starting database reset process...")
        
        # Cleanup AWS resources first
        app.logger.info("🧹 Cleaning up AWS resources...")
        cleanup_result = aws_service.cleanup_resources()
        app.logger.info(f"✅ AWS cleanup result: {cleanup_result}")
        
        # Clear all data using MongoDB store's reset method
        app.logger.info("🗑️ Clearing existing data...")
        data_store.reset_database()
        
        # Populate dashboard with comprehensive test data
        app.logger.info("📊 Populating dashboard with demo data...")
        populate_dashboard_data()
        
        app.logger.info("✅ Database reset completed successfully with 50 comprehensive records")
        
        response_data = {
            'success': True,
            'message': 'Database reset, AWS resources cleaned up, and fresh demo data populated successfully',
            'cleanup_result': cleanup_result,
            'timestamp': datetime.now().isoformat()
        }
        
        app.logger.info(f"📤 Sending response: {response_data}")
        return jsonify(response_data)
    
    except Exception as e:
        app.logger.error(f"❌ Database reset error: {str(e)}")
        error_response = {
            'success': False, 
            'error': f'Database reset failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }
        app.logger.error(f"📤 Sending error response: {error_response}")
        return jsonify(error_response), 500

def populate_dashboard_data():
    """Populate dashboard with comprehensive test data - 50 detailed records with aggressive testing"""
    import random
    from datetime import datetime, timedelta
    
    # Comprehensive patient data
    patient_names = [
        ('John Smith', 'M', '1985-03-15'), ('Mary Johnson', 'F', '1972-08-22'), ('Robert Wilson', 'M', '1968-11-07'),
        ('Sarah Davis', 'F', '1990-04-12'), ('Michael Brown', 'M', '1982-09-30'), ('Lisa Anderson', 'F', '1975-12-18'),
        ('David Miller', 'M', '1965-06-25'), ('Jennifer Taylor', 'F', '1988-01-14'), ('James Garcia', 'M', '1979-07-03'),
        ('Amanda Martinez', 'F', '1992-10-08'), ('Christopher Lee', 'M', '1987-05-20'), ('Jessica White', 'F', '1980-02-28'),
        ('Daniel Rodriguez', 'M', '1973-12-05'), ('Ashley Thompson', 'F', '1986-08-17'), ('Matthew Harris', 'M', '1971-04-09'),
        ('Emily Clark', 'F', '1995-11-23'), ('Joshua Lewis', 'M', '1984-07-31'), ('Samantha Walker', 'F', '1977-09-14'),
        ('Andrew Hall', 'M', '1969-03-26'), ('Nicole Young', 'F', '1989-06-11'), ('Ryan Allen', 'M', '1981-12-03'),
        ('Stephanie King', 'F', '1974-05-19'), ('Kevin Wright', 'M', '1983-10-27'), ('Rachel Green', 'F', '1991-01-08'),
        ('Brian Scott', 'M', '1976-08-15'), ('Lauren Baker', 'F', '1988-04-22'), ('Steven Adams', 'M', '1967-11-30'),
        ('Megan Nelson', 'F', '1993-07-05'), ('Timothy Carter', 'M', '1980-02-14'), ('Heather Mitchell', 'F', '1978-12-09'),
        ('Jason Perez', 'M', '1986-06-18'), ('Rebecca Roberts', 'F', '1972-09-25'), ('Eric Turner', 'M', '1985-01-12'),
        ('Michelle Phillips', 'F', '1990-03-28'), ('Mark Campbell', 'M', '1979-10-16'), ('Laura Parker', 'F', '1987-12-07'),
        ('Thomas Evans', 'M', '1974-04-03'), ('Christine Edwards', 'F', '1992-08-21'), ('Donald Collins', 'M', '1968-05-29'),
        ('Kimberly Stewart', 'F', '1983-11-13'), ('Ronald Sanchez', 'M', '1976-07-02'), ('Angela Morris', 'F', '1989-02-19'),
        ('Kenneth Rogers', 'M', '1981-06-24'), ('Melissa Reed', 'F', '1975-01-31'), ('Edward Cook', 'M', '1984-09-11'),
        ('Deborah Morgan', 'F', '1994-12-04'), ('Ronald Bell', 'M', '1970-03-17'), ('Diane Murphy', 'F', '1988-05-26'),
        ('George Bailey', 'M', '1977-10-08'), ('Virginia Cooper', 'F', '1991-07-15'), ('Frank Richardson', 'M', '1986-04-30'),
        ('Carol Cox', 'F', '1973-08-22'), ('Raymond Ward', 'M', '1982-12-14'), ('Ruth Torres', 'F', '1995-06-03')
    ]
    
    # Comprehensive medical conditions with ICD-10 codes
    medical_conditions = [
        {'name': 'Hypertension', 'icd10': 'I10', 'severity': 'moderate'},
        {'name': 'Type 2 Diabetes', 'icd10': 'E11.9', 'severity': 'moderate'},
        {'name': 'Asthma', 'icd10': 'J45.909', 'severity': 'mild'},
        {'name': 'Coronary Artery Disease', 'icd10': 'I25.10', 'severity': 'severe'},
        {'name': 'Major Depressive Disorder', 'icd10': 'F32.9', 'severity': 'moderate'},
        {'name': 'COPD', 'icd10': 'J44.9', 'severity': 'moderate'},
        {'name': 'Migraine', 'icd10': 'G43.909', 'severity': 'mild'},
        {'name': 'Generalized Anxiety Disorder', 'icd10': 'F41.1', 'severity': 'moderate'},
        {'name': 'Osteoarthritis', 'icd10': 'M19.90', 'severity': 'moderate'},
        {'name': 'Chronic Kidney Disease', 'icd10': 'N18.9', 'severity': 'moderate'},
        {'name': 'Heart Failure', 'icd10': 'I50.9', 'severity': 'severe'},
        {'name': 'Atrial Fibrillation', 'icd10': 'I48.91', 'severity': 'moderate'},
        {'name': 'Pneumonia', 'icd10': 'J18.9', 'severity': 'moderate'},
        {'name': 'Urinary Tract Infection', 'icd10': 'N39.0', 'severity': 'mild'},
        {'name': 'Gastroesophageal Reflux Disease', 'icd10': 'K21.9', 'severity': 'mild'},
        {'name': 'Hypothyroidism', 'icd10': 'E03.9', 'severity': 'mild'},
        {'name': 'Hyperlipidemia', 'icd10': 'E78.5', 'severity': 'mild'},
        {'name': 'Obesity', 'icd10': 'E66.9', 'severity': 'moderate'},
        {'name': 'Sleep Apnea', 'icd10': 'G47.33', 'severity': 'moderate'},
        {'name': 'Peripheral Neuropathy', 'icd10': 'G60.9', 'severity': 'moderate'}
    ]
    
    # Comprehensive medications with dosages
    medications = [
        {'name': 'Lisinopril', 'dosage': '10mg', 'frequency': 'daily', 'category': 'ACE Inhibitor'},
        {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'twice daily', 'category': 'Antidiabetic'},
        {'name': 'Atorvastatin', 'dosage': '20mg', 'frequency': 'daily', 'category': 'Statin'},
        {'name': 'Aspirin', 'dosage': '81mg', 'frequency': 'daily', 'category': 'Antiplatelet'},
        {'name': 'Amlodipine', 'dosage': '5mg', 'frequency': 'daily', 'category': 'Calcium Channel Blocker'},
        {'name': 'Losartan', 'dosage': '50mg', 'frequency': 'daily', 'category': 'ARB'},
        {'name': 'Metoprolol', 'dosage': '25mg', 'frequency': 'twice daily', 'category': 'Beta Blocker'},
        {'name': 'Furosemide', 'dosage': '20mg', 'frequency': 'daily', 'category': 'Diuretic'},
        {'name': 'Warfarin', 'dosage': '5mg', 'frequency': 'daily', 'category': 'Anticoagulant'},
        {'name': 'Insulin Glargine', 'dosage': '10 units', 'frequency': 'daily', 'category': 'Insulin'},
        {'name': 'Omeprazole', 'dosage': '20mg', 'frequency': 'daily', 'category': 'PPI'},
        {'name': 'Levothyroxine', 'dosage': '50mcg', 'frequency': 'daily', 'category': 'Thyroid Hormone'},
        {'name': 'Albuterol', 'dosage': '90mcg', 'frequency': 'as needed', 'category': 'Bronchodilator'},
        {'name': 'Sertraline', 'dosage': '50mg', 'frequency': 'daily', 'category': 'SSRI'},
        {'name': 'Ibuprofen', 'dosage': '400mg', 'frequency': 'as needed', 'category': 'NSAID'},
        {'name': 'Acetaminophen', 'dosage': '500mg', 'frequency': 'as needed', 'category': 'Analgesic'},
        {'name': 'Docusate', 'dosage': '100mg', 'frequency': 'daily', 'category': 'Stool Softener'},
        {'name': 'Calcium Carbonate', 'dosage': '500mg', 'frequency': 'twice daily', 'category': 'Calcium Supplement'},
        {'name': 'Vitamin D3', 'dosage': '1000 IU', 'frequency': 'daily', 'category': 'Vitamin Supplement'}
    ]
    
    # File types and processing modes
    file_types = ['xml', 'cda', 'jpg', 'png', 'pdf', 'txt']
    processing_modes = ['basic', 'advanced', 'image']
    
    # Generate 50 comprehensive processing records
    for i in range(50):
        # Select patient data
        name, gender, dob = random.choice(patient_names)
        mrn = f"MRN{random.randint(10000, 99999)}"
        
        # Select processing mode and file type
        processing_mode = random.choice(processing_modes)
        file_type = random.choice(file_types)
        
        # Generate realistic processing time based on mode
        if processing_mode == 'basic':
            processing_time = round(random.uniform(1.2, 3.5), 2)
        elif processing_mode == 'advanced':
            processing_time = round(random.uniform(4.0, 8.5), 2)
        else:  # image
            processing_time = round(random.uniform(2.5, 6.0), 2)
        
        # Generate timestamp within last 30 days
        timestamp = datetime.now() - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        
        # Generate patient conditions and medications
        patient_conditions = random.sample(medical_conditions, random.randint(1, 4))
        patient_medications = random.sample(medications, random.randint(2, 6))
        
        # Generate comprehensive FHIR resources
        fhir_resources = []
        fhir_resources.append({
            'resourceType': 'Patient',
            'id': mrn,
            'identifier': [{'system': 'http://hospital.example.org/identifiers/patient', 'value': mrn}],
            'name': [{'text': name}],
            'gender': gender.lower(),
            'birthDate': dob,
            'address': [{
                'text': f'{random.randint(100, 9999)} Main St, City, State {random.randint(10000, 99999)}'
            }]
        })
        
        # Add conditions
        for condition in patient_conditions:
            fhir_resources.append({
                'resourceType': 'Condition',
                'id': f'condition-{mrn}-{condition["icd10"]}',
                'subject': {'reference': f'Patient/{mrn}'},
                'code': {
                    'coding': [{
                        'system': 'http://hl7.org/fhir/sid/icd-10-cm',
                        'code': condition['icd10'],
                        'display': condition['name']
                    }]
                },
                'severity': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/condition-severity',
                        'code': condition['severity'],
                        'display': condition['severity'].title()
                    }]
                }
            })
        
        # Add medications
        for med in patient_medications:
            fhir_resources.append({
                'resourceType': 'MedicationRequest',
                'id': f'med-{mrn}-{med["name"].lower().replace(" ", "-")}',
                'subject': {'reference': f'Patient/{mrn}'},
                'medicationCodeableConcept': {
                    'coding': [{
                        'system': 'http://www.nlm.nih.gov/research/umls/rxnorm',
                        'display': med['name']
                    }]
                },
                'dosageInstruction': [{
                    'text': f'{med["dosage"]} {med["frequency"]}',
                    'timing': {'repeat': {'frequency': 1, 'period': 1, 'periodUnit': 'd'}}
                }]
            })
        
        # Add observations
        fhir_resources.append({
            'resourceType': 'Observation',
            'id': f'obs-{mrn}-vitals',
            'subject': {'reference': f'Patient/{mrn}'},
            'code': {
                'coding': [{
                    'system': 'http://loinc.org',
                    'code': '85354-9',
                    'display': 'Blood pressure panel'
                }]
            },
            'component': [
                {
                    'code': {'coding': [{'system': 'http://loinc.org', 'code': '8480-6', 'display': 'Systolic blood pressure'}]},
                    'valueQuantity': {'value': random.randint(110, 160), 'unit': 'mmHg'}
                },
                {
                    'code': {'coding': [{'system': 'http://loinc.org', 'code': '8462-4', 'display': 'Diastolic blood pressure'}]},
                    'valueQuantity': {'value': random.randint(60, 100), 'unit': 'mmHg'}
                }
            ]
        })
        
        # Generate Comprehend Medical results for advanced mode
        comprehend_results = None
        if processing_mode == 'advanced':
            entities = []
            phi = []
            
            # Add medical entities
            for condition in patient_conditions:
                entities.append({
                    'Text': condition['name'],
                    'Category': 'MEDICAL_CONDITION',
                    'Type': 'DIAGNOSIS',
                    'Score': round(random.uniform(0.85, 0.99), 3)
                })
            
            for med in patient_medications:
                entities.append({
                    'Text': med['name'],
                    'Category': 'MEDICATION',
                    'Type': 'GENERIC_NAME',
                    'Score': round(random.uniform(0.80, 0.95), 3)
                })
            
            # Add PII
            phi.append({
                'Text': name,
                'Category': 'PERSON',
                'Type': 'NAME',
                'Score': round(random.uniform(0.90, 0.99), 3)
            })
            
            phi.append({
                'Text': f'555-{random.randint(100,999)}-{random.randint(1000,9999)}',
                'Category': 'PHONE',
                'Type': 'PHONE_NUMBER',
                'Score': round(random.uniform(0.85, 0.95), 3)
            })
            
            comprehend_results = {
                'entities': entities,
                'phi': phi,
                'icd10_entities': [{'Text': condition['icd10'], 'Category': 'MEDICAL_CONDITION'} for condition in patient_conditions],
                'rxnorm_entities': [{'Text': med['name'], 'Category': 'MEDICATION'} for med in patient_medications]
            }
        
        # Generate Gemini AI results for advanced mode
        gemini_results = None
        if processing_mode == 'advanced':
            gemini_results = {
                'summary': f'Comprehensive analysis of {name}\'s medical record reveals {len(patient_conditions)} active conditions and {len(patient_medications)} prescribed medications. Patient shows {random.choice(["stable", "improving", "declining"])} health status.',
                'insights': [
                    f'Primary diagnosis: {patient_conditions[0]["name"]}',
                    f'Key medication: {patient_medications[0]["name"]} for {patient_medications[0]["category"]}',
                    f'Risk factors: {random.choice(["Hypertension", "Diabetes", "Smoking", "Obesity", "Family History"])}',
                    f'Recommended follow-up: {random.choice(["3 months", "6 months", "1 year"])}'
                ],
                'confidence_score': round(random.uniform(0.75, 0.95), 3)
            }
        
        # Generate image analysis results for image mode
        image_analysis = None
        if processing_mode == 'image':
            image_types = ['Chest X-Ray', 'Brain MRI', 'Abdominal CT', 'Echocardiogram', 'Mammogram']
            image_findings = [
                'Normal findings',
                'Pneumonia detected in right lower lobe',
                'Cardiomegaly with pulmonary congestion',
                'Pulmonary nodule, follow-up recommended',
                'Pleural effusion, moderate',
                'Atelectasis in left upper lobe',
                'Normal cardiac silhouette',
                'Mild interstitial lung disease'
            ]
            
            image_analysis = {
                'image_type': random.choice(image_types),
                'findings': random.choice(image_findings),
                'confidence': round(random.uniform(0.80, 0.98), 3),
                'recommendations': random.choice([
                    'No immediate action required',
                    'Follow-up imaging in 6 months',
                    'Consult with radiologist',
                    'Immediate clinical correlation needed'
                ])
            }
        
        # Create comprehensive record
        record = {
            'id': f"proc_{i+1:03d}",
            'file_id': f"file_{i+1:03d}.{file_type}",
            'file_type': file_type,
            'processing_mode': processing_mode,
            'processing_timestamp': timestamp.isoformat(),
            'status': 'completed',
            'success': True,
            'processing_time': processing_time,
            'aws_resources_created': random.choice([True, False]),
            'cleanup_available': True,
            'patient_data': {
                'mrn': mrn,
                'name': name,
                'dob': dob,
                'gender': gender,
                'medical_conditions': [c['name'] for c in patient_conditions],
                'medications': [m['name'] for m in patient_medications],
                'phi_detected': [
                    {'text': name, 'Category': 'PERSON', 'Type': 'NAME'},
                    {'text': f'555-{random.randint(100,999)}-{random.randint(1000,9999)}', 'Category': 'PHONE', 'Type': 'PHONE_NUMBER'}
                ]
            },
            'fhir_resources': fhir_resources,
            'fhir_resources_created': len(fhir_resources),
            'entities_extracted': len(patient_conditions) + len(patient_medications),
            'comprehend_results': comprehend_results,
            'gemini_results': gemini_results,
            'image_analysis': image_analysis
        }
        
        # Add to data store
        data_store.add_processing_record(record)
    
    # Initialize analytics collection
    analytics = data_store.get_initial_analytics()
    
    # Update analytics with comprehensive test data
    analytics.update({
        'total_documents': 50,
        'successful_conversions': 47,  # 94% success rate
        'failed_conversions': 3,
        'processing_time_avg': 4.2,
        'entity_extraction': {
            'total': 580,
            'medical_conditions': 125,
            'medications': 200,
            'procedures': 45,
            'lab_results': 80,
            'phi_detected': 130
        },
        'fhir_resources': {
            'total': 480,
            'patients': 50,
            'observations': 50,
            'conditions': 125,
            'medication_requests': 200,
            'procedures': 25
        },
        'processing_timeline': [],
        'conversion_success_rate': [
            {'month': 'Jan', 'success_rate': 92.5},
            {'month': 'Feb', 'success_rate': 94.2},
            {'month': 'Mar', 'success_rate': 91.8},
            {'month': 'Apr', 'success_rate': 95.1},
            {'month': 'May', 'success_rate': 93.7},
            {'month': 'Jun', 'success_rate': 94.0}
        ],
        'recent_activity': []
    })
    
    # Processing timeline (last 30 days)
    for i in range(30):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        documents = random.randint(0, 3) if i < 10 else 0  # Recent activity
        if documents > 0:
            analytics['processing_timeline'].append({'date': date, 'documents': documents})
    
    # Recent activity
    for i in range(20):
        activity = {
            'timestamp': (datetime.now() - timedelta(minutes=i*15)).strftime('%Y-%m-%d %H:%M:%S'),
            'action': random.choice(['Processed CDA Document', 'Analyzed Medical Image', 'Converted to FHIR', 'Extracted PII', 'Generated AI Insights']),
            'patient': f"Patient ID: MRN{random.randint(10000, 99999)}",
            'status': 'success',
            'file_type': random.choice(['xml', 'cda', 'jpg', 'png']),
            'processing_time': round(random.uniform(1.5, 8.0), 2)
        }
        analytics['recent_activity'].append(activity)
    
    # Add comprehensive PII analysis
    pii_analysis = {
        'total_phi': 130,
        'unique_patients': 50,
        'phi_types': ['NAME', 'PHONE_NUMBER', 'ADDRESS', 'DATE_OF_BIRTH', 'MEDICAL_RECORD_NUMBER'],
        'phi_breakdown': {
            'names': 25,
            'phone_numbers': 15,
            'addresses': 8,
            'dates_of_birth': 50,
            'medical_record_numbers': 50
        },
        'compliance_status': 'HIPAA Compliant',
        'last_audit': datetime.now().strftime('%Y-%m-%d')
    }
    
    # Add comprehensive medical insights
    medical_insights = {
        'top_conditions': ['Hypertension', 'Type 2 Diabetes', 'Asthma', 'Coronary Artery Disease', 'Major Depressive Disorder'],
        'top_medications': ['Lisinopril', 'Metformin', 'Atorvastatin', 'Aspirin', 'Amlodipine'],
        'condition_trends': {
            'increasing': ['Hypertension', 'Type 2 Diabetes'],
            'stable': ['Asthma', 'COPD'],
            'decreasing': ['Acute Infections']
        },
        'medication_adherence': 87.5,
        'risk_factors': ['Hypertension', 'Diabetes', 'Smoking', 'Obesity', 'Family History'],
        'preventive_care': {
            'screening_rate': 78.3,
            'vaccination_rate': 92.1,
            'wellness_visits': 85.7
        }
    }
    
    try:
        # Update analytics using MongoDB store methods
        # First, get current analytics
        current_analytics = data_store.get_analytics()
        
        # Update with new data
        current_analytics.update(analytics)
        current_analytics['pii_analysis'] = pii_analysis
        current_analytics['medical_insights'] = medical_insights
        
        # Save updated analytics back to MongoDB
        if data_store.client and data_store.analytics is not None:
            data_store.analytics.replace_one({}, current_analytics, upsert=True)
        
        # Add processing records with analytics data to populate dashboard
        for i in range(50):
            # Generate patient data
            name, gender, dob = random.choice(patient_names)
            mrn = f"MRN{random.randint(10000, 99999)}"
            
            # Generate processing record with analytics data
            processing_record = {
                'file_id': f"demo_file_{i}.xml",
                'file_type': random.choice(['xml', 'cda', 'jpg', 'png', 'pdf', 'txt']),
                'processing_mode': random.choice(['basic', 'advanced', 'image']),
                'success': True,
                'processing_time': round(random.uniform(1.5, 8.0), 2),
                'timestamp': (datetime.now() - timedelta(minutes=i*2)).isoformat(),
                'patient_data': {
                    'mrn': mrn,
                    'name': name,
                    'gender': gender,
                    'dob': dob,
                    'medical_conditions': random.sample([c['name'] for c in medical_conditions], random.randint(1, 3)),
                    'medications': random.sample([m['name'] for m in medications], random.randint(1, 4)),
                    'phi_detected': random.sample(['NAME', 'PHONE_NUMBER', 'ADDRESS', 'DATE_OF_BIRTH'], random.randint(0, 3))
                },
                'comprehend_results': {
                    'entities': [
                        {'Category': 'MEDICAL_CONDITION', 'Text': random.choice([c['name'] for c in medical_conditions])},
                        {'Category': 'MEDICATION', 'Text': random.choice([m['name'] for m in medications])},
                        {'Category': 'PROCEDURE', 'Text': 'Blood Test'},
                        {'Category': 'TEST_RESULT', 'Text': 'Normal'}
                    ],
                    'phi': random.sample(['NAME', 'PHONE_NUMBER', 'ADDRESS', 'DATE_OF_BIRTH'], random.randint(0, 3))
                },
                'fhir_resources': [
                    {'resourceType': 'Patient', 'id': mrn},
                    {'resourceType': 'Condition', 'id': f'condition-{mrn}'},
                    {'resourceType': 'MedicationRequest', 'id': f'med-{mrn}'}
                ]
            }
            
            # Add the processing record
            data_store.add_processing_record(copy.deepcopy(processing_record))
        
        print("✅ Analytics collections updated successfully")
        print("✅ Processing records added with analytics data")
        
    except Exception as e:
        print(f"❌ Error updating MongoDB collections: {str(e)}")
        raise
    
    app.logger.info(f"✅ Database populated with 50 comprehensive records")
    app.logger.info(f"✅ Analytics updated with realistic healthcare data")
    app.logger.info(f"✅ PII analysis and medical insights generated")
    app.logger.info(f"✅ Patient database populated with detailed information")

@app.route('/api/cynthia-answer', methods=['POST'])
def cynthia_answer():
    data = request.json
    question = data.get('question', '')
    # Fetch context from data_store (all patients)
    patients = data_store.get_all_patients()
    num_patients = len(patients) if isinstance(patients, dict) else 0
    # Example: Find number of active transfers (simulate)
    active_transfers = 12  # Placeholder, replace with real logic if available
    critical_alerts = 3    # Placeholder, replace with real logic if available
    # Compose answer
    answer = f"I am Cynthia of MedFlowX. Based on the latest patient records, there are {num_patients} patients, {active_transfers} active transfers, and {critical_alerts} patients with critical alerts."
    # Optionally, add more context-aware logic here
    return jsonify({'answer': answer})

@app.route('/start_call', methods=['POST'])
def start_call():
    """
    Start a new voice call with Ultravox API for Cynthia, using real context from DynamoDB
    """
    try:
        if not ULTRAVOX_API_KEY:
            return jsonify({
                "error": "Ultravox API key is not configured. Please set the ULTRAVOX_API_KEY in config.py."
            }), 401
        # Fetch real context from data_store
        analytics = data_store.get_analytics()
        patients = data_store.get_all_patients()
        medical_insights = data_store.get_medical_insights()
        total_documents = analytics.get('total_documents', 0)
        unique_patients = len(patients) if isinstance(patients, dict) else 0
        top_conditions = medical_insights.get('top_conditions', [])
        top_medications = medical_insights.get('top_medications', [])
        # Format top conditions/medications as comma-separated
        top_conditions_str = ', '.join([c[0] if isinstance(c, (list, tuple)) else str(c) for c in top_conditions[:3]])
        top_medications_str = ', '.join([m[0] if isinstance(m, (list, tuple)) else str(m) for m in top_medications[:3]])
        # Build system prompt
        system_prompt = (
            f"You are Cynthia, the helpful voice assistant of MedFlowX. "
            f"There are currently {total_documents} documents and {unique_patients} unique patients in the system. "
            f"The most common conditions are: {top_conditions_str}. "
            f"The most prescribed medications are: {top_medications_str}. "
            f"Answer user questions using this context."
        )
        data = {
            "systemPrompt": system_prompt,
            "voice": "Cassidy-English",
            "selectedTools": [],
        }
        headers = {"X-API-Key": ULTRAVOX_API_KEY}
        response = requests.post(
            ULTRAVOX_API_URL + "/calls",
            json=data,
            headers=headers
        )
        if response.status_code == 201:
            call_details = response.json()
            return jsonify(call_details)
        else:
            try:
                response_json = response.json()
                api_detail = response_json.get('detail', '')
            except:
                api_detail = response.text if hasattr(response, 'text') else ''
            error_message = f"Ultravox API error: {response.status_code} - {api_detail}"
            return jsonify({"error": error_message}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ultravox-voices', methods=['GET'])
def get_ultravox_voices():
    """
    Fetch the list of available voices from the Ultravox API
    """
    try:
        if not ULTRAVOX_API_KEY:
            return jsonify({"error": "Ultravox API key is not configured."}), 401
        response = requests.get(
            ULTRAVOX_API_URL + "/voices",
            headers={"X-API-Key": ULTRAVOX_API_KEY}
        )
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": f"Ultravox API error: {response.status_code} - {response.text}"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test-simple', methods=['GET'])
def test_simple():
    """Simple test endpoint without AWS services"""
    try:
        return jsonify({
            'success': True,
            'message': 'Simple test endpoint working',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
