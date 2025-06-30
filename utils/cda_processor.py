import xml.etree.ElementTree as ET
import json
import re
from datetime import datetime

class CDAProcessor:
    """Processes HL7 CDA documents and extracts healthcare information"""
    
    def __init__(self):
        self.namespace_map = {
            'hl7': 'urn:hl7-org:v3',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
    
    def process_cda_file(self, filepath):
        """Process a CDA file and extract relevant healthcare data"""
        try:
            # Parse XML file
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Extract patient information
            patient_data = self._extract_patient_data(root)
            
            # Extract clinical data
            clinical_data = self._extract_clinical_data(root)
            
            # Extract medications
            medications = self._extract_medications(root)
            
            # Extract procedures
            procedures = self._extract_procedures(root)
            
            # Extract vital signs and observations
            observations = self._extract_observations(root)
            
            processing_result = {
                'processing_timestamp': datetime.now().isoformat(),
                'document_type': 'CDA',
                'patient': patient_data,
                'clinical_data': clinical_data,
                'medications': medications,
                'procedures': procedures,
                'observations': observations,
                'processing_status': 'completed',
                'extracted_entities': len(clinical_data.get('conditions', [])) + len(medications) + len(procedures)
            }
            
            return processing_result
            
        except ET.ParseError as e:
            return {
                'processing_timestamp': datetime.now().isoformat(),
                'document_type': 'CDA',
                'processing_status': 'failed',
                'error': f'XML parsing error: {str(e)}'
            }
        except Exception as e:
            return {
                'processing_timestamp': datetime.now().isoformat(),
                'document_type': 'CDA',
                'processing_status': 'failed',
                'error': f'Processing error: {str(e)}'
            }
    
    def _extract_patient_data(self, root):
        """Extract patient demographic information"""
        patient_data = {
            'patient_id': None,
            'name': None,
            'gender': None,
            'birth_date': None,
            'address': None,
            'phone': None,
            'medical_record_number': None
        }
        
        try:
            # Look for patient information in recordTarget
            record_target = root.find('.//hl7:recordTarget', self.namespace_map)
            if record_target is not None:
                patient_role = record_target.find('.//hl7:patientRole', self.namespace_map)
                if patient_role is not None:
                    # Extract patient ID
                    id_elem = patient_role.find('.//hl7:id', self.namespace_map)
                    if id_elem is not None:
                        patient_data['patient_id'] = id_elem.get('extension', '')
                        patient_data['medical_record_number'] = id_elem.get('root', '')
                        print(f"DEBUG: Extracted patient_id: {patient_data['patient_id']}")
                    
                    # Extract patient name
                    name_elem = patient_role.find('.//hl7:patient/hl7:name', self.namespace_map)
                    if name_elem is not None:
                        given = name_elem.find('.//hl7:given', self.namespace_map)
                        family = name_elem.find('.//hl7:family', self.namespace_map)
                        if given is not None and family is not None:
                            patient_data['name'] = f"{given.text} {family.text}"
                            print(f"DEBUG: Extracted name: {patient_data['name']}")
                    
                    # Extract gender
                    gender_elem = patient_role.find('.//hl7:patient/hl7:administrativeGenderCode', self.namespace_map)
                    if gender_elem is not None:
                        patient_data['gender'] = gender_elem.get('code', '')
                        print(f"DEBUG: Extracted gender: {patient_data['gender']}")
                    
                    # Extract birth date
                    birth_elem = patient_role.find('.//hl7:patient/hl7:birthTime', self.namespace_map)
                    if birth_elem is not None:
                        patient_data['birth_date'] = birth_elem.get('value', '')
                        print(f"DEBUG: Extracted birth_date: {patient_data['birth_date']}")
        
        except Exception as e:
            print(f"Error extracting patient data: {e}")
        
        print(f"DEBUG: Final patient_data: {patient_data}")
        return patient_data
    
    def _extract_clinical_data(self, root):
        """Extract clinical conditions and diagnoses"""
        clinical_data = {
            'conditions': [],
            'allergies': [],
            'problems': []
        }
        
        try:
            # Look for structured body sections
            sections = root.findall('.//hl7:section', self.namespace_map)
            print(f"DEBUG: Found {len(sections)} sections")
            
            for section in sections:
                # Check section code to identify type
                code_elem = section.find('.//hl7:code', self.namespace_map)
                if code_elem is not None:
                    section_code = code_elem.get('code', '')
                    section_name = code_elem.get('displayName', '')
                    print(f"DEBUG: Processing section {section_code} - {section_name}")
                    
                    # Problem list section
                    if section_code in ['11450-4', '46240-8']:
                        entries = section.findall('.//hl7:entry', self.namespace_map)
                        print(f"DEBUG: Found {len(entries)} entries in problem list")
                        for entry in entries:
                            observation = entry.find('.//hl7:observation', self.namespace_map)
                            if observation is not None:
                                condition = self._extract_condition_from_observation(observation)
                                if condition:
                                    clinical_data['conditions'].append(condition)
                                    print(f"DEBUG: Added condition: {condition}")
                    
                    # Allergies section
                    elif section_code in ['48765-2', '10160-0']:
                        entries = section.findall('.//hl7:entry', self.namespace_map)
                        for entry in entries:
                            allergy = self._extract_allergy_from_entry(entry)
                            if allergy:
                                clinical_data['allergies'].append(allergy)
        
        except Exception as e:
            print(f"Error extracting clinical data: {e}")
        
        print(f"DEBUG: Final clinical_data: {clinical_data}")
        return clinical_data
    
    def _extract_condition_from_observation(self, observation):
        """Extract condition information from observation element"""
        condition = {}
        
        try:
            # Extract condition code
            value_elem = observation.find('.//hl7:value', self.namespace_map)
            if value_elem is not None:
                condition['code'] = value_elem.get('code', '')
                condition['display_name'] = value_elem.get('displayName', '')
                condition['code_system'] = value_elem.get('codeSystem', '')
            
            # Extract effective time
            effective_time = observation.find('.//hl7:effectiveTime', self.namespace_map)
            if effective_time is not None:
                condition['onset_date'] = effective_time.get('value', '')
            
            # Extract status
            status_code = observation.find('.//hl7:statusCode', self.namespace_map)
            if status_code is not None:
                condition['status'] = status_code.get('code', '')
        
        except Exception as e:
            print(f"Error extracting condition: {e}")
        
        return condition if condition else None
    
    def _extract_allergy_from_entry(self, entry):
        """Extract allergy information from entry element"""
        allergy = {}
        
        try:
            observation = entry.find('.//hl7:observation', self.namespace_map)
            if observation is not None:
                # Extract allergen
                participant = observation.find('.//hl7:participant', self.namespace_map)
                if participant is not None:
                    code_elem = participant.find('.//hl7:code', self.namespace_map)
                    if code_elem is not None:
                        allergy['allergen'] = code_elem.get('displayName', '')
                        allergy['allergen_code'] = code_elem.get('code', '')
                
                # Extract reaction
                entry_relationship = observation.find('.//hl7:entryRelationship', self.namespace_map)
                if entry_relationship is not None:
                    reaction_obs = entry_relationship.find('.//hl7:observation', self.namespace_map)
                    if reaction_obs is not None:
                        value_elem = reaction_obs.find('.//hl7:value', self.namespace_map)
                        if value_elem is not None:
                            allergy['reaction'] = value_elem.get('displayName', '')
        
        except Exception as e:
            print(f"Error extracting allergy: {e}")
        
        return allergy if allergy else None
    
    def _extract_medications(self, root):
        """Extract medication information"""
        medications = []
        
        try:
            # Look for medication sections
            sections = root.findall('.//hl7:section', self.namespace_map)
            
            for section in sections:
                code_elem = section.find('.//hl7:code', self.namespace_map)
                if code_elem is not None and code_elem.get('code') in ['10160-0', '57828-6']:
                    section_name = code_elem.get('displayName', '')
                    print(f"DEBUG: Processing medication section: {section_name}")
                    entries = section.findall('.//hl7:entry', self.namespace_map)
                    print(f"DEBUG: Found {len(entries)} medication entries")
                    
                    for entry in entries:
                        medication = self._extract_medication_from_entry(entry)
                        if medication:
                            medications.append(medication)
                            print(f"DEBUG: Added medication: {medication}")
        
        except Exception as e:
            print(f"Error extracting medications: {e}")
        
        print(f"DEBUG: Final medications: {medications}")
        return medications
    
    def _extract_medication_from_entry(self, entry):
        """Extract medication details from entry element"""
        medication = {}
        try:
            # Look for substance administration
            substance_admin = entry.find('.//hl7:substanceAdministration', self.namespace_map)
            if substance_admin is not None:
                # Extract medication name - try multiple paths
                consumable = substance_admin.find('.//hl7:consumable', self.namespace_map)
                if consumable is not None:
                    # Try to find manufacturedProduct first
                    manufactured_product = consumable.find('.//hl7:manufacturedProduct', self.namespace_map)
                    if manufactured_product is not None:
                        manufactured_material = manufactured_product.find('.//hl7:manufacturedMaterial', self.namespace_map)
                        if manufactured_material is not None:
                            code_elem = manufactured_material.find('.//hl7:code', self.namespace_map)
                            if code_elem is not None:
                                medication['name'] = code_elem.get('displayName', '')
                                medication['code'] = code_elem.get('code', '')
                                medication['code_system'] = code_elem.get('codeSystem', '')
                    else:
                        # Fallback to direct code element in consumable
                        code_elem = consumable.find('.//hl7:code', self.namespace_map)
                        if code_elem is not None:
                            medication['name'] = code_elem.get('displayName', '')
                            medication['code'] = code_elem.get('code', '')
                            medication['code_system'] = code_elem.get('codeSystem', '')
                
                # Extract dosage
                dose_quantity = substance_admin.find('.//hl7:doseQuantity', self.namespace_map)
                if dose_quantity is not None:
                    medication['dose'] = dose_quantity.get('value', '')
                    medication['dose_unit'] = dose_quantity.get('unit', '')
                
                # Extract route
                route_code = substance_admin.find('.//hl7:routeCode', self.namespace_map)
                if route_code is not None:
                    medication['route'] = route_code.get('displayName', '')
        except Exception as e:
            print(f"Error extracting medication: {e}")
        return medication if medication else None
    
    def _extract_procedures(self, root):
        """Extract procedure information"""
        procedures = []
        
        try:
            # Look for procedure sections
            sections = root.findall('.//hl7:section', self.namespace_map)
            
            for section in sections:
                code_elem = section.find('.//hl7:code', self.namespace_map)
                if code_elem is not None and code_elem.get('code') in ['47519-4', '8716-3']:
                    entries = section.findall('.//hl7:entry', self.namespace_map)
                    
                    for entry in entries:
                        procedure = self._extract_procedure_from_entry(entry)
                        if procedure:
                            procedures.append(procedure)
        
        except Exception as e:
            print(f"Error extracting procedures: {e}")
        
        return procedures
    
    def _extract_procedure_from_entry(self, entry):
        """Extract procedure details from entry element"""
        procedure = {}
        
        try:
            # Look for procedure act
            procedure_elem = entry.find('.//hl7:procedure', self.namespace_map)
            if procedure_elem is not None:
                # Extract procedure code
                code_elem = procedure_elem.find('.//hl7:code', self.namespace_map)
                if code_elem is not None:
                    procedure['name'] = code_elem.get('displayName', '')
                    procedure['code'] = code_elem.get('code', '')
                    procedure['code_system'] = code_elem.get('codeSystem', '')
                
                # Extract effective time
                effective_time = procedure_elem.find('.//hl7:effectiveTime', self.namespace_map)
                if effective_time is not None:
                    procedure['date'] = effective_time.get('value', '')
        
        except Exception as e:
            print(f"Error extracting procedure: {e}")
        
        return procedure if procedure else None
    
    def _extract_observations(self, root):
        """Extract vital signs and lab results"""
        observations = []
        
        try:
            # Look for vital signs and results sections
            sections = root.findall('.//hl7:section', self.namespace_map)
            
            for section in sections:
                code_elem = section.find('.//hl7:code', self.namespace_map)
                if code_elem is not None and code_elem.get('code') in ['8716-3', '30954-2']:
                    entries = section.findall('.//hl7:entry', self.namespace_map)
                    
                    for entry in entries:
                        observation = self._extract_observation_from_entry(entry)
                        if observation:
                            observations.append(observation)
        
        except Exception as e:
            print(f"Error extracting observations: {e}")
        
        return observations
    
    def _extract_observation_from_entry(self, entry):
        """Extract observation details from entry element"""
        observation = {}
        
        try:
            obs_elem = entry.find('.//hl7:observation', self.namespace_map)
            if obs_elem is not None:
                # Extract observation code
                code_elem = obs_elem.find('.//hl7:code', self.namespace_map)
                if code_elem is not None:
                    observation['name'] = code_elem.get('displayName', '')
                    observation['code'] = code_elem.get('code', '')
                
                # Extract value
                value_elem = obs_elem.find('.//hl7:value', self.namespace_map)
                if value_elem is not None:
                    observation['value'] = value_elem.get('value', '')
                    observation['unit'] = value_elem.get('unit', '')
                
                # Extract effective time
                effective_time = obs_elem.find('.//hl7:effectiveTime', self.namespace_map)
                if effective_time is not None:
                    observation['date'] = effective_time.get('value', '')
        
        except Exception as e:
            print(f"Error extracting observation: {e}")
        
        return observation if observation else None
