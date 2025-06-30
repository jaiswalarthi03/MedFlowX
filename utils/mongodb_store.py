import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import uuid
import logging

logger = logging.getLogger(__name__)

class MongoDBStore:
    """MongoDB-based data store for tracking processing history and analytics"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.processing_history = None
        self.patients = None
        self.analytics = None
        self.connect()
    
    def connect(self):
        """Connect to MongoDB"""
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
            from mongodb_config import (
                MONGODB_URI, MONGODB_DATABASE, 
                PROCESSING_HISTORY_COLLECTION, PATIENTS_COLLECTION, ANALYTICS_COLLECTION
            )
            
            self.client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
            
            # Test connection
            self.client.admin.command('ping')
            logger.info("✅ MongoDB connection successful")
            
            self.db = self.client[MONGODB_DATABASE]
            self.processing_history = self.db[PROCESSING_HISTORY_COLLECTION]
            self.patients = self.db[PATIENTS_COLLECTION]
            self.analytics = self.db[ANALYTICS_COLLECTION]
            
            # Initialize collections if they don't exist
            self.initialize_collections()
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            # Fallback to in-memory storage for development
            self.use_fallback_storage()
        except ImportError as e:
            logger.error(f"❌ MongoDB config not found: {e}")
            self.use_fallback_storage()
        except Exception as e:
            logger.error(f"❌ MongoDB initialization error: {e}")
            self.use_fallback_storage()
    
    def use_fallback_storage(self):
        """Use in-memory storage as fallback"""
        logger.warning("⚠️ Using in-memory storage as fallback")
        self.client = None
        self.db = None
        self.processing_history = []
        self.patients = {}
        self.analytics = self.get_initial_analytics()
    
    def initialize_collections(self):
        """Initialize collections with default data if empty"""
        try:
            # Initialize analytics if empty
            if self.analytics.count_documents({}) == 0:
                initial_analytics = self.get_initial_analytics()
                self.analytics.insert_one(initial_analytics)
                logger.info("✅ Analytics collection initialized")
            
            # Create indexes for better performance, specify names to avoid conflicts
            self.processing_history.create_index([("timestamp", -1)], name="timestamp_-1", background=True)
            self.processing_history.create_index([("file_id", 1)], name="file_id_1", background=True)
            self.patients.create_index([("mrn", 1)], name="mrn_1", background=True, unique=True)
            self.patients.create_index([("last_processed", -1)], name="last_processed_-1", background=True)
            
            logger.info("✅ MongoDB collections initialized with indexes")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize collections: {e}")
    
    def get_initial_analytics(self):
        """Get initial analytics structure"""
        return {
            'total_documents': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'processing_time_avg': 0,
            'entity_extraction': {
                'medical_conditions': 0,
                'medications': 0,
                'procedures': 0,
                'lab_results': 0,
                'phi_detected': 0
            },
            'fhir_resources': {
                'patients': 0,
                'observations': 0,
                'conditions': 0,
                'medication_requests': 0,
                'procedures': 0
            },
            'processing_timeline': [],
            'conversion_success_rate': [],
            'recent_activity': [],
            'last_updated': datetime.now().isoformat()
        }
    
    def add_processing_record(self, record: Dict[str, Any]):
        """Add a new processing record"""
        # Create a copy of the record to avoid modifying the original
        record_copy = record.copy()
        record_copy['id'] = str(uuid.uuid4())
        record_copy['timestamp'] = datetime.now().isoformat()
        
        # Remove any existing _id to avoid duplicate key errors
        if '_id' in record_copy:
            del record_copy['_id']
        
        try:
            if self.client:  # MongoDB mode
                # Add to processing history
                result = self.processing_history.insert_one(record_copy)
                
                # Update analytics
                self.update_analytics(record_copy)
                
                # Add patient data if available
                if 'patient_data' in record_copy:
                    self.add_patient_data(record_copy['patient_data'])
                
                logger.info(f"✅ Processing record added to MongoDB: {record_copy['id']}")
                return record_copy['id']
            else:  # Fallback mode
                self.processing_history.append(record_copy)
                self.update_analytics(record_copy)
                if 'patient_data' in record_copy:
                    self.add_patient_data(record_copy['patient_data'])
                logger.info(f"✅ Processing record added to fallback storage: {record_copy['id']}")
                return record_copy['id']
            
        except Exception as e:
            logger.error(f"❌ Failed to add processing record: {e}")
            return None
    
    def add_patient_data(self, patient_data: Dict[str, Any]):
        """Add or update patient data"""
        try:
            patient_id = patient_data.get('mrn', patient_data.get('id', 'unknown'))
            
            if self.client:  # MongoDB mode
                # Use upsert to create or update
                update_data = {
                    '$set': {
                        'last_processed': datetime.now().isoformat(),
                        'patient_data': patient_data
                    },
                    '$inc': {'processing_count': 1},
                    '$setOnInsert': {
                        'first_seen': datetime.now().isoformat(),
                        'phi_detected': [],
                        'medical_conditions': [],
                        'medications': []
                    }
                }
                
                self.patients.update_one(
                    {'mrn': patient_id},
                    update_data,
                    upsert=True
                )
                
                # Update arrays if new data is available
                if 'phi_detected' in patient_data:
                    phi_list = patient_data['phi_detected']
                    if isinstance(phi_list, list):
                        self.patients.update_one(
                            {'mrn': patient_id},
                            {'$addToSet': {'phi_detected': {'$each': phi_list}}}
                        )
                
                if 'medical_conditions' in patient_data:
                    conditions = patient_data['medical_conditions']
                    if isinstance(conditions, list):
                        condition_names = []
                        for condition in conditions:
                            if isinstance(condition, dict):
                                name = condition.get('name', condition.get('display_name', str(condition)))
                                if name:
                                    condition_names.append(name)
                            else:
                                condition_names.append(str(condition))
                        
                        if condition_names:
                            self.patients.update_one(
                                {'mrn': patient_id},
                                {'$addToSet': {'medical_conditions': {'$each': condition_names}}}
                            )
                
                if 'medications' in patient_data:
                    medications = patient_data['medications']
                    if isinstance(medications, list):
                        med_names = []
                        for medication in medications:
                            if isinstance(medication, dict):
                                name = medication.get('name', str(medication))
                                if name:
                                    med_names.append(name)
                            else:
                                med_names.append(str(medication))
                        
                        if med_names:
                            self.patients.update_one(
                                {'mrn': patient_id},
                                {'$addToSet': {'medications': {'$each': med_names}}}
                            )
            
            else:  # Fallback mode
                if patient_id not in self.patients:
                    self.patients[patient_id] = {
                        'first_seen': datetime.now().isoformat(),
                        'processing_count': 0,
                        'last_processed': None,
                        'phi_detected': [],
                        'medical_conditions': [],
                        'medications': []
                    }
                
                self.patients[patient_id]['processing_count'] += 1
                self.patients[patient_id]['last_processed'] = datetime.now().isoformat()
                
                # Add detected PII
                if 'phi_detected' in patient_data:
                    phi_list = patient_data['phi_detected']
                    if isinstance(phi_list, list):
                        self.patients[patient_id]['phi_detected'].extend(phi_list)
                
                # Add medical conditions
                if 'medical_conditions' in patient_data:
                    conditions = patient_data['medical_conditions']
                    if isinstance(conditions, list):
                        for condition in conditions:
                            if isinstance(condition, dict):
                                condition_name = condition.get('name', condition.get('display_name', str(condition)))
                                if condition_name and condition_name not in self.patients[patient_id]['medical_conditions']:
                                    self.patients[patient_id]['medical_conditions'].append(condition_name)
                            else:
                                condition_str = str(condition)
                                if condition_str and condition_str not in self.patients[patient_id]['medical_conditions']:
                                    self.patients[patient_id]['medical_conditions'].append(condition_str)
                
                # Add medications
                if 'medications' in patient_data:
                    medications = patient_data['medications']
                    if isinstance(medications, list):
                        for medication in medications:
                            if isinstance(medication, dict):
                                med_name = medication.get('name', str(medication))
                                if med_name and med_name not in self.patients[patient_id]['medications']:
                                    self.patients[patient_id]['medications'].append(med_name)
                            else:
                                med_str = str(medication)
                                if med_str and med_str not in self.patients[patient_id]['medications']:
                                    self.patients[patient_id]['medications'].append(med_str)
            
        except Exception as e:
            logger.error(f"❌ Failed to add patient data: {e}")
    
    def update_analytics(self, record: Dict[str, Any]):
        """Update analytics based on processing record"""
        try:
            if self.client:  # MongoDB mode
                # Get current analytics
                current_analytics = self.analytics.find_one({})
                if not current_analytics:
                    current_analytics = self.get_initial_analytics()
                
                # Update basic counts
                current_analytics['total_documents'] += 1
                
                if record.get('success', False):
                    current_analytics['successful_conversions'] += 1
                else:
                    current_analytics['failed_conversions'] += 1
                
                # Update processing time average
                processing_time = record.get('processing_time', 0)
                if processing_time > 0:
                    current_avg = current_analytics['processing_time_avg']
                    total_processed = current_analytics['successful_conversions'] + current_analytics['failed_conversions']
                    current_analytics['processing_time_avg'] = ((current_avg * (total_processed - 1)) + processing_time) / total_processed
                
                # Update entity extraction counts
                comprehend_results = record.get('comprehend_results')
                if comprehend_results is not None:
                    entities = comprehend_results.get('entities', [])
                    phi = comprehend_results.get('phi', [])
                    
                    for entity in entities:
                        category = entity.get('Category', '').lower()
                        if 'condition' in category:
                            current_analytics['entity_extraction']['medical_conditions'] += 1
                        elif 'medication' in category:
                            current_analytics['entity_extraction']['medications'] += 1
                        elif 'procedure' in category:
                            current_analytics['entity_extraction']['procedures'] += 1
                        elif 'test' in category or 'lab' in category:
                            current_analytics['entity_extraction']['lab_results'] += 1
                    
                    current_analytics['entity_extraction']['phi_detected'] += len(phi)
                
                # Update FHIR resource counts
                fhir_resources = record.get('fhir_resources', [])
                if fhir_resources:
                    for resource in fhir_resources:
                        resource_type = resource.get('resourceType', '').lower()
                        if resource_type in current_analytics['fhir_resources']:
                            current_analytics['fhir_resources'][resource_type] += 1
                
                # Update last updated timestamp
                current_analytics['last_updated'] = datetime.now().isoformat()
                
                # Save updated analytics
                self.analytics.replace_one({}, current_analytics, upsert=True)
            
            else:  # Fallback mode
                # Update basic counts
                self.analytics['total_documents'] += 1
                
                if record.get('success', False):
                    self.analytics['successful_conversions'] += 1
                else:
                    self.analytics['failed_conversions'] += 1
                
                # Update processing time average
                processing_time = record.get('processing_time', 0)
                if processing_time > 0:
                    current_avg = self.analytics['processing_time_avg']
                    total_processed = self.analytics['successful_conversions'] + self.analytics['failed_conversions']
                    self.analytics['processing_time_avg'] = ((current_avg * (total_processed - 1)) + processing_time) / total_processed
                
                # Update entity extraction counts
                comprehend_results = record.get('comprehend_results')
                if comprehend_results is not None:
                    entities = comprehend_results.get('entities', [])
                    phi = comprehend_results.get('phi', [])
                    
                    for entity in entities:
                        category = entity.get('Category', '').lower()
                        if 'condition' in category:
                            self.analytics['entity_extraction']['medical_conditions'] += 1
                        elif 'medication' in category:
                            self.analytics['entity_extraction']['medications'] += 1
                        elif 'procedure' in category:
                            self.analytics['entity_extraction']['procedures'] += 1
                        elif 'test' in category or 'lab' in category:
                            self.analytics['entity_extraction']['lab_results'] += 1
                    
                    self.analytics['entity_extraction']['phi_detected'] += len(phi)
                
                # Update FHIR resource counts
                fhir_resources = record.get('fhir_resources', [])
                if fhir_resources:
                    for resource in fhir_resources:
                        resource_type = resource.get('resourceType', '').lower()
                        if resource_type in self.analytics['fhir_resources']:
                            self.analytics['fhir_resources'][resource_type] += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to update analytics: {e}")
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get analytics data"""
        try:
            if self.client:  # MongoDB mode
                analytics = self.analytics.find_one({})
                if analytics:
                    return self.convert_objectid_to_str(analytics)
                else:
                    return self.get_initial_analytics()
            else:  # Fallback mode
                return self.analytics
        except Exception as e:
            logger.error(f"❌ Failed to get analytics: {e}")
            return self.get_initial_analytics()
    
    def get_processing_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get processing history"""
        try:
            if self.client:  # MongoDB mode
                cursor = self.processing_history.find().sort('timestamp', -1).limit(limit)
                documents = list(cursor)
                return self.convert_objectid_to_str(documents)
            else:  # Fallback mode
                return sorted(self.processing_history, key=lambda x: x.get('timestamp', ''), reverse=True)[:limit]
        except Exception as e:
            logger.error(f"❌ Failed to get processing history: {e}")
            return []
    
    def get_patient_details(self, patient_id: str) -> Dict[str, Any]:
        """Get patient details"""
        try:
            if self.client:  # MongoDB mode
                patient = self.patients.find_one({'mrn': patient_id})
                if patient:
                    return self.convert_objectid_to_str(patient)
                else:
                    return {}
            else:  # Fallback mode
                return self.patients.get(patient_id, {})
        except Exception as e:
            logger.error(f"❌ Failed to get patient details: {e}")
            return {}
    
    def get_pii_analysis(self) -> Dict[str, Any]:
        """Get PII analysis from analytics"""
        try:
            if self.client:  # MongoDB mode
                analytics = self.analytics.find_one({})
                if analytics and 'pii_analysis' in analytics:
                    return analytics['pii_analysis']
                else:
                    return self.get_default_pii_analysis()
            else:  # Fallback mode
                return self.analytics.get('pii_analysis', self.get_default_pii_analysis())
        except Exception as e:
            logger.error(f"❌ Failed to get PII analysis: {e}")
            return self.get_default_pii_analysis()
    
    def get_default_pii_analysis(self) -> Dict[str, Any]:
        """Get default PII analysis structure"""
        return {
            'total_phi': 0,
            'unique_patients': 0,
            'phi_types': ['NAME', 'PHONE_NUMBER', 'ADDRESS', 'DATE_OF_BIRTH', 'MEDICAL_RECORD_NUMBER'],
            'phi_breakdown': {
                'names': 0,
                'phone_numbers': 0,
                'addresses': 0,
                'dates_of_birth': 0,
                'medical_record_numbers': 0
            },
            'compliance_status': 'HIPAA Compliant',
            'last_audit': datetime.now().strftime('%Y-%m-%d')
        }
    
    def ensure_patient_structure(self):
        """Ensure all patients have the correct structure with processing_count"""
        try:
            if self.client:  # MongoDB mode
                # Update all patients to ensure they have the correct structure
                update_result = self.patients.update_many(
                    {},
                    {
                        '$setOnInsert': {
                            'processing_count': 1,
                            'first_seen': datetime.now().isoformat(),
                            'last_processed': datetime.now().isoformat(),
                            'phi_detected': [],
                            'medical_conditions': [],
                            'medications': []
                        }
                    },
                    upsert=False
                )
                
                # Update patients that don't have processing_count
                self.patients.update_many(
                    {'processing_count': {'$exists': False}},
                    {'$set': {'processing_count': 1}}
                )
                
                # Update patients that don't have first_seen
                self.patients.update_many(
                    {'first_seen': {'$exists': False}},
                    {'$set': {'first_seen': datetime.now().isoformat()}}
                )
                
                # Update patients that don't have last_processed
                self.patients.update_many(
                    {'last_processed': {'$exists': False}},
                    {'$set': {'last_processed': datetime.now().isoformat()}}
                )
                
                # Update patients that don't have phi_detected
                self.patients.update_many(
                    {'phi_detected': {'$exists': False}},
                    {'$set': {'phi_detected': []}}
                )
                
                # Update patients that don't have medical_conditions
                self.patients.update_many(
                    {'medical_conditions': {'$exists': False}},
                    {'$set': {'medical_conditions': []}}
                )
                
                # Update patients that don't have medications
                self.patients.update_many(
                    {'medications': {'$exists': False}},
                    {'$set': {'medications': []}}
                )
                
                logger.info(f"✅ Patient structure ensured for MongoDB collection")
                
            else:  # Fallback mode
                for patient_id, patient_data in self.patients.items():
                    if 'processing_count' not in patient_data:
                        patient_data['processing_count'] = 1
                    if 'first_seen' not in patient_data:
                        patient_data['first_seen'] = datetime.now().isoformat()
                    if 'last_processed' not in patient_data:
                        patient_data['last_processed'] = datetime.now().isoformat()
                    if 'phi_detected' not in patient_data:
                        patient_data['phi_detected'] = []
                    if 'medical_conditions' not in patient_data:
                        patient_data['medical_conditions'] = []
                    if 'medications' not in patient_data:
                        patient_data['medications'] = []
                
                logger.info(f"✅ Patient structure ensured for fallback storage")
                
        except Exception as e:
            logger.error(f"❌ Failed to ensure patient structure: {e}")
    
    def get_all_patients(self) -> Dict[str, Any]:
        """Get all patients"""
        try:
            if self.client:  # MongoDB mode
                patients = list(self.patients.find())
                return {'patients': self.convert_objectid_to_str(patients)}
            else:  # Fallback mode
                return {'patients': self.patients}
        except Exception as e:
            logger.error(f"❌ Failed to get all patients: {e}")
            return {'patients': {}}
    
    def get_medical_insights(self) -> Dict[str, Any]:
        """Get medical insights from analytics"""
        try:
            if self.client:  # MongoDB mode
                analytics = self.analytics.find_one({})
                if analytics and 'medical_insights' in analytics:
                    return analytics['medical_insights']
                else:
                    return self.get_default_medical_insights()
            else:  # Fallback mode
                return self.analytics.get('medical_insights', self.get_default_medical_insights())
        except Exception as e:
            logger.error(f"❌ Failed to get medical insights: {e}")
            return self.get_default_medical_insights()
    
    def get_default_medical_insights(self) -> Dict[str, Any]:
        """Get default medical insights structure"""
        return {
            'top_conditions': ['Hypertension', 'Type 2 Diabetes', 'Asthma'],
            'top_medications': ['Lisinopril', 'Metformin', 'Atorvastatin'],
            'condition_trends': {
                'increasing': ['Hypertension', 'Type 2 Diabetes'],
                'stable': ['Asthma', 'COPD'],
                'decreasing': ['Acute Infections']
            },
            'medication_adherence': 85.0,
            'risk_factors': ['Hypertension', 'Diabetes', 'Smoking'],
            'preventive_care': {
                'screening_rate': 75.0,
                'vaccination_rate': 90.0,
                'wellness_visits': 80.0
            }
        }
    
    def reset_database(self):
        """Reset all data"""
        try:
            if self.client:  # MongoDB mode
                self.processing_history.delete_many({})
                self.patients.delete_many({})
                self.analytics.delete_many({})
                self.initialize_collections()
                logger.info("✅ MongoDB database reset successfully")
            else:  # Fallback mode
                self.processing_history = []
                self.patients = {}
                self.analytics = self.get_initial_analytics()
                logger.info("✅ Fallback storage reset successfully")
        except Exception as e:
            logger.error(f"❌ Failed to reset database: {e}")

    def convert_objectid_to_str(self, obj):
        """Convert ObjectId to string for JSON serialization"""
        if isinstance(obj, dict):
            return {k: self.convert_objectid_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_objectid_to_str(item) for item in obj]
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'ObjectId':
            return str(obj)
        else:
            return obj

# Global MongoDB store instance
mongodb_store = MongoDBStore()
 