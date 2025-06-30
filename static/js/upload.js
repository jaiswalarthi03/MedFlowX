// Upload functionality for CDA-to-FHIR Converter

document.addEventListener('DOMContentLoaded', function() {
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    const uploadProgress = document.getElementById('upload-progress');
    const filePreviewCard = document.getElementById('file-preview-card');
    const processingResultsCard = document.getElementById('processing-results-card');

    // Initialize upload functionality
    initializeUpload();
    
    function initializeUpload() {
        // File input change handler
        fileInput.addEventListener('change', handleFileSelect);
        
        // Drag and drop handlers
        uploadZone.addEventListener('dragover', handleDragOver);
        uploadZone.addEventListener('dragleave', handleDragLeave);
        uploadZone.addEventListener('drop', handleDrop);
        
        // Click handler for upload zone
        uploadZone.addEventListener('click', function(e) {
            if (e.target === uploadZone || e.target.closest('.upload-zone')) {
                fileInput.click();
            }
        });
    }
    
    function handleDragOver(e) {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    }
    
    function handleDragLeave(e) {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
    }
    
    function handleDrop(e) {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            processFiles(files);
        }
    }
    
    function handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            processFiles(files);
        }
    }
    
    function processFiles(files) {
        // Show upload progress
        showUploadProgress();
        
        // Process each file
        Array.from(files).forEach(file => {
            uploadFile(file);
        });
    }
    
    function showUploadProgress() {
        uploadProgress.classList.remove('d-none');
        const progressBar = uploadProgress.querySelector('.progress-bar');
        
        // Animate progress bar
        let progress = 0;
        const interval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress >= 90) {
                clearInterval(interval);
                progress = 90;
            }
            progressBar.style.width = progress + '%';
        }, 200);
    }
    
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        // Get selected processing mode
        const processingMode = document.querySelector('input[name="processingMode"]:checked').value;
        
        // Choose endpoint based on processing mode
        let endpoint = '/api/upload';
        if (processingMode === 'advanced') {
            endpoint = '/api/upload-advanced';
        }
        
        fetch(endpoint, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            hideUploadProgress();
            
            if (data.success) {
                showFilePreview(file, data);
                if (data.processing_result || data.comprehend_results || data.fhir_resources) {
                    showProcessingResults(data, processingMode);
                }
                showSuccessMessage('File uploaded and processed successfully!');
            } else {
                showErrorMessage(data.error || 'Upload failed');
            }
        })
        .catch(error => {
            hideUploadProgress();
            console.error('Upload error:', error);
            showErrorMessage('Upload failed: ' + error.message);
        });
    }
    
    function hideUploadProgress() {
        uploadProgress.classList.add('d-none');
        const progressBar = uploadProgress.querySelector('.progress-bar');
        progressBar.style.width = '100%';
    }
    
    function showFilePreview(file, data) {
        const previewContent = document.getElementById('file-preview-content');
        
        const fileInfo = `
            <div class="file-preview-item fade-in">
                <div class="row align-items-center">
                    <div class="col-md-2 text-center">
                        <i data-feather="file" style="width: 48px; height: 48px; color: #C8A8E9;"></i>
                    </div>
                    <div class="col-md-10">
                        <h6 class="mb-1">${file.name}</h6>
                        <p class="text-muted mb-1">Size: ${formatFileSize(file.size)}</p>
                        <p class="text-muted mb-1">Type: ${file.type || 'Unknown'}</p>
                        <p class="text-muted mb-0">Uploaded: ${new Date().toLocaleString()}</p>
                        ${data.file_type === 'cda' ? '<span class="badge bg-success">CDA Document</span>' : '<span class="badge bg-info">Image/Other</span>'}
                        ${data.processing_mode ? `<span class="badge bg-warning ms-1">${data.processing_mode}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
        
        previewContent.innerHTML = fileInfo;
        filePreviewCard.classList.remove('d-none');
        
        // Re-initialize Feather icons
        feather.replace();
    }
    
    function showProcessingResults(data, processingMode) {
        const resultsContent = document.getElementById('processing-results-content');
        
        let resultsHTML = '<div class="fade-in">';
        
        // Processing Status
        resultsHTML += `
            <div class="processing-result-item mb-3">
                <div class="d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">Processing Status</h6>
                    <span class="badge bg-success">COMPLETED</span>
                </div>
                <small class="text-muted">Processed at: ${new Date().toLocaleString()}</small>
                ${processingMode !== 'basic' ? `<br><small class="text-muted">Mode: ${processingMode.toUpperCase()}</small>` : ''}
            </div>
        `;
        
        // Basic Processing Results
        if (data.processing_result) {
            const processingResult = data.processing_result;
            
            // Patient Information
            if (processingResult.patient && processingResult.patient.name) {
                resultsHTML += `
                    <div class="processing-result-item mb-3">
                        <h6 class="mb-2"><i data-feather="user" class="me-1"></i> Patient Information</h6>
                        <div class="row">
                            <div class="col-md-6">
                                <small class="text-muted">Name:</small><br>
                                <strong>${processingResult.patient.name || 'Not available'}</strong>
                            </div>
                            <div class="col-md-6">
                                <small class="text-muted">Patient ID:</small><br>
                                <strong>${processingResult.patient.patient_id || 'Not available'}</strong>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Clinical Data Summary
            if (processingResult.clinical_data) {
                const conditions = processingResult.clinical_data.conditions || [];
                resultsHTML += `
                    <div class="processing-result-item mb-3">
                        <h6 class="mb-2"><i data-feather="heart" class="me-1"></i> Clinical Data Extracted</h6>
                        <div class="row">
                            <div class="col-md-4">
                                <small class="text-muted">Conditions:</small><br>
                                <strong>${conditions.length}</strong>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Medications:</small><br>
                                <strong>${processingResult.medications ? processingResult.medications.length : 0}</strong>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Procedures:</small><br>
                                <strong>${processingResult.procedures ? processingResult.procedures.length : 0}</strong>
                            </div>
                        </div>
                    </div>
                `;
            }
        }
        
        // Advanced Processing Results
        if (data.comprehend_results) {
            resultsHTML += `
                <div class="processing-result-item mb-3">
                    <h6 class="mb-2"><i data-feather="brain" class="me-1"></i> AWS Comprehend Medical Results</h6>
                    <div class="row">
                        <div class="col-md-4">
                            <small class="text-muted">Medical Entities:</small><br>
                            <strong>${data.comprehend_results.entities ? data.comprehend_results.entities.length : 0}</strong>
                        </div>
                        <div class="col-md-4">
                            <small class="text-muted">PHI Detected:</small><br>
                            <strong>${data.comprehend_results.phi ? data.comprehend_results.phi.length : 0}</strong>
                        </div>
                        <div class="col-md-4">
                            <small class="text-muted">ICD-10 Codes:</small><br>
                            <strong>${data.comprehend_results.icd10_codes ? data.comprehend_results.icd10_codes.length : 0}</strong>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // FHIR Resources
        if (data.fhir_resources || data.fhir_result) {
            const fhirResources = data.fhir_resources || data.fhir_result;
            resultsHTML += `
                <div class="processing-result-item mb-3">
                    <h6 class="mb-2"><i data-feather="layers" class="me-1"></i> FHIR Resources Created</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <small class="text-muted">Total Resources:</small><br>
                            <strong>${Array.isArray(fhirResources) ? fhirResources.length : 1}</strong>
                        </div>
                        <div class="col-md-6">
                            <small class="text-muted">Resource Types:</small><br>
                            <strong>Patient, Condition, MedicationRequest, Observation</strong>
                        </div>
                    </div>
                </div>
            `;
        }
        
        // Image Analysis Results
        if (data.fhir_observation) {
            resultsHTML += `
                <div class="processing-result-item mb-3">
                    <h6 class="mb-2"><i data-feather="image" class="me-1"></i> Medical Image Analysis</h6>
                    <div class="row">
                        <div class="col-md-6">
                            <small class="text-muted">Patient MRN:</small><br>
                            <strong>${data.patient_mrn || 'Not specified'}</strong>
                        </div>
                        <div class="col-md-6">
                            <small class="text-muted">Observation ID:</small><br>
                            <strong>${data.fhir_observation.id || 'Generated'}</strong>
                        </div>
                    </div>
                </div>
            `;
        }
        
        resultsHTML += '</div>';
        
        resultsContent.innerHTML = resultsHTML;
        processingResultsCard.classList.remove('d-none');
        
        // Re-initialize Feather icons
        feather.replace();
    }
    
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    function showSuccessMessage(message) {
        showMessage(message, 'success');
    }
    
    function showErrorMessage(message) {
        showMessage(message, 'error');
    }
    
    function showMessage(message, type) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `toast-notification toast-${type}`;
        toast.innerHTML = `
            <div class="toast-content">
                <i data-feather="${type === 'success' ? 'check-circle' : 'x-circle'}" class="me-2"></i>
                ${message}
            </div>
        `;
        
        // Add to page
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // Remove toast after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 5000);
        
        // Re-initialize Feather icons
        feather.replace();
    }
});

// Sample CDA function
function showSampleCDA() {
    const modal = new bootstrap.Modal(document.getElementById('sampleCDAModal'));
    modal.show();
}

