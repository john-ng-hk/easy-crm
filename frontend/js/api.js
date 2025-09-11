// API communication module
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.API = {
    // Make authenticated API request
    request: async function(endpoint, options = {}) {
        const config = window.EasyCRM.Config;
        const auth = window.EasyCRM.Auth;
        
        // Ensure we have a valid token before making the request
        let token;
        try {
            token = await auth.ensureValidToken();
        } catch (error) {
            console.error('Authentication error:', error);
            auth.logout();
            throw new Error('Authentication required. Please log in again.');
        }
        
        const url = config.API.BASE_URL + endpoint;

        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            timeout: config.API.TIMEOUT
        };

        const requestOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };

        try {
            console.log('🔍 NETWORK DEBUG: Making request to:', url);
            console.log('🔍 Request options:', requestOptions);
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), requestOptions.timeout);
            
            const response = await fetch(url, {
                ...requestOptions,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            console.log('🔍 Network response status:', response.status, response.statusText);
            console.log('🔍 Response headers:', Object.fromEntries(response.headers.entries()));

            if (!response.ok) {
                console.error('🔍 Request failed with status:', response.status);
                if (response.status === 401 || response.status === 403) {
                    // Authentication/authorization failed
                    console.warn('Authentication failed, logging out user');
                    auth.logout();
                    throw new Error('Session expired. Please log in again.');
                } else {
                    const errorData = await response.json().catch(() => ({}));
                    console.error('🔍 Error response data:', errorData);
                    throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
                }
            }

            const responseData = await response.json();
            console.log('🔍 Parsed response data:', responseData);
            return responseData;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            throw error;
        }
    },

    // Check if user is authenticated before making requests
    isAuthenticated: function() {
        const auth = window.EasyCRM.Auth;
        return auth && auth.currentUser && auth.getToken();
    },

    // Authentication guard for API calls
    requireAuth: function() {
        if (!this.isAuthenticated()) {
            const auth = window.EasyCRM.Auth;
            if (auth) {
                auth.logout();
            }
            throw new Error('Authentication required');
        }
    },

    // Upload file endpoints
    upload: {
        // Get presigned URL for file upload
        getPresignedUrl: async function(fileName, fileType, fileSize) {
            window.EasyCRM.API.requireAuth();
            return await window.EasyCRM.API.request(window.EasyCRM.Config.API.ENDPOINTS.UPLOAD, {
                method: 'POST',
                body: JSON.stringify({
                    fileName: fileName,
                    fileType: fileType,
                    fileSize: fileSize
                })
            });
        },

        // Upload file to S3 using presigned URL
        uploadToS3: async function(presignedUrl, file, onProgress) {
            return new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                
                xhr.upload.addEventListener('progress', (event) => {
                    if (event.lengthComputable && onProgress) {
                        const percentComplete = (event.loaded / event.total) * 100;
                        onProgress(percentComplete);
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve(xhr.response);
                    } else {
                        reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
                    }
                });

                xhr.addEventListener('error', () => {
                    reject(new Error('Upload failed: Network error'));
                });

                xhr.addEventListener('timeout', () => {
                    reject(new Error('Upload failed: Timeout'));
                });

                xhr.open('PUT', presignedUrl);
                xhr.setRequestHeader('Content-Type', file.type);
                xhr.timeout = window.EasyCRM.Config.APP.UPLOAD_TIMEOUT;
                xhr.send(file);
            });
        }
    },

    // Lead management endpoints
    leads: {
        // Active request tracking for deduplication
        _activeRequests: new Map(),
        
        // Validate API request parameters
        _validateParams: function(params) {
            const errors = [];
            
            // Validate pagination parameters
            if (params.page !== undefined) {
                const page = parseInt(params.page);
                if (isNaN(page) || page < 1) {
                    errors.push('Page must be a positive integer');
                }
                params.page = page; // Normalize to integer
            }
            
            if (params.pageSize !== undefined) {
                const pageSize = parseInt(params.pageSize);
                if (isNaN(pageSize) || pageSize < 1 || pageSize > 100) {
                    errors.push('Page size must be between 1 and 100');
                }
                params.pageSize = pageSize; // Normalize to integer
            }
            
            // Validate sorting parameters
            if (params.sortBy !== undefined) {
                const validSortFields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone', 'createdAt', 'updatedAt'];
                if (!validSortFields.includes(params.sortBy)) {
                    errors.push(`Sort field must be one of: ${validSortFields.join(', ')}`);
                }
            }
            
            if (params.sortOrder !== undefined) {
                const validSortOrders = ['asc', 'desc'];
                if (!validSortOrders.includes(params.sortOrder.toLowerCase())) {
                    errors.push('Sort order must be "asc" or "desc"');
                }
                params.sortOrder = params.sortOrder.toLowerCase(); // Normalize to lowercase
            }
            
            // Validate filter parameters
            if (params.filters && typeof params.filters === 'object') {
                const validFilterFields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone'];
                Object.keys(params.filters).forEach(key => {
                    if (!validFilterFields.includes(key)) {
                        errors.push(`Invalid filter field: ${key}`);
                    }
                    // Sanitize filter values
                    if (typeof params.filters[key] === 'string') {
                        params.filters[key] = params.filters[key].trim();
                        if (params.filters[key].length > 100) {
                            errors.push(`Filter value for ${key} is too long (max 100 characters)`);
                        }
                    }
                });
            }
            
            if (errors.length > 0) {
                throw new Error(`Parameter validation failed: ${errors.join(', ')}`);
            }
            
            return params;
        },
        
        // Generate request key for deduplication
        _generateRequestKey: function(params) {
            return JSON.stringify({
                page: params.page || 1,
                pageSize: params.pageSize || 50,
                sortBy: params.sortBy || null,
                sortOrder: params.sortOrder || 'asc',
                filters: params.filters || {}
            });
        },
        
        // Build query parameters with proper encoding
        _buildQueryParams: function(params) {
            const queryParams = new URLSearchParams();
            
            // Always include pagination parameters with defaults
            queryParams.append('page', params.page || 1);
            queryParams.append('pageSize', params.pageSize || 50);
            console.log('🔍 Added pagination parameters:', {
                page: params.page || 1,
                pageSize: params.pageSize || 50
            });
            
            // Add sorting parameters if provided
            if (params.sortBy) {
                queryParams.append('sortBy', params.sortBy);
                queryParams.append('sortOrder', params.sortOrder || 'asc');
                console.log('🔍 Added sorting parameters:', {
                    sortBy: params.sortBy,
                    sortOrder: params.sortOrder || 'asc'
                });
            }
            
            // Add filter parameters if provided
            if (params.filters && typeof params.filters === 'object') {
                Object.keys(params.filters).forEach(key => {
                    const value = params.filters[key];
                    if (value && value.trim()) {
                        queryParams.append(`filter_${key}`, value.trim());
                        console.log('🔍 Added filter parameter:', `filter_${key}`, value.trim());
                    }
                });
            }
            
            return queryParams;
        },

        // Get leads with filtering, sorting, and pagination
        getLeads: async function(params = {}) {
            console.log('🔍 API DEBUG: getLeads() called with params:', params);
            
            try {
                window.EasyCRM.API.requireAuth();
                
                // Validate and normalize parameters
                const validatedParams = this._validateParams({ ...params });
                console.log('🔍 Validated parameters:', validatedParams);
                
                // Generate request key for deduplication
                const requestKey = this._generateRequestKey(validatedParams);
                console.log('🔍 Request key for deduplication:', requestKey);
                
                // Check if identical request is already in progress
                if (this._activeRequests.has(requestKey)) {
                    console.log('🔍 Duplicate request detected, returning existing promise');
                    return await this._activeRequests.get(requestKey);
                }
                
                // Build query parameters
                const queryParams = this._buildQueryParams(validatedParams);
                
                const endpoint = window.EasyCRM.Config.API.ENDPOINTS.LEADS + 
                               `?${queryParams.toString()}`;
                
                console.log('🔍 Final API endpoint:', endpoint);
                console.log('🔍 Query parameters string:', queryParams.toString());
                
                // Create and track the request promise
                const requestPromise = window.EasyCRM.API.request(endpoint);
                this._activeRequests.set(requestKey, requestPromise);
                
                try {
                    const response = await requestPromise;
                    console.log('🔍 API response received:', response);
                    console.log('🔍 Response leads count:', response.leads ? response.leads.length : 0);
                    console.log('🔍 Response pagination:', response.pagination);
                    
                    // Validate response structure
                    if (!response || typeof response !== 'object') {
                        throw new Error('Invalid API response format');
                    }
                    
                    if (!Array.isArray(response.leads)) {
                        console.warn('🔍 Response missing leads array, using empty array');
                        response.leads = [];
                    }
                    
                    // Ensure pagination metadata exists
                    if (!response.pagination) {
                        console.warn('🔍 Response missing pagination metadata, creating default');
                        response.pagination = {
                            page: validatedParams.page || 1,
                            pageSize: validatedParams.pageSize || 50,
                            totalCount: response.leads.length,
                            totalPages: 1
                        };
                    }
                    
                    // Log final response structure for debugging
                    // Log final response structure for debugging (can be removed in production)
                    console.log('🔍 Final response structure:', {
                        leadsCount: response.leads.length,
                        pagination: response.pagination,
                        firstLead: response.leads[0] ? {
                            leadId: response.leads[0].leadId,
                            firstName: response.leads[0].firstName,
                            lastName: response.leads[0].lastName
                        } : null
                    });
                    
                    return response;
                } finally {
                    // Clean up active request tracking
                    this._activeRequests.delete(requestKey);
                }
                
            } catch (error) {
                console.error('🔍 API parameter validation or request error:', error);
                throw error;
            }
        },

        // Get single lead by ID
        getLead: async function(leadId) {
            window.EasyCRM.API.requireAuth();
            return await window.EasyCRM.API.request(`${window.EasyCRM.Config.API.ENDPOINTS.LEADS}/${leadId}`);
        }
    },

    // Export functionality
    export: {
        // Export leads as CSV
        exportLeads: async function(filters = {}) {
            window.EasyCRM.API.requireAuth();
            const params = { filters };
            
            return await window.EasyCRM.API.request(window.EasyCRM.Config.API.ENDPOINTS.EXPORT, {
                method: 'POST',
                body: JSON.stringify(params)
            });
        }
    },

    // Chat functionality
    chat: {
        // Send message to chatbot
        sendMessage: async function(message, userId) {
            window.EasyCRM.API.requireAuth();
            return await window.EasyCRM.API.request(window.EasyCRM.Config.API.ENDPOINTS.CHAT, {
                method: 'POST',
                body: JSON.stringify({
                    query: message,
                    userId: userId
                })
            });
        }
    },

    // Processing status functionality
    processing: {
        // Get processing status by uploadId with enhanced error handling
        getStatus: async function(uploadId) {
            window.EasyCRM.API.requireAuth();
            
            if (!uploadId || typeof uploadId !== 'string') {
                throw new Error('Invalid upload ID provided');
            }
            
            try {
                const response = await window.EasyCRM.API.request(`/status/${uploadId}`);
                
                // Validate response structure
                if (!response || typeof response !== 'object') {
                    throw new Error('Invalid status response format');
                }
                
                if (!response.status || typeof response.status !== 'string') {
                    throw new Error('Status response missing required status field');
                }
                
                return response;
            } catch (error) {
                // Enhance error messages for status-specific errors
                if (error.message && error.message.includes('404')) {
                    throw new Error('Status not found - the upload may have expired or completed');
                } else if (error.message && error.message.includes('500')) {
                    throw new Error('Server error retrieving status - please try again');
                } else {
                    throw error;
                }
            }
        },

        // Get recent processing statuses (fallback method for file-based tracking)
        getRecentStatuses: async function(limit = 10) {
            window.EasyCRM.API.requireAuth();
            
            if (limit && (typeof limit !== 'number' || limit < 1 || limit > 100)) {
                throw new Error('Limit must be a number between 1 and 100');
            }
            
            return await window.EasyCRM.API.request(`/processing/recent?limit=${limit}`);
        },

        // Update processing status by uploadId
        updateStatus: async function(uploadId, statusData) {
            window.EasyCRM.API.requireAuth();
            
            if (!uploadId || typeof uploadId !== 'string') {
                throw new Error('Invalid upload ID provided');
            }
            
            if (!statusData || typeof statusData !== 'object') {
                throw new Error('Invalid status data provided');
            }
            
            try {
                const response = await window.EasyCRM.API.request(`/status/${uploadId}`, {
                    method: 'PUT',
                    body: JSON.stringify(statusData)
                });
                
                return response;
            } catch (error) {
                // Enhance error messages for status update errors
                if (error.message && error.message.includes('404')) {
                    throw new Error('Status not found - the upload may have expired');
                } else if (error.message && error.message.includes('400')) {
                    throw new Error('Invalid status data provided');
                } else {
                    throw error;
                }
            }
        },

        // Cancel processing by uploadId with enhanced error handling
        cancelProcessing: async function(uploadId) {
            window.EasyCRM.API.requireAuth();
            
            if (!uploadId || typeof uploadId !== 'string') {
                throw new Error('Invalid upload ID provided');
            }
            
            try {
                const response = await window.EasyCRM.API.request(`/status/${uploadId}/cancel`, {
                    method: 'POST'
                });
                
                return response;
            } catch (error) {
                // Enhance error messages for cancellation-specific errors
                if (error.message && error.message.includes('404')) {
                    throw new Error('Cannot cancel - processing not found or already completed');
                } else if (error.message && error.message.includes('409')) {
                    throw new Error('Cannot cancel - processing is already in final state');
                } else {
                    throw error;
                }
            }
        },

        // Retry processing for recoverable errors
        retryProcessing: async function(uploadId) {
            window.EasyCRM.API.requireAuth();
            
            if (!uploadId || typeof uploadId !== 'string') {
                throw new Error('Invalid upload ID provided');
            }
            
            try {
                const response = await window.EasyCRM.API.request(`/status/${uploadId}/retry`, {
                    method: 'POST'
                });
                
                return response;
            } catch (error) {
                // Enhance error messages for retry-specific errors
                if (error.message && error.message.includes('404')) {
                    throw new Error('Cannot retry - processing not found');
                } else if (error.message && error.message.includes('400')) {
                    throw new Error('Cannot retry - error is not recoverable');
                } else {
                    throw error;
                }
            }
        }
    },

    // Utility methods
    utils: {
        // Test API connectivity
        healthCheck: async function() {
            try {
                // Try to make a simple request to test connectivity
                await window.EasyCRM.API.leads.getLeads({ page: 1, pageSize: 1 });
                return true;
            } catch (error) {
                console.error('API health check failed:', error);
                return false;
            }
        },

        // Retry failed requests
        retry: async function(fn, maxAttempts = 3, delay = 1000) {
            let lastError;
            
            for (let attempt = 1; attempt <= maxAttempts; attempt++) {
                try {
                    return await fn();
                } catch (error) {
                    lastError = error;
                    
                    if (attempt === maxAttempts) {
                        throw error;
                    }
                    
                    // Exponential backoff
                    await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, attempt - 1)));
                }
            }
            
            throw lastError;
        },

        // Handle API errors gracefully
        handleError: function(error, context = '') {
            console.error(`API Error ${context}:`, error);
            
            let userMessage = 'An unexpected error occurred. Please try again.';
            
            if (error.message) {
                if (error.message.includes('timeout')) {
                    userMessage = 'Request timed out. Please check your connection and try again.';
                } else if (error.message.includes('Network')) {
                    userMessage = 'Network error. Please check your connection.';
                } else if (error.message.includes('Session expired')) {
                    userMessage = 'Your session has expired. Please log in again.';
                } else {
                    userMessage = error.message;
                }
            }
            
            window.EasyCRM.Utils.showToast(userMessage, 'error');
            return userMessage;
        }
    }
};