// Processing Status Indicator Component
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.ProcessingStatusIndicator = {
    // Component state
    uploadId: null,
    pollInterval: null,
    isVisible: false,
    retryCount: 0,
    maxRetries: 6,
    pollIntervalMs: 10000,
    pollingStartTime: null,
    
    // Error state management
    errorState: {
        hasError: false,
        errorType: null,
        errorMessage: null,
        recoveryOptions: null,
        persistedErrors: new Map() // Store errors by uploadId for recovery
    },
    
    // Polling configuration
    config: {
        baseRetryDelay: 1000,      // Base delay for exponential backoff (1 second)
        maxRetryDelay: 30000,      // Maximum retry delay (30 seconds)
        pollInterval: 10000,       // Normal polling interval (10 seconds) - reduced from 2s to save API costs
        maxRetries: 6,             // Maximum number of retry attempts (reduced from 10 to limit total time)
        authRetryDelay: 5000,      // Delay before retrying after auth refresh (5 seconds)
        maxPollingDuration: 300000 // Maximum polling duration (5 minutes) - stop polling after this time
    },
    
    // Initialize the component
    init: function() {
        this.createStatusContainer();
        this.attachEventHandlers();
    },

    // Create the status container HTML
    createStatusContainer: function() {
        // Check if container already exists
        if (document.getElementById('processing-status-indicator')) {
            return;
        }

        const container = document.createElement('div');
        container.id = 'processing-status-indicator';
        container.className = 'fixed top-4 right-4 max-w-md w-full mx-4 bg-white rounded-lg shadow-lg border z-50 hidden';
        
        container.innerHTML = `
            <div class="p-4">
                <!-- Header -->
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center">
                        <div id="status-spinner" class="mr-3">
                            <i class="fas fa-spinner fa-spin text-blue-600"></i>
                        </div>
                        <h3 id="status-title" class="text-lg font-medium text-gray-900">Processing File</h3>
                    </div>
                    <button type="button" id="status-close" class="text-gray-400 hover:text-gray-600 hidden" title="Close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>

                <!-- Status Message -->
                <div id="status-message" class="text-sm text-gray-600 mb-3">
                    Initializing processing...
                </div>

                <!-- Progress Bar -->
                <div id="progress-container" class="mb-3">
                    <div class="flex items-center justify-between mb-1">
                        <span id="progress-label" class="text-xs text-gray-500">Progress</span>
                        <span id="progress-percentage" class="text-xs text-gray-500">0%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div id="progress-bar" 
                             class="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out" 
                             style="width: 0%"></div>
                    </div>
                </div>

                <!-- Details -->
                <div id="status-details" class="text-xs text-gray-500 mb-3">
                    <!-- Processing details will be shown here -->
                </div>

                <!-- Actions -->
                <div id="status-actions" class="flex items-center justify-between">
                    <div id="estimated-time" class="text-xs text-gray-500">
                        <!-- Estimated time will be shown here -->
                    </div>
                    <button type="button" id="cancel-processing" 
                            class="text-xs text-red-600 hover:text-red-800 hidden">
                        Cancel Processing
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(container);
    },

    // Attach event handlers
    attachEventHandlers: function() {
        const closeBtn = document.getElementById('status-close');
        const cancelBtn = document.getElementById('cancel-processing');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.hide();
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                this.cancelProcessing();
            });
        }
    },

    // Show the status indicator
    show: function(uploadId, initialStatus = 'uploading', fileName = '') {
        this.uploadId = uploadId;
        this.isVisible = true;
        this.retryCount = 0;
        this.pollingStartTime = Date.now();

        const container = document.getElementById('processing-status-indicator');
        if (!container) {
            this.createStatusContainer();
        }

        // Update initial status
        this.render({
            status: initialStatus,
            stage: 'file_upload',
            progress: {
                percentage: 0,
                totalBatches: 0,
                completedBatches: 0,
                totalLeads: 0,
                processedLeads: 0
            },
            metadata: {
                fileName: fileName
            }
        });

        // Show container with animation
        container.classList.remove('hidden');
        container.style.opacity = '0';
        container.style.transform = 'translateY(-20px)';
        
        // Animate in
        setTimeout(() => {
            container.style.transition = 'opacity 0.3s ease-out, transform 0.3s ease-out';
            container.style.opacity = '1';
            container.style.transform = 'translateY(0)';
        }, 10);

        // Start polling for status updates
        this.startPolling();
    },

    // Hide the status indicator
    hide: function() {
        const container = document.getElementById('processing-status-indicator');
        if (!container) return;

        this.stopPolling();
        this.isVisible = false;

        // Animate out
        container.style.transition = 'opacity 0.3s ease-in, transform 0.3s ease-in';
        container.style.opacity = '0';
        container.style.transform = 'translateY(-20px)';

        setTimeout(() => {
            container.classList.add('hidden');
        }, 300);
    },

    // Render status data
    render: function(statusData) {
        if (!statusData) return;

        const titleEl = document.getElementById('status-title');
        const messageEl = document.getElementById('status-message');
        const progressBarEl = document.getElementById('progress-bar');
        const progressPercentageEl = document.getElementById('progress-percentage');
        const progressLabelEl = document.getElementById('progress-label');
        const detailsEl = document.getElementById('status-details');
        const spinnerEl = document.getElementById('status-spinner');
        const closeBtn = document.getElementById('status-close');
        const cancelBtn = document.getElementById('cancel-processing');
        const estimatedTimeEl = document.getElementById('estimated-time');

        // Update title and icon based on status
        this.updateStatusIcon(statusData.status, spinnerEl);
        this.updateTitle(statusData.status, statusData.metadata?.fileName, titleEl);
        this.updateMessage(statusData, messageEl);
        this.updateProgress(statusData.progress, progressBarEl, progressPercentageEl, progressLabelEl);
        this.updateDetails(statusData, detailsEl);
        this.updateEstimatedTime(statusData, estimatedTimeEl);

        // Show/hide action buttons based on status
        if (statusData.status === 'completed' || statusData.status === 'error' || statusData.status === 'cancelled') {
            closeBtn.classList.remove('hidden');
            cancelBtn.classList.add('hidden');
            
            // Auto-hide after 3 seconds for completed status
            if (statusData.status === 'completed') {
                setTimeout(() => {
                    if (this.isVisible) {
                        this.hide();
                    }
                }, 3000);
            }
        } else {
            closeBtn.classList.add('hidden');
            cancelBtn.classList.remove('hidden');
        }
    },

    // Update status icon
    updateStatusIcon: function(status, spinnerEl) {
        if (!spinnerEl) return;

        let iconClass = '';
        let colorClass = '';

        switch (status) {
            case 'uploading':
                iconClass = 'fas fa-cloud-upload-alt fa-pulse';
                colorClass = 'text-blue-600';
                break;
            case 'uploaded':
                iconClass = 'fas fa-check text-green-600';
                colorClass = 'text-green-600';
                break;
            case 'processing':
                iconClass = 'fas fa-cogs fa-spin';
                colorClass = 'text-blue-600';
                break;
            case 'completed':
                iconClass = 'fas fa-check-circle';
                colorClass = 'text-green-600';
                break;
            case 'error':
                iconClass = 'fas fa-exclamation-circle';
                colorClass = 'text-red-600';
                break;
            case 'cancelled':
                iconClass = 'fas fa-times-circle';
                colorClass = 'text-yellow-600';
                break;
            default:
                iconClass = 'fas fa-spinner fa-spin';
                colorClass = 'text-blue-600';
        }

        spinnerEl.innerHTML = `<i class="${iconClass} ${colorClass}"></i>`;
    },

    // Update title
    updateTitle: function(status, fileName, titleEl) {
        if (!titleEl) return;

        let title = '';
        switch (status) {
            case 'uploading':
                title = 'Uploading File';
                break;
            case 'uploaded':
                title = 'File Uploaded';
                break;
            case 'processing':
                title = 'Processing Leads';
                break;
            case 'completed':
                title = 'Processing Complete';
                break;
            case 'error':
                title = 'Processing Failed';
                break;
            case 'cancelled':
                title = 'Processing Cancelled';
                break;
            default:
                title = 'Processing File';
        }

        if (fileName) {
            title += ` - ${fileName}`;
        }

        titleEl.textContent = title;
    },

    // Update status message
    updateMessage: function(statusData, messageEl) {
        if (!messageEl) return;

        let message = '';
        switch (statusData.status) {
            case 'uploading':
                message = 'Uploading your file to the server...';
                break;
            case 'uploaded':
                message = 'File uploaded successfully. Starting processing...';
                break;
            case 'processing':
                if (statusData.stage === 'file_processing') {
                    message = 'Reading and validating file contents...';
                } else if (statusData.stage === 'batch_processing') {
                    const progress = statusData.progress;
                    if (progress && progress.totalBatches > 0) {
                        message = `Processing batch ${progress.completedBatches || 0} of ${progress.totalBatches}...`;
                    } else {
                        message = 'Processing leads through AI standardization...';
                    }
                } else {
                    message = 'Processing your leads...';
                }
                break;
            case 'completed':
                const totalLeads = (statusData.progress?.processedLeads || 0);
                const createdLeads = (statusData.progress?.createdLeads || 0);
                const updatedLeads = (statusData.progress?.updatedLeads || 0);
                
                if (createdLeads > 0 && updatedLeads > 0) {
                    message = `Successfully processed ${totalLeads} leads! (${createdLeads} new, ${updatedLeads} updated)`;
                } else if (totalLeads > 0) {
                    message = `Successfully processed ${totalLeads} leads!`;
                } else {
                    message = 'Processing completed successfully!';
                }
                break;
            case 'error':
                message = statusData.error?.message || 'An error occurred during processing';
                break;
            case 'cancelled':
                message = 'Processing was cancelled by user';
                break;
            default:
                message = 'Processing...';
        }

        messageEl.textContent = message;
    },

    // Update progress bar
    updateProgress: function(progress, progressBarEl, progressPercentageEl, progressLabelEl) {
        if (!progress || !progressBarEl || !progressPercentageEl) return;

        const percentage = Math.min(Math.max(progress.percentage || 0, 0), 100);
        
        progressBarEl.style.width = `${percentage}%`;
        progressPercentageEl.textContent = `${Math.round(percentage)}%`;

        // Update progress bar color based on percentage
        if (percentage >= 100) {
            progressBarEl.className = progressBarEl.className.replace('bg-blue-600', 'bg-green-600');
        } else {
            progressBarEl.className = progressBarEl.className.replace('bg-green-600', 'bg-blue-600');
        }

        // Update progress label
        if (progressLabelEl) {
            if (progress.totalBatches > 0) {
                progressLabelEl.textContent = `Batch ${progress.completedBatches || 0} of ${progress.totalBatches}`;
            } else {
                progressLabelEl.textContent = 'Progress';
            }
        }
    },

    // Update details section
    updateDetails: function(statusData, detailsEl) {
        if (!detailsEl) return;

        const details = [];
        const progress = statusData.progress;

        if (progress) {
            if (progress.totalBatches > 0) {
                details.push(`${progress.completedBatches || 0}/${progress.totalBatches} batches processed`);
            }
            if (progress.processedLeads > 0) {
                details.push(`${progress.processedLeads} leads processed`);
            }
            if (progress.totalLeads > 0 && progress.processedLeads !== progress.totalLeads) {
                details.push(`${progress.totalLeads} total leads`);
            }
            
            // Show processing rate for longer operations (showEstimates is now 1/0 instead of true/false)
            if (progress.processingRate && progress.showEstimates === 1 && statusData.status === 'processing') {
                const rate = progress.processingRate;
                if (rate >= 1) {
                    details.push(`${rate.toFixed(1)} batches/sec`);
                } else {
                    const batchesPerMinute = (rate * 60).toFixed(1);
                    details.push(`${batchesPerMinute} batches/min`);
                }
            }
        }

        if (statusData.metadata?.fileSize) {
            details.push(`File size: ${window.EasyCRM.Utils.formatFileSize(statusData.metadata.fileSize)}`);
        }

        detailsEl.textContent = details.length > 0 ? details.join(' • ') : '';
    },

    // Update estimated time
    updateEstimatedTime: function(statusData, estimatedTimeEl) {
        if (!estimatedTimeEl) return;

        // Check if we should show estimates (only for longer operations) - showEstimates is now 1/0 instead of true/false
        const showEstimates = statusData.progress?.showEstimates === 1;
        const isProcessing = statusData.status === 'processing';
        
        if (isProcessing && showEstimates) {
            // Use progress-based estimates if available
            if (statusData.progress?.estimatedRemainingSeconds) {
                const remainingSeconds = statusData.progress.estimatedRemainingSeconds;
                const formattedTime = this.formatTimeRemaining(remainingSeconds);
                estimatedTimeEl.textContent = `Est. ${formattedTime} remaining`;
                return;
            }
            
            // Fallback to metadata-based estimates
            if (statusData.progress?.estimatedCompletion) {
                const estimatedTime = new Date(statusData.progress.estimatedCompletion);
                const now = new Date();
                const remainingMs = estimatedTime.getTime() - now.getTime();

                if (remainingMs > 0) {
                    const remainingSeconds = Math.ceil(remainingMs / 1000);
                    const formattedTime = this.formatTimeRemaining(remainingSeconds);
                    estimatedTimeEl.textContent = `Est. ${formattedTime} remaining`;
                } else {
                    estimatedTimeEl.textContent = 'Finishing up...';
                }
                return;
            }
            
            // Legacy metadata support
            if (statusData.metadata?.estimatedCompletion) {
                const estimatedTime = new Date(statusData.metadata.estimatedCompletion);
                const now = new Date();
                const remainingMs = estimatedTime.getTime() - now.getTime();

                if (remainingMs > 0) {
                    const remainingSeconds = Math.ceil(remainingMs / 1000);
                    const formattedTime = this.formatTimeRemaining(remainingSeconds);
                    estimatedTimeEl.textContent = `Est. ${formattedTime} remaining`;
                } else {
                    estimatedTimeEl.textContent = 'Finishing up...';
                }
                return;
            }
        }
        
        // Clear estimated time if not applicable
        estimatedTimeEl.textContent = '';
    },

    // Handle polling timeout (when max polling duration is exceeded)
    handlePollingTimeout: function() {
        console.log('Polling timeout reached - stopping to avoid high API costs');
        
        const messageEl = document.getElementById('status-message');
        const closeBtn = document.getElementById('status-close');
        const cancelBtn = document.getElementById('cancel-processing');
        
        if (messageEl) {
            messageEl.textContent = 'Status updates stopped to avoid high costs. Processing may still be running in the background.';
            messageEl.className = 'text-sm text-yellow-600 mb-3';
        }
        
        // Show close button and hide cancel button
        if (closeBtn) closeBtn.classList.remove('hidden');
        if (cancelBtn) cancelBtn.classList.add('hidden');
        
        // Update title to indicate timeout
        const titleEl = document.getElementById('status-title');
        if (titleEl) {
            titleEl.textContent = 'Status Updates Paused';
        }
        
        // Update icon to show warning
        const spinnerEl = document.getElementById('status-spinner');
        if (spinnerEl) {
            spinnerEl.innerHTML = '<i class="fas fa-clock text-yellow-600"></i>';
        }
    },

    // Format time remaining in a user-friendly way
    formatTimeRemaining: function(totalSeconds) {
        if (totalSeconds < 60) {
            return `${totalSeconds}s`;
        } else if (totalSeconds < 3600) {
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = totalSeconds % 60;
            if (seconds > 0) {
                return `${minutes}m ${seconds}s`;
            } else {
                return `${minutes}m`;
            }
        } else {
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            if (minutes > 0) {
                return `${hours}h ${minutes}m`;
            } else {
                return `${hours}h`;
            }
        }
    },

    // Start polling for status updates
    startPolling: function() {
        if (!this.uploadId) {
            console.warn('Cannot start polling: no uploadId available');
            return;
        }

        console.log(`Starting status polling for uploadId: ${this.uploadId} (interval: ${this.config.pollInterval}ms)`);
        
        // Clear any existing interval to prevent multiple polling
        this.stopPolling();
        
        // Start polling with error handling
        this.pollInterval = setInterval(async () => {
            // Skip polling if component is no longer visible
            if (!this.isVisible) {
                console.log('Component no longer visible, stopping polling');
                this.stopPolling();
                return;
            }

            // Check if maximum polling duration has been exceeded
            const pollingDuration = Date.now() - this.pollingStartTime;
            if (pollingDuration > this.config.maxPollingDuration) {
                console.log('Maximum polling duration exceeded, stopping polling to avoid high API costs');
                this.stopPolling();
                this.handlePollingTimeout();
                return;
            }

            try {
                await this.fetchStatus();
            } catch (error) {
                console.error('Error during status polling:', error);
                this.handlePollingError(error);
            }
        }, this.config.pollInterval);

        console.log('Status polling started successfully');
    },

    // Stop polling
    stopPolling: function() {
        if (this.pollInterval) {
            console.log('Stopping status polling');
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    },

    // Fetch status from API with retry logic
    fetchStatus: async function() {
        if (!this.uploadId) {
            console.warn('No uploadId available for status polling');
            return;
        }

        try {
            console.log(`Fetching status for uploadId: ${this.uploadId}`);
            
            // Make API call to get processing status
            const status = await window.EasyCRM.API.processing.getStatus(this.uploadId);
            
            if (status) {
                console.log('Status fetched successfully:', status);
                this.handleSuccessfulStatusFetch(status);
            } else {
                throw new Error('Status not found - empty response from API');
            }
        } catch (error) {
            console.error('Error fetching status:', error);
            throw error;
        }
    },

    // Validate status response structure
    validateStatusResponse: function(status) {
        if (!status || typeof status !== 'object') {
            throw new Error('Invalid status response: not an object');
        }

        if (!status.status || typeof status.status !== 'string') {
            throw new Error('Invalid status response: missing or invalid status field');
        }

        const validStatuses = ['uploading', 'uploaded', 'processing', 'completed', 'error', 'cancelled'];
        if (!validStatuses.includes(status.status)) {
            throw new Error(`Invalid status response: unknown status '${status.status}'`);
        }

        return true;
    },

    // Handle successful status fetch
    handleSuccessfulStatusFetch: function(status) {
        try {
            // Validate the status response structure
            this.validateStatusResponse(status);
            
            // Reset retry count on successful fetch
            this.retryCount = 0;
            
            // Clear any existing error state
            this.clearErrorState();
            
            // Handle server-side error status
            if (status.status === 'error') {
                this.handleServerError(status);
                return;
            }
            
            // Update the UI with the new status
            this.render(status);

            // Check if processing is complete or failed
            const finalStatuses = ['completed', 'error', 'cancelled'];
            if (finalStatuses.includes(status.status)) {
                console.log(`Processing finished with status: ${status.status}`);
                this.stopPolling();
                this.handleProcessingComplete(status);
            }
        } catch (validationError) {
            console.error('Status response validation failed:', validationError);
            throw new Error(`Invalid status response: ${validationError.message}`);
        }
    },

    // Handle server-side error status
    handleServerError: function(status) {
        console.error('Server-side processing error:', status.error);
        
        const error = status.error || {};
        const errorMessage = error.message || 'An error occurred during processing';
        const errorCode = error.code || 'PROCESSING_ERROR';
        const recoverable = error.recoverable || false;
        
        let recoveryOptions = null;
        
        if (recoverable) {
            recoveryOptions = {
                available: true,
                options: []
            };
            
            // Add retry option for recoverable errors
            if (error.retryAfter) {
                recoveryOptions.options.push({
                    type: 'retry',
                    label: 'Retry Processing',
                    description: 'Retry the processing operation',
                    retryAfter: error.retryAfter
                });
            }
            
            // Add specific recovery options based on error code
            if (errorCode === 'VALIDATION_ERROR') {
                recoveryOptions.options.push({
                    type: 'reupload',
                    label: 'Upload Corrected File',
                    description: 'Please correct the file format and upload again'
                });
            }
            
            // Always add manual recovery option
            recoveryOptions.options.push({
                type: 'manual',
                label: 'Contact Support',
                description: 'Contact support for assistance'
            });
        } else {
            recoveryOptions = {
                available: false,
                message: 'This error cannot be automatically recovered. Please try uploading your file again.'
            };
        }
        
        this.setErrorState('processing', errorMessage, recoveryOptions);
        this.stopPolling();
    },

    // Handle polling errors with exponential backoff and enhanced error state management
    handlePollingError: function(error) {
        const errorType = this.categorizeError(error);
        this.retryCount++;
        
        console.warn(`Polling error (attempt ${this.retryCount}/${this.config.maxRetries}, type: ${errorType}):`, error);

        // Handle authentication errors immediately
        if (errorType === 'authentication') {
            console.log('Authentication error detected during polling');
            this.setErrorState('authentication', 'Your session has expired. Please refresh the page and log in again.');
            this.handleAuthError();
            return;
        }

        // Check if max retries reached
        if (this.retryCount >= this.config.maxRetries) {
            console.error('Max retries reached, stopping polling');
            this.stopPolling();
            
            let errorMessage = 'Unable to get processing status after multiple attempts.';
            let recoveryOptions = null;
            
            if (errorType === 'network') {
                errorMessage = 'Network connection issues prevented status updates. Please check your connection.';
                recoveryOptions = {
                    available: true,
                    options: [
                        {
                            type: 'retry',
                            label: 'Retry Now',
                            description: 'Retry getting status updates'
                        }
                    ]
                };
            } else if (errorType === 'not_found') {
                errorMessage = 'Processing status not found. The upload may have expired or completed.';
                recoveryOptions = {
                    available: true,
                    options: [
                        {
                            type: 'reupload',
                            label: 'Upload New File',
                            description: 'Upload a new file to start processing'
                        }
                    ]
                };
            } else {
                recoveryOptions = {
                    available: true,
                    options: [
                        {
                            type: 'retry',
                            label: 'Retry',
                            description: 'Retry getting status updates'
                        },
                        {
                            type: 'manual',
                            label: 'Get Help',
                            description: 'Contact support for assistance'
                        }
                    ]
                };
            }
            
            this.setErrorState(errorType, errorMessage, recoveryOptions);
            return;
        }

        // Calculate exponential backoff delay based on error type
        let baseDelay = this.config.baseRetryDelay;
        
        // Use longer delays for network errors
        if (errorType === 'network') {
            baseDelay = this.config.baseRetryDelay * 2;
        }
        
        const exponentialDelay = baseDelay * Math.pow(2, this.retryCount - 1);
        const delay = Math.min(exponentialDelay, this.config.maxRetryDelay);
        
        console.log(`Retrying in ${delay}ms (attempt ${this.retryCount}/${this.config.maxRetries}, error type: ${errorType})`);

        // Show temporary error state for transient errors
        if (this.retryCount > 3) {
            const tempMessage = `Connection issues detected. Retrying... (attempt ${this.retryCount}/${this.config.maxRetries})`;
            this.showTemporaryError(tempMessage);
        }

        // Clear current polling interval
        this.stopPolling();

        // Set up retry with exponential backoff
        setTimeout(() => {
            if (this.isVisible && this.uploadId) {
                console.log('Retrying status fetch after backoff delay');
                this.clearTemporaryError();
                // Restart polling with normal interval
                this.startPolling();
            }
        }, delay);
    },

    // Show temporary error message (for transient errors during retry)
    showTemporaryError: function(message) {
        const messageEl = document.getElementById('status-message');
        if (messageEl) {
            messageEl.textContent = message;
            messageEl.className = 'text-sm text-yellow-600 mb-3';
        }
    },

    // Clear temporary error message
    clearTemporaryError: function() {
        const messageEl = document.getElementById('status-message');
        if (messageEl) {
            messageEl.className = 'text-sm text-gray-600 mb-3';
        }
    },

    // Check if error is authentication-related
    isAuthenticationError: function(error) {
        if (!error) return false;
        
        const errorMessage = error.message || '';
        const errorString = errorMessage.toLowerCase();
        
        return (
            errorString.includes('401') ||
            errorString.includes('403') ||
            errorString.includes('unauthorized') ||
            errorString.includes('forbidden') ||
            errorString.includes('authentication') ||
            errorString.includes('session expired') ||
            errorString.includes('token')
        );
    },

    // Check if error is network-related
    isNetworkError: function(error) {
        if (!error) return false;
        
        const errorMessage = error.message || '';
        const errorString = errorMessage.toLowerCase();
        
        return (
            errorString.includes('network') ||
            errorString.includes('timeout') ||
            errorString.includes('connection') ||
            errorString.includes('fetch') ||
            error.name === 'AbortError' ||
            error.name === 'TypeError'
        );
    },

    // Categorize error type for appropriate handling
    categorizeError: function(error) {
        if (this.isAuthenticationError(error)) {
            return 'authentication';
        } else if (this.isNetworkError(error)) {
            return 'network';
        } else if (error.message && error.message.includes('Status not found')) {
            return 'not_found';
        } else {
            return 'unknown';
        }
    },

    // Enhanced error state management
    setErrorState: function(errorType, errorMessage, recoveryOptions = null) {
        this.errorState.hasError = true;
        this.errorState.errorType = errorType;
        this.errorState.errorMessage = errorMessage;
        this.errorState.recoveryOptions = recoveryOptions;
        
        // Persist error for this upload
        if (this.uploadId) {
            this.errorState.persistedErrors.set(this.uploadId, {
                type: errorType,
                message: errorMessage,
                timestamp: new Date().toISOString(),
                recoveryOptions: recoveryOptions
            });
        }
        
        this.renderErrorState();
    },

    // Clear error state
    clearErrorState: function() {
        this.errorState.hasError = false;
        this.errorState.errorType = null;
        this.errorState.errorMessage = null;
        this.errorState.recoveryOptions = null;
        
        // Keep persisted errors for potential recovery
        this.hideErrorUI();
    },

    // Get persisted error for upload
    getPersistedError: function(uploadId) {
        return this.errorState.persistedErrors.get(uploadId);
    },

    // Clear persisted error
    clearPersistedError: function(uploadId) {
        this.errorState.persistedErrors.delete(uploadId);
    },

    // Render error state in UI
    renderErrorState: function() {
        const container = document.getElementById('processing-status-indicator');
        if (!container) return;

        const errorContainer = this.getOrCreateErrorContainer();
        const errorType = this.errorState.errorType;
        const errorMessage = this.errorState.errorMessage;
        const recoveryOptions = this.errorState.recoveryOptions;

        // Update error icon and styling
        const spinnerEl = document.getElementById('status-spinner');
        if (spinnerEl) {
            spinnerEl.innerHTML = '<i class="fas fa-exclamation-triangle text-red-600"></i>';
        }

        // Update title
        const titleEl = document.getElementById('status-title');
        if (titleEl) {
            titleEl.textContent = this.getErrorTitle(errorType);
        }

        // Update error message
        const messageEl = document.getElementById('error-message');
        if (messageEl) {
            messageEl.textContent = errorMessage;
        }

        // Show recovery options if available
        this.renderRecoveryOptions(recoveryOptions);

        // Show error container
        errorContainer.classList.remove('hidden');
        
        // Hide progress elements
        const progressContainer = document.getElementById('progress-container');
        if (progressContainer) {
            progressContainer.classList.add('hidden');
        }
    },

    // Get or create error container
    getOrCreateErrorContainer: function() {
        let errorContainer = document.getElementById('error-container');
        if (!errorContainer) {
            const container = document.getElementById('processing-status-indicator');
            if (!container) return null;

            errorContainer = document.createElement('div');
            errorContainer.id = 'error-container';
            errorContainer.className = 'mt-3 p-3 bg-red-50 border border-red-200 rounded-md hidden';
            
            errorContainer.innerHTML = `
                <div id="error-message" class="text-sm text-red-800 mb-3">
                    <!-- Error message will be inserted here -->
                </div>
                <div id="recovery-options" class="space-y-2">
                    <!-- Recovery options will be inserted here -->
                </div>
            `;

            // Insert before status actions
            const actionsEl = document.getElementById('status-actions');
            if (actionsEl) {
                actionsEl.parentNode.insertBefore(errorContainer, actionsEl);
            } else {
                container.querySelector('.p-4').appendChild(errorContainer);
            }
        }
        return errorContainer;
    },

    // Hide error UI elements
    hideErrorUI: function() {
        const errorContainer = document.getElementById('error-container');
        if (errorContainer) {
            errorContainer.classList.add('hidden');
        }

        // Show progress elements again
        const progressContainer = document.getElementById('progress-container');
        if (progressContainer) {
            progressContainer.classList.remove('hidden');
        }
    },

    // Get error title based on error type
    getErrorTitle: function(errorType) {
        switch (errorType) {
            case 'authentication':
                return 'Authentication Error';
            case 'network':
                return 'Connection Error';
            case 'not_found':
                return 'Status Not Found';
            case 'processing':
                return 'Processing Error';
            case 'validation':
                return 'Validation Error';
            default:
                return 'Processing Error';
        }
    },

    // Render recovery options
    renderRecoveryOptions: function(recoveryOptions) {
        const recoveryContainer = document.getElementById('recovery-options');
        if (!recoveryContainer || !recoveryOptions) return;

        recoveryContainer.innerHTML = '';

        if (!recoveryOptions.available) {
            recoveryContainer.innerHTML = `
                <p class="text-xs text-red-600">${recoveryOptions.message || 'No recovery options available.'}</p>
            `;
            return;
        }

        recoveryOptions.options.forEach(option => {
            const button = document.createElement('button');
            button.className = 'text-xs bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 mr-2';
            button.textContent = option.label;
            button.title = option.description;
            
            button.addEventListener('click', () => {
                this.executeRecoveryOption(option);
            });

            recoveryContainer.appendChild(button);
        });
    },

    // Execute recovery option
    executeRecoveryOption: function(option) {
        console.log('Executing recovery option:', option);

        switch (option.type) {
            case 'retry':
                this.retryProcessing(option.retryAfter);
                break;
            case 'reupload':
                this.promptReupload();
                break;
            case 'manual':
                this.showManualRecoveryHelp();
                break;
            default:
                console.warn('Unknown recovery option type:', option.type);
        }
    },

    // Retry processing with optional delay
    retryProcessing: function(retryAfter = 0) {
        console.log(`Retrying processing in ${retryAfter} seconds`);
        
        this.clearErrorState();
        
        if (retryAfter > 0) {
            // Show countdown
            this.showRetryCountdown(retryAfter);
            
            setTimeout(() => {
                this.resumePolling();
            }, retryAfter * 1000);
        } else {
            this.resumePolling();
        }
    },

    // Show retry countdown
    showRetryCountdown: function(seconds) {
        const messageEl = document.getElementById('status-message');
        if (!messageEl) return;

        let remaining = seconds;
        const countdownInterval = setInterval(() => {
            messageEl.textContent = `Retrying in ${remaining} seconds...`;
            remaining--;
            
            if (remaining < 0) {
                clearInterval(countdownInterval);
                messageEl.textContent = 'Retrying processing...';
            }
        }, 1000);
    },

    // Resume polling after error recovery
    resumePolling: function() {
        console.log('Resuming status polling after error recovery');
        this.retryCount = 0; // Reset retry count
        this.startPolling();
    },

    // Prompt user to reupload file
    promptReupload: function() {
        const message = 'Please correct your file and upload it again. The upload area will be available after closing this status indicator.';
        
        if (window.EasyCRM.Utils && window.EasyCRM.Utils.showToast) {
            window.EasyCRM.Utils.showToast(message, 'info', 5000);
        } else {
            alert(message);
        }
        
        // Hide status indicator to allow reupload
        setTimeout(() => {
            this.hide();
        }, 2000);
    },

    // Show manual recovery help
    showManualRecoveryHelp: function() {
        const helpMessage = `
            If you continue to experience issues:
            1. Check your internet connection
            2. Try refreshing the page
            3. Contact support with your upload ID: ${this.uploadId}
        `;
        
        if (window.EasyCRM.Utils && window.EasyCRM.Utils.showModal) {
            window.EasyCRM.Utils.showModal('Recovery Help', helpMessage);
        } else if (window.EasyCRM.Utils && window.EasyCRM.Utils.showToast) {
            window.EasyCRM.Utils.showToast('Please contact support for assistance.', 'info', 5000);
        } else {
            alert(helpMessage);
        }
    },

    // Handle authentication errors during polling
    handleAuthError: function() {
        console.warn('Authentication error during status polling, attempting token refresh');
        
        // Stop current polling to prevent multiple auth attempts
        this.stopPolling();
        
        // Check if auth module is available and has refresh capability
        if (window.EasyCRM.Auth && typeof window.EasyCRM.Auth.refreshToken === 'function') {
            console.log('Attempting to refresh authentication token');
            
            window.EasyCRM.Auth.refreshToken()
                .then(() => {
                    console.log('Token refreshed successfully, resuming polling');
                    // Reset retry count after successful auth refresh
                    this.retryCount = 0;
                    // Resume polling if component is still visible
                    if (this.isVisible && this.uploadId) {
                        this.startPolling();
                    }
                })
                .catch((refreshError) => {
                    console.error('Token refresh failed:', refreshError);
                    this.showError('Your session has expired. Please refresh the page and log in again.');
                });
        } else if (window.EasyCRM.Auth && typeof window.EasyCRM.Auth.ensureValidToken === 'function') {
            console.log('Attempting to ensure valid token');
            
            window.EasyCRM.Auth.ensureValidToken()
                .then(() => {
                    console.log('Token validated successfully, resuming polling');
                    // Reset retry count after successful auth validation
                    this.retryCount = 0;
                    // Resume polling if component is still visible
                    if (this.isVisible && this.uploadId) {
                        this.startPolling();
                    }
                })
                .catch((authError) => {
                    console.error('Token validation failed:', authError);
                    this.showError('Authentication failed. Please refresh the page and log in again.');
                });
        } else {
            console.error('No authentication refresh method available');
            this.showError('Authentication required. Please refresh the page and log in again.');
        }
    },

    // Handle processing completion
    handleProcessingComplete: function(status) {
        if (status.status === 'completed') {
            // Trigger automatic lead table refresh while maintaining current pagination and filter settings
            setTimeout(() => {
                if (window.EasyCRM.Leads && window.EasyCRM.Leads.refreshLeadTable) {
                    console.log('Processing completed, triggering automatic lead table refresh');
                    window.EasyCRM.Leads.refreshLeadTable();
                } else if (window.EasyCRM.Leads && window.EasyCRM.Leads.refreshLeads) {
                    // Fallback to basic refresh if refreshLeadTable is not available
                    console.log('refreshLeadTable not available, falling back to refreshLeads');
                    window.EasyCRM.Leads.refreshLeads();
                    
                    // Show success message with lead count for fallback
                    const totalLeads = (status.progress?.processedLeads || 0);
                    const message = `Successfully processed ${totalLeads} leads! Lead table has been updated.`;
                    
                    if (window.EasyCRM.Utils && window.EasyCRM.Utils.showToast) {
                        window.EasyCRM.Utils.showToast(message, 'success');
                    }
                } else {
                    console.warn('No lead refresh method available');
                }
            }, 1000);
        }
        
        // Notify upload module of completion
        if (window.EasyCRM.Upload && window.EasyCRM.Upload.handleProcessingCompletion) {
            window.EasyCRM.Upload.handleProcessingCompletion(status);
        }
    },

    // Cancel processing
    cancelProcessing: async function() {
        if (!this.uploadId) return;

        try {
            const cancelBtn = document.getElementById('cancel-processing');
            if (cancelBtn) {
                cancelBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Cancelling...';
                cancelBtn.disabled = true;
            }

            // Call cancel API endpoint if available
            if (window.EasyCRM.API.processing && window.EasyCRM.API.processing.cancelProcessing) {
                await window.EasyCRM.API.processing.cancelProcessing(this.uploadId);
            }
            
            // Update status immediately
            this.render({
                status: 'cancelled',
                stage: 'cancelled',
                progress: { percentage: 0 },
                metadata: {}
            });

            this.stopPolling();
            
            // Notify upload module of cancellation
            if (window.EasyCRM.Upload && window.EasyCRM.Upload.handleUploadCancellation) {
                window.EasyCRM.Upload.handleUploadCancellation();
            }

        } catch (error) {
            console.error('Error cancelling processing:', error);
            this.showError('Failed to cancel processing. The operation may continue in the background.');
            
            // Reset cancel button
            const cancelBtn = document.getElementById('cancel-processing');
            if (cancelBtn) {
                cancelBtn.innerHTML = 'Cancel Processing';
                cancelBtn.disabled = false;
            }
        }
    },

    // Show error message
    showError: function(message) {
        // Render error state using the standard render method
        this.render({
            status: 'error',
            stage: 'error',
            progress: { percentage: 0 },
            error: { message: message },
            metadata: {}
        });
        
        // Stop polling on error
        this.stopPolling();
        
        // Log error for debugging
        console.error('ProcessingStatusIndicator error:', message);
    },

    // Check if component is visible
    isShowing: function() {
        return this.isVisible;
    },

    // Get current upload ID
    getCurrentUploadId: function() {
        return this.uploadId;
    },

    // Get current polling state for debugging
    getPollingState: function() {
        return {
            uploadId: this.uploadId,
            isVisible: this.isVisible,
            isPolling: !!this.pollInterval,
            retryCount: this.retryCount,
            maxRetries: this.config.maxRetries,
            pollInterval: this.config.pollInterval
        };
    },

    // Reset polling state
    resetPollingState: function() {
        this.retryCount = 0;
        this.stopPolling();
    },

    // Cleanup method
    cleanup: function() {
        console.log('Cleaning up ProcessingStatusIndicator');
        this.stopPolling();
        this.uploadId = null;
        this.isVisible = false;
        this.retryCount = 0;
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (window.EasyCRM && window.EasyCRM.ProcessingStatusIndicator) {
        window.EasyCRM.ProcessingStatusIndicator.init();
    }
});