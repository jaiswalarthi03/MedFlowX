import json
import uuid
from datetime import datetime

class FHIRConverter:
    """Converts processed CDA data to FHIR R4 resources"""
    
    def __init__(self):
        self.base_url = "https://example.com/fhir"
    
    def convert_to_fhir(self, cda_data):
        """Convert processed CDA data to FHIR R4 resources"""
        try:
            fhir_bundle = {
                "resourceType": "Bundle",
                "id": str(uuid.uuid4()),
                "type": "transaction",
                "timestamp": datetime.now().isoformat(),
                "entry": []
            }
            
            patient_resource = None
            
            # Convert patient data
            if cda_data.get('patient'):
                patient_resource = self._create_patient_resource(cda_data['patient'])
                fhir_bundle['entry'].append({
                    "resource": patient_resource,
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    }
                })
            
            # Convert conditions
            if cda_data.get('clinical_data', {}).get('conditions'):
                for condition_data in cda_data['clinical_data']['conditions']:
                    condition_resource = self._create_condition_resource(condition_data, patient_resource)
                    if condition_resource:
                        fhir_bundle['entry'].append({
                            "resource": condition_resource,
                            "request": {
                                "method": "POST",
                                "url": "Condition"
                            }
                        })
            
            # Convert medications
            if cda_data.get('medications'):
                for medication_data in cda_data['medications']:
                    medication_request = self._create_medication_request_resource(medication_data, patient_resource)
                    if medication_request:
                        fhir_bundle['entry'].append({
                            "resource": medication_request,
                            "request": {
                                "method": "POST",
                                "url": "MedicationRequest"
                            }
                        })
            
            # Convert procedures
            if cda_data.get('procedures'):
                for procedure_data in cda_data['procedures']:
                    procedure_resource = self._create_procedure_resource(procedure_data, patient_resource)
                    if procedure_resource:
                        fhir_bundle['entry'].append({
                            "resource": procedure_resource,
                            "request": {
                                "method": "POST",
                                "url": "Procedure"
                            }
                        })
            
            # Convert observations
            if cda_data.get('observations'):
                for observation_data in cda_data['observations']:
                    observation_resource = self._create_observation_resource(observation_data, patient_resource)
                    if observation_resource:
                        fhir_bundle['entry'].append({
                            "resource": observation_resource,
                            "request": {
                                "method": "POST",
                                "url": "Observation"
                            }
                        })
            
            # Create conversion summary
            conversion_summary = {
                'conversion_timestamp': datetime.now().isoformat(),
                'total_resources': len(fhir_bundle['entry']),
                'resource_types': {},
                'conversion_status': 'completed',
                'fhir_version': 'R4',
                'bundle_id': fhir_bundle['id']
            }
            
            # Count resource types
            for entry in fhir_bundle['entry']:
                resource_type = entry['resource']['resourceType']
                conversion_summary['resource_types'][resource_type] = conversion_summary['resource_types'].get(resource_type, 0) + 1
            
            return {
                'fhir_bundle': fhir_bundle,
                'conversion_summary': conversion_summary
            }
            
        except Exception as e:
            return {
                'conversion_timestamp': datetime.now().isoformat(),
                'conversion_status': 'failed',
                'error': f'FHIR conversion error: {str(e)}'
            }
    
    def _create_patient_resource(self, patient_data):
        """Create FHIR Patient resource"""
        patient_resource = {
            "resourceType": "Patient",
            "id": str(uuid.uuid4()),
            "identifier": []
        }
        
        # Add medical record number
        if patient_data.get('medical_record_number'):
            patient_resource["identifier"].append({
                "system": patient_data.get('medical_record_number', ''),
                "value": patient_data.get('patient_id', '')
            })
        
        # Add name
        if patient_data.get('name'):
            name_parts = patient_data['name'].split(' ')
            patient_resource["name"] = [{
                "family": name_parts[-1] if name_parts else '',
                "given": name_parts[:-1] if len(name_parts) > 1 else name_parts
            }]
        
        # Add gender
        if patient_data.get('gender'):
            gender_map = {'M': 'male', 'F': 'female', 'male': 'male', 'female': 'female'}
            patient_resource["gender"] = gender_map.get(patient_data['gender'], 'unknown')
        
        # Add birth date
        if patient_data.get('birth_date'):
            # Convert HL7 date format to FHIR date format
            birth_date = self._convert_hl7_date(patient_data['birth_date'])
            if birth_date:
                patient_resource["birthDate"] = birth_date
        
        return patient_resource
    
    def _create_condition_resource(self, condition_data, patient_resource):
        """Create FHIR Condition resource"""
        if not condition_data or not patient_resource:
            return None
        
        condition_resource = {
            "resourceType": "Condition",
            "id": str(uuid.uuid4()),
            "subject": {
                "reference": f"Patient/{patient_resource['id']}"
            }
        }
        
        # Add condition code
        if condition_data.get('code') and condition_data.get('display_name'):
            condition_resource["code"] = {
                "coding": [{
                    "system": self._map_code_system(condition_data.get('code_system', '')),
                    "code": condition_data['code'],
                    "display": condition_data['display_name']
                }],
                "text": condition_data['display_name']
            }
        
        # Add clinical status
        condition_resource["clinicalStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": "active"
            }]
        }
        
        # Add verification status
        condition_resource["verificationStatus"] = {
            "coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                "code": "confirmed"
            }]
        }
        
        # Add onset date
        if condition_data.get('onset_date'):
            onset_date = self._convert_hl7_date(condition_data['onset_date'])
            if onset_date:
                condition_resource["onsetDateTime"] = onset_date
        
        return condition_resource
    
    def _create_medication_request_resource(self, medication_data, patient_resource):
        """Create FHIR MedicationRequest resource"""
        if not medication_data or not patient_resource:
            return None
        
        medication_request = {
            "resourceType": "MedicationRequest",
            "id": str(uuid.uuid4()),
            "status": "active",
            "intent": "order",
            "subject": {
                "reference": f"Patient/{patient_resource['id']}"
            }
        }
        
        # Add medication code
        if medication_data.get('code') and medication_data.get('name'):
            medication_request["medicationCodeableConcept"] = {
                "coding": [{
                    "system": self._map_code_system(medication_data.get('code_system', '')),
                    "code": medication_data['code'],
                    "display": medication_data['name']
                }],
                "text": medication_data['name']
            }
        
        # Add dosage instruction
        if medication_data.get('dose') or medication_data.get('route'):
            dosage_instruction = {}
            
            if medication_data.get('dose') and medication_data.get('dose_unit'):
                dosage_instruction["doseAndRate"] = [{
                    "doseQuantity": {
                        "value": float(medication_data['dose']) if medication_data['dose'].replace('.', '').isdigit() else 1,
                        "unit": medication_data['dose_unit']
                    }
                }]
            
            if medication_data.get('route'):
                dosage_instruction["route"] = {
                    "text": medication_data['route']
                }
            
            medication_request["dosageInstruction"] = [dosage_instruction]
        
        return medication_request
    
    def _create_procedure_resource(self, procedure_data, patient_resource):
        """Create FHIR Procedure resource"""
        if not procedure_data or not patient_resource:
            return None
        
        procedure_resource = {
            "resourceType": "Procedure",
            "id": str(uuid.uuid4()),
            "status": "completed",
            "subject": {
                "reference": f"Patient/{patient_resource['id']}"
            }
        }
        
        # Add procedure code
        if procedure_data.get('code') and procedure_data.get('name'):
            procedure_resource["code"] = {
                "coding": [{
                    "system": self._map_code_system(procedure_data.get('code_system', '')),
                    "code": procedure_data['code'],
                    "display": procedure_data['name']
                }],
                "text": procedure_data['name']
            }
        
        # Add performed date
        if procedure_data.get('date'):
            performed_date = self._convert_hl7_date(procedure_data['date'])
            if performed_date:
                procedure_resource["performedDateTime"] = performed_date
        
        return procedure_resource
    
    def _create_observation_resource(self, observation_data, patient_resource):
        """Create FHIR Observation resource"""
        if not observation_data or not patient_resource:
            return None
        
        observation_resource = {
            "resourceType": "Observation",
            "id": str(uuid.uuid4()),
            "status": "final",
            "subject": {
                "reference": f"Patient/{patient_resource['id']}"
            }
        }
        
        # Add observation code
        if observation_data.get('code') and observation_data.get('name'):
            observation_resource["code"] = {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": observation_data['code'],
                    "display": observation_data['name']
                }],
                "text": observation_data['name']
            }
        
        # Add value
        if observation_data.get('value'):
            if observation_data.get('unit'):
                observation_resource["valueQuantity"] = {
                    "value": float(observation_data['value']) if observation_data['value'].replace('.', '').isdigit() else 0,
                    "unit": observation_data['unit']
                }
            else:
                observation_resource["valueString"] = observation_data['value']
        
        # Add effective date
        if observation_data.get('date'):
            effective_date = self._convert_hl7_date(observation_data['date'])
            if effective_date:
                observation_resource["effectiveDateTime"] = effective_date
        
        return observation_resource
    
    def _convert_hl7_date(self, hl7_date):
        """Convert HL7 date format to FHIR date format"""
        if not hl7_date:
            return None
        
        try:
            # HL7 dates are typically in format YYYYMMDD or YYYYMMDDHHMMSS
            if len(hl7_date) >= 8:
                year = hl7_date[:4]
                month = hl7_date[4:6]
                day = hl7_date[6:8]
                
                # Validate date components
                if year.isdigit() and month.isdigit() and day.isdigit():
                    return f"{year}-{month}-{day}"
        
        except Exception:
            pass
        
        return None
    
    def _map_code_system(self, code_system):
        """Map HL7 code system OIDs to FHIR URIs"""
        code_system_map = {
            '2.16.840.1.113883.6.96': 'http://snomed.info/sct',  # SNOMED CT
            '2.16.840.1.113883.6.1': 'http://loinc.org',  # LOINC
            '2.16.840.1.113883.6.3': 'http://hl7.org/fhir/sid/icd-10-cm',  # ICD-10-CM
            '2.16.840.1.113883.6.88': 'http://www.nlm.nih.gov/research/umls/rxnorm',  # RxNorm
            '2.16.840.1.113883.6.4': 'http://hl7.org/fhir/sid/icd-10-pcs'  # ICD-10-PCS
        }
        
        return code_system_map.get(code_system, code_system)
