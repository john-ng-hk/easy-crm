// File upload functionality
window.EasyCRM = window.EasyCRM || {};

// Simple utility functions for upload workflow
window.EasyCRM.Utils = window.EasyCRM.Utils || {
    // Simple toast notification
    showToast: function(message, type = 'info') {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `fixed top-4 left-1/2 transform -translate-x-1/2 px-6 py-3 rounded-lg shadow-lg z-50 transition-all duration-300`;
        
        // Set toast styling based on type
        switch (type) {
            case 'success':
                toast.classList.add('bg-green-600', 'text-white');
                break;
            case 'error':
                toast.classList.add('bg-red-600', 'text-white');
                break;
            case 'warning':
                toast.classList.add('bg-yellow-600', 'text-white');
                break;
            default:
                toast.classList.add('bg-blue-600', 'text-white');
        }
        
        toast.textContent = message;
        
        // Add to DOM
        document.body.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(-50%) translateY(0)';
        }, 10);
        
        // Remove after delay
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(-50%) translateY(-20px)';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 4000);
    },

    // Format file size
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
};

window.EasyCRM.Upload = {
    currentUpload: null,
    
    // Initialize upload functionality
    init: function() {
        this.attachEventHandlers();
        this.setupDragAndDrop();
    },

    // Attach event handlers
    attachEventHandlers: function() {
        const fileInput = document.getElementById('file-input');
        const browseBtn = document.getElementById('browse-btn');
        const uploadArea = document.getElementById('upload-area');

        // Browse button click
        browseBtn.addEventListener('click', () => {
            fileInput.click();
        });

        // Upload area click
        uploadArea.addEventListener('click', (e) => {
            if (e.target === uploadArea || e.target.closest('#upload-area')) {
                fileInput.click();
            }
        });

        // File input change
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileSelection(e.target.files[0]);
            }
        });
    },

    // Setup drag and drop functionality
    setupDragAndDrop: function() {
        const uploadArea = document.getElementById('upload-area');

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight drop area when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.add('upload-dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadArea.addEventListener(eventName, () => {
                uploadArea.classList.remove('upload-dragover');
            }, false);
        });

        // Handle dropped files
        uploadArea.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files.length > 0) {
                this.handleFileSelection(files[0]);
            }
        }, false);
    },

    // Prevent default drag behaviors
    preventDefaults: function(e) {
        e.preventDefault();
        e.stopPropagation();
    },

    // Handle file selection
    handleFileSelection: function(file) {
        // Validate file
        const validation = this.validateFile(file);
        if (!validation.valid) {
            this.showUploadStatus('error', validation.message);
            return;
        }

        // Start upload process
        this.startUpload(file);
    },

    // Validate selected file
    validateFile: function(file) {
        const config = window.EasyCRM.Config.APP;
        
        // Check file size
        if (file.size > config.MAX_FILE_SIZE) {
            return {
                valid: false,
                message: `File size exceeds ${window.EasyCRM.Utils.formatFileSize(config.MAX_FILE_SIZE)} limit`
            };
        }

        // Check file type
        const fileName = file.name.toLowerCase();
        const isValidType = config.ALLOWED_FILE_TYPES.some(type => 
            fileName.endsWith(type)
        );

        if (!isValidType) {
            return {
                valid: false,
                message: `Invalid file type. Please upload ${config.ALLOWED_FILE_TYPES.join(', ')} files only`
            };
        }

        return { valid: true };
    },

    // Start file upload process
    startUpload: async function(file) {
        try {
            this.currentUpload = {
                file: file,
                startTime: Date.now(),
                status: 'uploading'
            };

            // Show status indicator immediately when upload starts
            if (window.EasyCRM.ProcessingStatusIndicator) {
                // Generate a temporary uploadId for immediate status display
                const tempUploadId = 'temp_' + Date.now();
                window.EasyCRM.ProcessingStatusIndicator.show(tempUploadId, 'uploading', file.name);
            } else {
                // Fallback to old upload progress display
                this.showUploadProgress(file.name, 0);
            }

            // Get presigned URL
            this.updateUploadStatus('Getting upload URL...');
            const presignedData = await window.EasyCRM.API.upload.getPresignedUrl(
                file.name,
                file.type,
                file.size
            );

            // Upload file to S3
            this.updateUploadStatus('Uploading file...');
            await window.EasyCRM.API.upload.uploadToS3(
                presignedData.uploadUrl,
                file,
                (progress) => {
                    this.updateUploadProgress(progress);
                    
                    // Update status indicator with upload progress if available
                    if (window.EasyCRM.ProcessingStatusIndicator && window.EasyCRM.ProcessingStatusIndicator.isShowing()) {
                        window.EasyCRM.ProcessingStatusIndicator.render({
                            status: 'uploading',
                            stage: 'file_upload',
                            progress: {
                                percentage: progress,
                                totalBatches: 0,
                                completedBatches: 0,
                                totalLeads: 0,
                                processedLeads: 0
                            },
                            metadata: {
                                fileName: file.name,
                                fileSize: file.size
                            }
                        });
                    }
                }
            );

            // Upload completed - transition to processing status tracking
            this.currentUpload.status = 'processing';
            
            // Start tracking processing status using the ProcessingStatusIndicator
            if (presignedData.uploadId && window.EasyCRM.ProcessingStatusIndicator) {
                console.log('Starting status tracking with uploadId:', presignedData.uploadId);
                
                // Update the status indicator with the real uploadId
                window.EasyCRM.ProcessingStatusIndicator.uploadId = presignedData.uploadId;
                
                // Update status to uploaded in the database and UI
                try {
                    console.log('Updating status to uploaded in database...');
                    await window.EasyCRM.API.processing.updateStatus(presignedData.uploadId, {
                        status: 'uploaded',
                        stage: 'file_processing',
                        progress: {
                            percentage: 100,
                            totalBatches: 0,
                            completedBatches: 0,
                            totalLeads: 0,
                            processedLeads: 0
                        },
                        metadata: {
                            fileName: file.name,
                            fileSize: file.size
                        }
                    });
                    
                    // Update the UI to show uploaded status
                    window.EasyCRM.ProcessingStatusIndicator.render({
                        status: 'uploaded',
                        stage: 'file_processing',
                        progress: {
                            percentage: 100,
                            totalBatches: 0,
                            completedBatches: 0,
                            totalLeads: 0,
                            processedLeads: 0
                        },
                        metadata: {
                            fileName: file.name,
                            fileSize: file.size
                        }
                    });
                    
                    console.log('Status updated successfully, starting polling...');
                    
                    // Wait a moment to show "uploaded" status, then start polling
                    setTimeout(() => {
                        window.EasyCRM.ProcessingStatusIndicator.startPolling();
                    }, 2000);
                    
                } catch (error) {
                    console.error('Failed to update status to uploaded:', error);
                    // Fall back to just showing the status and starting polling
                    window.EasyCRM.ProcessingStatusIndicator.render({
                        status: 'uploaded',
                        stage: 'file_processing',
                        progress: {
                            percentage: 100,
                            totalBatches: 0,
                            completedBatches: 0,
                            totalLeads: 0,
                            processedLeads: 0
                        },
                        metadata: {
                            fileName: file.name,
                            fileSize: file.size
                        }
                    });
                    
                    setTimeout(() => {
                        window.EasyCRM.ProcessingStatusIndicator.startPolling();
                    }, 2000);
                }
                
                // Hide the old upload progress/status elements
                this.hideOldUploadElements();
                
            } else if (presignedData.uploadId) {
                // Fallback to old tracking method if status indicator not available
                console.log('Falling back to old status tracking method');
                this.startProcessingStatusTracking(presignedData.uploadId, file.name);
            } else {
                // Fallback to file-based tracking for backward compatibility
                console.log('Falling back to file-based status tracking');
                this.startProcessingStatusTrackingByFile(presignedData.fileKey, file.name);
            }

        } catch (error) {
            this.handleUploadError(error, 'Upload');
            this.resetUploadArea();
        }
    },

    // Show upload progress
    showUploadProgress: function(filename, progress) {
        const progressContainer = document.getElementById('upload-progress');
        const filenameSpan = document.getElementById('upload-filename');
        const percentageSpan = document.getElementById('upload-percentage');
        const progressBar = document.getElementById('progress-bar');

        filenameSpan.textContent = filename;
        percentageSpan.textContent = `${Math.round(progress)}%`;
        progressBar.style.width = `${progress}%`;

        progressContainer.classList.remove('hidden');
        
        // Add animation class for smooth progress
        if (progress > 0) {
            progressBar.classList.add('progress-bar-animated');
        }
    },

    // Update upload progress
    updateUploadProgress: function(progress) {
        const percentageSpan = document.getElementById('upload-percentage');
        const progressBar = document.getElementById('progress-bar');

        percentageSpan.textContent = `${Math.round(progress)}%`;
        progressBar.style.width = `${progress}%`;
    },



    // Show upload status
    showUploadStatus: function(type, message) {
        const statusContainer = document.getElementById('upload-status');
        const statusIcon = document.getElementById('status-icon');
        const statusMessage = document.getElementById('status-message');

        // Set status content
        statusMessage.textContent = message;

        // Set status styling and icon
        statusContainer.className = 'mt-4 p-4 rounded-md';
        
        switch (type) {
            case 'success':
                statusContainer.classList.add('status-success');
                statusIcon.className = 'fas fa-check-circle text-green-600';
                break;
            case 'error':
                statusContainer.classList.add('status-error');
                statusIcon.className = 'fas fa-exclamation-circle text-red-600';
                break;
            case 'warning':
                statusContainer.classList.add('status-warning');
                statusIcon.className = 'fas fa-exclamation-triangle text-yellow-600';
                break;
            default:
                statusContainer.classList.add('status-info');
                statusIcon.className = 'fas fa-info-circle text-blue-600';
        }

        statusContainer.classList.remove('hidden');

        // Auto-hide success messages after delay
        if (type === 'success') {
            setTimeout(() => {
                statusContainer.classList.add('hidden');
            }, 5000);
        }
    },

    // Reset upload area
    resetUploadArea: function() {
        const fileInput = document.getElementById('file-input');
        const progressContainer = document.getElementById('upload-progress');
        const progressBar = document.getElementById('progress-bar');

        // Reset file input
        fileInput.value = '';

        // Hide progress
        progressContainer.classList.add('hidden');
        progressBar.style.width = '0%';
        progressBar.classList.remove('progress-bar-animated');

        // Reset current upload
        this.currentUpload = null;
    },

    // Get upload statistics
    getUploadStats: function() {
        if (!this.currentUpload) {
            return null;
        }

        const elapsed = Date.now() - this.currentUpload.startTime;
        const fileSize = this.currentUpload.file.size;
        
        return {
            filename: this.currentUpload.file.name,
            fileSize: window.EasyCRM.Utils.formatFileSize(fileSize),
            elapsed: Math.round(elapsed / 1000),
            status: this.currentUpload.status
        };
    },

    // Hide old upload elements when using new status indicator
    hideOldUploadElements: function() {
        const progressContainer = document.getElementById('upload-progress');
        const statusContainer = document.getElementById('upload-status');
        
        if (progressContainer) {
            progressContainer.classList.add('hidden');
        }
        if (statusContainer) {
            statusContainer.classList.add('hidden');
        }
    },

    // Update upload status message (enhanced for status indicator integration)
    updateUploadStatus: function(message) {
        // Update old progress display if visible
        const percentageSpan = document.getElementById('upload-percentage');
        if (percentageSpan) {
            percentageSpan.textContent = message;
        }
        
        // Update status indicator if it's showing
        if (window.EasyCRM.ProcessingStatusIndicator && window.EasyCRM.ProcessingStatusIndicator.isShowing()) {
            const currentStatus = window.EasyCRM.ProcessingStatusIndicator.getCurrentUploadId();
            if (currentStatus) {
                // Update the status indicator with the message
                const messageEl = document.getElementById('status-message');
                if (messageEl) {
                    messageEl.textContent = message;
                }
            }
        }
    },

    // Cancel current upload (enhanced for status indicator integration)
    cancelUpload: function() {
        if (this.currentUpload && this.currentUpload.status === 'uploading') {
            // Cancel via status indicator if available
            if (window.EasyCRM.ProcessingStatusIndicator && window.EasyCRM.ProcessingStatusIndicator.isShowing()) {
                window.EasyCRM.ProcessingStatusIndicator.cancelProcessing();
            } else {
                // Fallback to old method
                this.currentUpload.status = 'cancelled';
                this.showUploadStatus('warning', 'Upload cancelled');
            }
            this.resetUploadArea();
        }
    },

    // Start tracking processing status
    startProcessingStatusTracking: function(statusId, filename) {
        this.currentUpload.statusId = statusId;
        this.currentUpload.filename = filename;
        
        // Show processing status
        this.showProcessingStatus(statusId, filename);
        
        // Start polling for status updates
        this.pollProcessingStatus(statusId);
    },

    // Start tracking processing status by file key
    startProcessingStatusTrackingByFile: function(fileKey, filename) {
        this.currentUpload.fileKey = fileKey;
        this.currentUpload.filename = filename;
        
        // Show initial processing status
        this.showProcessingStatusByFile(filename);
        
        // Start polling for status by file key
        this.pollProcessingStatusByFile(fileKey, filename);
    },

    // Show processing status UI
    showProcessingStatus: function(statusId, filename) {
        const statusContainer = document.getElementById('upload-status');
        const statusIcon = document.getElementById('status-icon');
        const statusMessage = document.getElementById('status-message');

        // Create processing status HTML
        statusMessage.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <div class="font-medium">Processing ${filename}</div>
                    <div class="text-sm text-gray-600 mt-1" id="processing-details">
                        Initializing processing...
                    </div>
                </div>
                <div class="ml-4">
                    <div class="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div id="processing-progress" class="h-full bg-blue-500 transition-all duration-300" style="width: 0%"></div>
                    </div>
                    <div class="text-xs text-gray-500 mt-1 text-center" id="processing-percentage">0%</div>
                </div>
            </div>
        `;

        // Set status styling
        statusContainer.className = 'mt-4 p-4 rounded-md status-info';
        statusIcon.className = 'fas fa-spinner fa-spin text-blue-600';
        statusContainer.classList.remove('hidden');
    },

    // Poll processing status
    pollProcessingStatus: function(statusId) {
        const pollInterval = setInterval(async () => {
            try {
                const status = await window.EasyCRM.API.processing.getStatus(statusId);
                
                if (status) {
                    this.updateProcessingStatus(status);
                    
                    // Stop polling if processing is complete or failed
                    if (status.status === 'completed' || status.status === 'failed') {
                        clearInterval(pollInterval);
                        this.handleProcessingComplete(status);
                    }
                } else {
                    // Status not found, stop polling
                    clearInterval(pollInterval);
                    this.handleProcessingError('Processing status not found');
                }
            } catch (error) {
                console.error('Error polling processing status:', error);
                // Continue polling on error, but limit retries
                if (!this.pollRetries) this.pollRetries = 0;
                this.pollRetries++;
                
                if (this.pollRetries > 10) {
                    clearInterval(pollInterval);
                    this.handleProcessingError('Failed to get processing status');
                }
            }
        }, 2000); // Poll every 2 seconds

        // Store interval ID for cleanup
        this.currentUpload.pollInterval = pollInterval;
    },

    // Update processing status display
    updateProcessingStatus: function(status) {
        const detailsElement = document.getElementById('processing-details');
        const progressElement = document.getElementById('processing-progress');
        const percentageElement = document.getElementById('processing-percentage');

        if (detailsElement) {
            const details = [];
            if (status.processedBatches > 0) {
                details.push(`${status.processedBatches}/${status.totalBatches} batches processed`);
            }
            if (status.createdLeads > 0) {
                details.push(`${status.createdLeads} leads created`);
            }
            if (status.updatedLeads > 0) {
                details.push(`${status.updatedLeads} leads updated`);
            }
            
            detailsElement.textContent = details.length > 0 ? details.join(', ') : 'Processing...';
        }

        if (progressElement && percentageElement) {
            const progress = status.progressPercentage || 0;
            progressElement.style.width = `${progress}%`;
            percentageElement.textContent = `${Math.round(progress)}%`;
        }
    },

    // Handle processing completion
    handleProcessingComplete: function(status) {
        const statusContainer = document.getElementById('upload-status');
        const statusIcon = document.getElementById('status-icon');
        const statusMessage = document.getElementById('status-message');

        if (status.status === 'completed') {
            // Show success
            statusContainer.className = 'mt-4 p-4 rounded-md status-success';
            statusIcon.className = 'fas fa-check-circle text-green-600';
            
            const totalLeads = (status.createdLeads || 0) + (status.updatedLeads || 0);
            statusMessage.innerHTML = `
                <div>
                    <div class="font-medium">Processing completed successfully!</div>
                    <div class="text-sm text-gray-600 mt-1">
                        ${totalLeads} leads processed (${status.createdLeads || 0} new, ${status.updatedLeads || 0} updated)
                    </div>
                </div>
            `;

            // Refresh leads table
            setTimeout(() => {
                if (window.EasyCRM.Leads) {
                    window.EasyCRM.Leads.refreshLeads();
                }
            }, 1000);

            // Auto-hide after delay
            setTimeout(() => {
                statusContainer.classList.add('hidden');
                this.resetUploadArea();
            }, 5000);

        } else if (status.status === 'failed') {
            // Show error
            statusContainer.className = 'mt-4 p-4 rounded-md status-error';
            statusIcon.className = 'fas fa-exclamation-circle text-red-600';
            
            statusMessage.innerHTML = `
                <div>
                    <div class="font-medium">Processing failed</div>
                    <div class="text-sm text-gray-600 mt-1">
                        ${status.errorMessage || 'An error occurred during processing'}
                    </div>
                </div>
            `;
        }

        // Clean up
        this.pollRetries = 0;
        if (this.currentUpload && this.currentUpload.pollInterval) {
            clearInterval(this.currentUpload.pollInterval);
        }
    },

    // Handle processing error
    handleProcessingError: function(errorMessage) {
        this.showUploadStatus('warning', `Processing status unavailable: ${errorMessage}. Please check the leads table manually.`);
        
        // Fallback to refreshing leads table
        setTimeout(() => {
            if (window.EasyCRM.Leads) {
                window.EasyCRM.Leads.refreshLeads();
            }
        }, 3000);

        // Clean up
        this.pollRetries = 0;
        this.fileSearchRetries = 0;
        if (this.currentUpload && this.currentUpload.pollInterval) {
            clearInterval(this.currentUpload.pollInterval);
        }
    },

    // Show processing status UI for file-based tracking
    showProcessingStatusByFile: function(filename) {
        const statusContainer = document.getElementById('upload-status');
        const statusIcon = document.getElementById('status-icon');
        const statusMessage = document.getElementById('status-message');

        // Create processing status HTML
        statusMessage.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <div class="font-medium">Processing ${filename}</div>
                    <div class="text-sm text-gray-600 mt-1" id="processing-details">
                        Waiting for processing to start...
                    </div>
                </div>
                <div class="ml-4">
                    <div class="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div id="processing-progress" class="h-full bg-blue-500 transition-all duration-300" style="width: 0%"></div>
                    </div>
                    <div class="text-xs text-gray-500 mt-1 text-center" id="processing-percentage">0%</div>
                </div>
            </div>
        `;

        // Set status styling
        statusContainer.className = 'mt-4 p-4 rounded-md status-info';
        statusIcon.className = 'fas fa-spinner fa-spin text-blue-600';
        statusContainer.classList.remove('hidden');
    },

    // Poll processing status by file key
    pollProcessingStatusByFile: function(fileKey, filename) {
        let foundStatus = false;
        
        const pollInterval = setInterval(async () => {
            try {
                // Get recent processing statuses and look for our file
                const recentStatuses = await window.EasyCRM.API.processing.getRecentStatuses(20);
                
                if (recentStatuses && recentStatuses.statuses) {
                    // Look for a status matching our file key
                    const matchingStatus = recentStatuses.statuses.find(status => 
                        status.fileKey === fileKey || status.sourceFile === filename
                    );
                    
                    if (matchingStatus) {
                        foundStatus = true;
                        
                        // Switch to regular status tracking
                        clearInterval(pollInterval);
                        this.currentUpload.statusId = matchingStatus.statusId;
                        this.pollProcessingStatus(matchingStatus.statusId);
                        
                        // Update the UI with the found status
                        this.updateProcessingStatus(matchingStatus);
                        
                        return;
                    }
                }
                
                // If we haven't found the status yet, continue waiting
                if (!foundStatus) {
                    const detailsElement = document.getElementById('processing-details');
                    if (detailsElement) {
                        detailsElement.textContent = 'Waiting for processing to start...';
                    }
                }
                
                // Limit the search time to avoid infinite polling
                if (!this.fileSearchRetries) this.fileSearchRetries = 0;
                this.fileSearchRetries++;
                
                if (this.fileSearchRetries > 30) { // 30 * 2 seconds = 1 minute
                    clearInterval(pollInterval);
                    this.handleProcessingError('Processing status not found within expected time');
                }
                
            } catch (error) {
                console.error('Error polling for processing status by file:', error);
                
                if (!this.fileSearchRetries) this.fileSearchRetries = 0;
                this.fileSearchRetries++;
                
                if (this.fileSearchRetries > 10) {
                    clearInterval(pollInterval);
                    this.handleProcessingError('Failed to find processing status');
                }
            }
        }, 2000); // Poll every 2 seconds

        // Store interval ID for cleanup
        this.currentUpload.pollInterval = pollInterval;
    },

    // Handle upload cancellation (called from status indicator)
    handleUploadCancellation: function() {
        if (this.currentUpload) {
            this.currentUpload.status = 'cancelled';
            
            // Stop any ongoing polling
            if (this.currentUpload.pollInterval) {
                clearInterval(this.currentUpload.pollInterval);
                this.currentUpload.pollInterval = null;
            }
            
            // Reset upload area
            this.resetUploadArea();
            
            console.log('Upload cancelled by user');
        }
    },

    // Handle processing completion (called when status indicator completes)
    handleProcessingCompletion: function(status) {
        if (status && status.status === 'completed') {
            // Trigger lead table refresh
            setTimeout(() => {
                if (window.EasyCRM.Leads && window.EasyCRM.Leads.refreshLeads) {
                    console.log('Refreshing lead table after processing completion');
                    window.EasyCRM.Leads.refreshLeads();
                    
                    // Show success toast
                    if (window.EasyCRM.Utils && window.EasyCRM.Utils.showToast) {
                        const totalLeads = (status.progress?.processedLeads || 0);
                        window.EasyCRM.Utils.showToast(
                            `Successfully processed ${totalLeads} leads!`, 
                            'success'
                        );
                    }
                }
            }, 1000);
        }
        
        // Clean up upload state
        this.resetUploadArea();
    },

    // Enhanced error handling for upload workflow
    handleUploadError: function(error, stage = 'upload') {
        console.error(`Upload error during ${stage}:`, error);
        
        let errorMessage = `${stage} failed: ${error.message}`;
        
        // Categorize errors for better user experience
        if (error.message.includes('timeout')) {
            errorMessage = `${stage} timed out. Please check your connection and try again.`;
        } else if (error.message.includes('Network')) {
            errorMessage = `Network error during ${stage}. Please check your connection.`;
        } else if (error.message.includes('401') || error.message.includes('403')) {
            errorMessage = 'Authentication failed. Please refresh the page and log in again.';
        }
        
        // Show error in status indicator if available
        if (window.EasyCRM.ProcessingStatusIndicator && window.EasyCRM.ProcessingStatusIndicator.isShowing()) {
            window.EasyCRM.ProcessingStatusIndicator.showError(errorMessage);
        } else {
            this.showUploadStatus('error', errorMessage);
        }
        
        // Update current upload status
        if (this.currentUpload) {
            this.currentUpload.status = 'error';
        }
    }
};