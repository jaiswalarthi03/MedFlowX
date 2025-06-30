import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION

logger = logging.getLogger(__name__)

class AWSService:
    """Service layer for AWS healthcare processing functionality"""
    
    def __init__(self):
        self.demo = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize the AWS service instance"""
        try:
            # Set AWS credentials from config
            os.environ['AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
            os.environ['AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY
            os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
            
            from safe.hackathon_demo import HealthcareHackathonDemo
            self.demo = HealthcareHackathonDemo()
            logger.info("AWS healthcare service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AWS healthcare service: {e}")
            self.demo = None
    
    def is_available(self) -> bool:
        """Check if AWS healthcare service is available"""
        return self.demo is not None
    
    def process_cda_advanced(self, filepath: str) -> Dict[str, Any]:
        """Process CDA document with advanced AWS services"""
        if not self.is_available():
            return {
                'success': False,
                'error': 'Advanced processing not available'
            }
        
        try:
            # Read CDA content
            with open(filepath, 'r', encoding='utf-8') as f:
                cda_content = f.read()
            
            # Process with Comprehend Medical
            comprehend_results = self.demo.process_with_comprehend_medical(cda_content)
            
            # Process with Bedrock
            bedrock_results = self.demo.process_with_bedrock(cda_content)
            
            # Create comprehensive FHIR resources
            cda_data = {'content': cda_content, 'filepath': filepath}
            fhir_resources = self.demo.create_fhir_resources(cda_data, comprehend_results, {})
            
            return {
                'success': True,
                'comprehend_results': comprehend_results,
                'bedrock_results': bedrock_results,
                'fhir_resources': fhir_resources,
                'processing_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Advanced CDA processing error: {e}")
            return {
                'success': False,
                'error': f'Advanced processing failed: {str(e)}'
            }
    
    def process_medical_image(self, filepath: str, patient_mrn: str) -> Dict[str, Any]:
        """Process medical image with Bedrock AI"""
        if not self.is_available():
            return {
                'success': False,
                'error': 'Image processing not available'
            }
        
        try:
            # Process the image
            image_observation = self.demo.process_medical_image(filepath, patient_mrn)
            
            if image_observation:
                return {
                    'success': True,
                    'fhir_observation': image_observation,
                    'patient_mrn': patient_mrn,
                    'processing_timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Image processing failed'
                }
                
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            return {
                'success': False,
                'error': f'Image processing failed: {str(e)}'
            }
    
    def run_comprehensive_demo(self) -> Dict[str, Any]:
        """Run the comprehensive AWS healthcare demo"""
        if not self.is_available():
            return {
                'success': False,
                'error': 'Demo not available'
            }
        
        try:
            # Run the comprehensive demo
            success = self.demo.run_comprehensive_demo()
            
            if success:
                return {
                    'success': True,
                    'message': 'Comprehensive demo completed successfully',
                    'demo_type': 'aws_healthcare',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Demo execution failed'
                }
                
        except Exception as e:
            logger.error(f"Demo execution error: {e}")
            return {
                'success': False,
                'error': f'Demo failed: {str(e)}'
            }
    
    def cleanup_resources(self) -> Dict[str, Any]:
        """Clean up all AWS resources created during processing"""
        if not self.is_available():
            return {
                'success': False,
                'error': 'Service not available'
            }
        
        try:
            # Run the cleanup
            cleanup_results = self.demo.cleanup_resources()
            
            # Count successful cleanups
            successful_cleanups = sum(cleanup_results.values())
            total_resources = len(cleanup_results)
            
            return {
                'success': True,
                'message': f'AWS resources cleaned up successfully ({successful_cleanups}/{total_resources} resources deleted)',
                'cleanup_results': cleanup_results,
                'successful_cleanups': successful_cleanups,
                'total_resources': total_resources,
                'timestamp': datetime.now().isoformat()
            }
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return {
                'success': False,
                'error': f'Cleanup failed: {str(e)}'
            }
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get AWS service status and capabilities"""
        return {
            'available': self.is_available(),
            'aws_configured': self._check_aws_configuration(),
            'services': self._get_available_services()
        }
    
    def _check_aws_configuration(self) -> bool:
        """Check if AWS is properly configured"""
        try:
            import boto3
            # Try to create a simple client to test credentials
            sts = boto3.client('sts',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_REGION)
            sts.get_caller_identity()
            return True
        except Exception:
            return False
    
    def _get_available_services(self) -> Dict[str, bool]:
        """Get list of available AWS services"""
        services = {
            'comprehend_medical': False,
            'bedrock': False,
            'dynamodb': False,
            'lambda': False,
            'sqs': False,
            'sns': False
        }
        
        if not self.is_available():
            return services
        
        try:
            # Test each service
            self.demo.comprehend.list_entities_detection_jobs(MaxResults=1)
            services['comprehend_medical'] = True
        except:
            pass
        
        try:
            self.demo.bedrock.list_foundation_models()
            services['bedrock'] = True
        except:
            pass
        
        try:
            self.demo.dynamodb.list_tables()
            services['dynamodb'] = True
        except:
            pass
        
        try:
            self.demo.lambda_client.list_functions()
            services['lambda'] = True
        except:
            pass
        
        try:
            self.demo.sqs.list_queues()
            services['sqs'] = True
        except:
            pass
        
        try:
            self.demo.sns.list_topics()
            services['sns'] = True
        except:
            pass
        
        return services

# Global service instance
aws_service = AWSService() 