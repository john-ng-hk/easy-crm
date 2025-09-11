// Leads management functionality
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.Leads = {
    currentPage: 1,
    pageSize: 50,
    totalPages: 1,
    totalLeads: 0,
    currentSort: { field: null, order: 'asc' },
    currentFilters: {},
    leads: [],
    isLoading: false,
    
    // Initialize leads functionality
    init: function() {
        console.log('🔍 PAGINATION DEBUG: Initializing leads module');
        this.verifyDOMElements();
        this.attachEventHandlers();
        this.loadLeads();
    },

    // Verify all required DOM elements exist
    verifyDOMElements: function() {
        console.log('🔍 PAGINATION DEBUG: Verifying DOM elements');
        
        const requiredElements = [
            'leads-tbody',
            'loading-state', 
            'empty-state',
            'showing-from',
            'showing-to', 
            'total-leads',
            'page-info',
            'prev-page',
            'next-page'
        ];
        
        const missingElements = [];
        
        requiredElements.forEach(id => {
            const element = document.getElementById(id);
            if (!element) {
                missingElements.push(id);
                console.error('🔍 Missing DOM element:', id);
            } else {
                console.log('🔍 Found DOM element:', id, element);
            }
        });
        
        if (missingElements.length > 0) {
            console.error('🔍 CRITICAL: Missing DOM elements:', missingElements);
        } else {
            console.log('🔍 All required DOM elements found');
        }
    },

    // Attach event handlers
    attachEventHandlers: function() {
        // Filter inputs with debouncing
        const filterInputs = document.querySelectorAll('[id^="filter-"]');
        filterInputs.forEach(input => {
            input.addEventListener('input', window.EasyCRM.Utils.debounce(() => {
                this.handleFilterChange();
            }, window.EasyCRM.Config.UI.DEBOUNCE_DELAY));
        });

        // Clear filters button
        document.getElementById('clear-filters').addEventListener('click', () => {
            this.clearFilters();
        });

        // Sort headers
        const sortHeaders = document.querySelectorAll('[data-sort]');
        sortHeaders.forEach(header => {
            header.addEventListener('click', () => {
                const field = header.getAttribute('data-sort');
                this.handleSort(field);
            });
        });

        // Pagination buttons with proper event handling and state management
        document.getElementById('prev-page').addEventListener('click', window.EasyCRM.Utils.debounce((event) => {
            event.preventDefault();
            event.stopPropagation();
            
            console.log('🔍 PAGINATION DEBUG: Previous button clicked');
            console.log('🔍 Current state before:', {
                currentPage: this.currentPage,
                totalPages: this.totalPages,
                totalLeads: this.totalLeads,
                isLoading: this.isLoading,
                filters: this.currentFilters,
                sort: this.currentSort
            });
            
            // Validate pagination action
            if (!this.canNavigateToPreviousPage()) {
                return;
            }
            
            this.currentPage--;
            this.validatePageState();
            console.log('🔍 Moving to previous page:', this.currentPage);
            console.log('🔍 Maintaining filters:', this.currentFilters);
            console.log('🔍 Maintaining sort:', this.currentSort);
            this.loadLeads();
        }, 200)); // 200ms debounce for pagination

        document.getElementById('next-page').addEventListener('click', window.EasyCRM.Utils.debounce((event) => {
            event.preventDefault();
            event.stopPropagation();
            
            console.log('🔍 PAGINATION DEBUG: Next button clicked');
            console.log('🔍 Current state before:', {
                currentPage: this.currentPage,
                totalPages: this.totalPages,
                totalLeads: this.totalLeads,
                isLoading: this.isLoading,
                filters: this.currentFilters,
                sort: this.currentSort
            });
            
            // Validate pagination action
            if (!this.canNavigateToNextPage()) {
                return;
            }
            
            this.currentPage++;
            this.validatePageState();
            console.log('🔍 Moving to next page:', this.currentPage);
            console.log('🔍 Maintaining filters:', this.currentFilters);
            console.log('🔍 Maintaining sort:', this.currentSort);
            this.loadLeads();
        }, 200)); // 200ms debounce for pagination

        // Export button
        document.getElementById('export-btn').addEventListener('click', () => {
            this.exportLeads();
        });

        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', () => {
            this.refreshLeads();
        });
    },

    // Load leads from API
    loadLeads: async function() {
        try {
            console.log('🔍 PAGINATION DEBUG: loadLeads() called');
            console.log('🔍 Request parameters:', {
                currentPage: this.currentPage,
                pageSize: this.pageSize,
                filters: this.currentFilters,
                sort: this.currentSort
            });
            
            // Validate page state before making request
            this.validatePageState();
            
            // Prevent concurrent requests
            if (this.isLoading) {
                console.log('🔍 Request already in progress, skipping');
                return;
            }
            
            // Set loading state and disable pagination buttons
            this.isLoading = true;
            this.setPaginationButtonsState(true);
            this.showLoading();

            // Build comprehensive parameters object
            const params = this.buildRequestParams();
            
            // Validate parameters before making API call
            this.validateRequestParams(params);
            
            console.log('🔍 Final API call parameters (validated):', params);
            const response = await window.EasyCRM.API.leads.getLeads(params);
            console.log('🔍 API response received:', response);
            
            // Enhanced validation of API response structure
            this.validateApiResponse(response);
            
            this.leads = response.leads || [];
            console.log('🔍 Leads data received:', this.leads.length, 'leads');
            
            // Handle both nested pagination object and flat response structure
            if (response.pagination) {
                console.log('🔍 Using nested pagination structure:', response.pagination);
                this.totalLeads = response.pagination.totalCount || 0;
                this.totalPages = response.pagination.totalPages || 1;
                this.currentPage = response.pagination.page || 1;
            } else {
                console.log('🔍 Using flat response structure');
                // Fallback to flat structure or calculate from leads
                this.totalLeads = response.totalCount || this.leads.length;
                this.totalPages = response.totalPages || Math.max(1, Math.ceil(this.totalLeads / this.pageSize));
                this.currentPage = response.page || 1;
            }

            console.log('🔍 Final pagination state:', {
                currentPage: this.currentPage,
                totalPages: this.totalPages,
                totalLeads: this.totalLeads,
                leadsCount: this.leads.length
            });

            // Ensure table is properly cleared and rendered
            console.log('🔍 Clearing table and rendering new data');
            this.clearTable();
            console.log('🔍 Calling renderLeads()');
            this.renderLeads();
            console.log('🔍 Calling updatePagination()');
            this.updatePagination();
            console.log('🔍 Calling updateExportButton()');
            this.updateExportButton();

        } catch (error) {
            console.error('🔍 PAGINATION DEBUG: Error in loadLeads():', error);
            console.error('🔍 Error stack:', error.stack);
            console.error('🔍 Current state when error occurred:', {
                currentPage: this.currentPage,
                pageSize: this.pageSize,
                totalPages: this.totalPages,
                totalLeads: this.totalLeads
            });
            
            // Enhanced error handling with recovery
            this.handleLoadError(error);
        } finally {
            // Clear loading state and re-enable pagination buttons
            this.isLoading = false;
            this.setPaginationButtonsState(false);
            this.removeLoadingOverlay();
        }
    },

    // Build comprehensive request parameters
    buildRequestParams: function() {
        const params = {
            page: this.currentPage,
            pageSize: this.pageSize
        };
        
        // Always include current filters (maintain during pagination)
        if (this.currentFilters && Object.keys(this.currentFilters).length > 0) {
            params.filters = { ...this.currentFilters };
            console.log('🔍 Including filters in request:', params.filters);
        }
        
        // Always include current sorting (maintain during pagination)
        if (this.currentSort.field) {
            params.sortBy = this.currentSort.field;
            params.sortOrder = this.currentSort.order;
            console.log('🔍 Including sorting in request:', {
                sortBy: params.sortBy,
                sortOrder: params.sortOrder
            });
        }
        
        return params;
    },
    
    // Validate and normalize current page state
    validatePageState: function() {
        // Ensure currentPage is within valid bounds
        if (this.currentPage < 1) {
            this.currentPage = 1;
        }
        if (this.totalPages > 0 && this.currentPage > this.totalPages) {
            this.currentPage = this.totalPages;
        }
        
        // Validate pageSize
        if (this.pageSize < 1 || this.pageSize > 100) {
            this.pageSize = 50; // Reset to default
        }
        
        console.log('🔍 Page state validated:', {
            currentPage: this.currentPage,
            totalPages: this.totalPages,
            totalLeads: this.totalLeads,
            pageSize: this.pageSize
        });
    },
    
    // Validate request parameters before API call
    validateRequestParams: function(params) {
        const errors = [];
        
        // Validate pagination
        if (!params.page || params.page < 1) {
            errors.push('Invalid page number');
        }
        if (!params.pageSize || params.pageSize < 1 || params.pageSize > 100) {
            errors.push('Invalid page size');
        }
        
        // Validate sorting
        if (params.sortBy) {
            const validSortFields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone', 'createdAt'];
            if (!validSortFields.includes(params.sortBy)) {
                errors.push(`Invalid sort field: ${params.sortBy}`);
            }
        }
        
        if (params.sortOrder && !['asc', 'desc'].includes(params.sortOrder)) {
            errors.push(`Invalid sort order: ${params.sortOrder}`);
        }
        
        // Validate filters
        if (params.filters) {
            const validFilterFields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone'];
            Object.keys(params.filters).forEach(key => {
                if (!validFilterFields.includes(key)) {
                    errors.push(`Invalid filter field: ${key}`);
                }
            });
        }
        
        if (errors.length > 0) {
            throw new Error(`Parameter validation failed: ${errors.join(', ')}`);
        }
        
        return true;
    },

    // Check if can navigate to previous page
    canNavigateToPreviousPage: function() {
        if (this.isLoading) {
            console.log('🔍 Cannot navigate: Request already in progress');
            return false;
        }
        
        if (this.currentPage <= 1) {
            console.log('🔍 Cannot navigate: Already on first page');
            return false;
        }
        
        return true;
    },
    
    // Check if can navigate to next page
    canNavigateToNextPage: function() {
        if (this.isLoading) {
            console.log('🔍 Cannot navigate: Request already in progress');
            return false;
        }
        
        if (this.currentPage >= this.totalPages) {
            console.log('🔍 Cannot navigate: Already on last page');
            return false;
        }
        
        return true;
    },
    
    // Set pagination buttons state (disabled during loading)
    setPaginationButtonsState: function(disabled) {
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');
        
        if (disabled) {
            // Disable buttons during loading
            prevBtn.disabled = true;
            nextBtn.disabled = true;
            prevBtn.classList.add('opacity-50', 'cursor-not-allowed');
            nextBtn.classList.add('opacity-50', 'cursor-not-allowed');
            console.log('🔍 Pagination buttons disabled during loading');
        } else {
            // Re-enable buttons based on current page state
            const prevDisabled = this.currentPage <= 1;
            const nextDisabled = this.currentPage >= this.totalPages;
            
            prevBtn.disabled = prevDisabled;
            nextBtn.disabled = nextDisabled;
            
            // Update visual states
            if (prevDisabled) {
                prevBtn.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                prevBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
            
            if (nextDisabled) {
                nextBtn.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                nextBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            }
            
            console.log('🔍 Pagination buttons state updated:', {
                prevDisabled,
                nextDisabled,
                currentPage: this.currentPage,
                totalPages: this.totalPages
            });
        }
    },

    // Validate API response structure for malformed responses
    validateApiResponse: function(response) {
        console.log('🔍 Validating API response structure');
        
        if (!response || typeof response !== 'object') {
            throw new Error('Invalid API response: Response is not an object');
        }
        
        // Check for leads array
        if (!response.hasOwnProperty('leads')) {
            console.warn('🔍 API response missing leads property, will use empty array');
            response.leads = [];
        }
        
        if (!Array.isArray(response.leads)) {
            console.warn('🔍 API response leads property is not an array, converting to array');
            response.leads = [];
        }
        
        // Validate each lead object structure
        if (response.leads.length > 0) {
            const requiredFields = ['leadId'];
            const optionalFields = ['firstName', 'lastName', 'title', 'company', 'email', 'phone', 'remarks', 'createdAt', 'updatedAt'];
            
            response.leads.forEach((lead, index) => {
                if (!lead || typeof lead !== 'object') {
                    console.warn(`🔍 Lead at index ${index} is not a valid object, skipping`);
                    return;
                }
                
                // Check required fields
                requiredFields.forEach(field => {
                    if (!lead.hasOwnProperty(field)) {
                        console.warn(`🔍 Lead at index ${index} missing required field: ${field}`);
                        lead[field] = `missing-${field}-${index}`;
                    }
                });
                
                // Sanitize string fields
                [...requiredFields, ...optionalFields].forEach(field => {
                    if (lead[field] && typeof lead[field] === 'string') {
                        lead[field] = lead[field].trim();
                        if (lead[field] === '') {
                            lead[field] = 'N/A';
                        }
                    }
                });
            });
        }
        
        // Validate pagination structure
        if (response.pagination) {
            const paginationFields = ['page', 'pageSize', 'totalCount', 'totalPages'];
            paginationFields.forEach(field => {
                if (response.pagination[field] !== undefined) {
                    const value = parseInt(response.pagination[field]);
                    if (isNaN(value) || value < 0) {
                        console.warn(`🔍 Invalid pagination ${field}: ${response.pagination[field]}, using default`);
                        response.pagination[field] = field === 'page' ? 1 : 0;
                    } else {
                        response.pagination[field] = value;
                    }
                }
            });
        }
        
        console.log('🔍 API response validation completed');
        return response;
    },

    // Clear table DOM before rendering new data
    clearTable: function() {
        console.log('🔍 Clearing table DOM');
        const tbody = document.getElementById('leads-tbody');
        const loadingState = document.getElementById('loading-state');
        const emptyState = document.getElementById('empty-state');
        
        // Clear existing table content
        if (tbody) {
            tbody.innerHTML = '';
            console.log('🔍 Table tbody cleared');
        }
        
        // Hide all states initially
        if (loadingState) {
            loadingState.classList.add('hidden');
        }
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
        
        // Remove any loading overlays
        this.removeLoadingOverlay();
    },

    // Enhanced error handling with recovery options
    handleLoadError: function(error) {
        console.error('🔍 Handling load error:', error);
        
        let errorMessage = 'Failed to load leads. Please try again.';
        let showRetry = true;
        let shouldResetPage = false;
        
        // Categorize error types and provide appropriate handling
        if (error.message) {
            if (error.message.includes('timeout')) {
                errorMessage = 'Request timed out. Please check your connection and try again.';
            } else if (error.message.includes('Network')) {
                errorMessage = 'Network error. Please check your internet connection.';
            } else if (error.message.includes('Session expired') || error.message.includes('Authentication')) {
                errorMessage = 'Your session has expired. Please log in again.';
                showRetry = false;
                // Trigger logout after a delay
                setTimeout(() => {
                    if (window.EasyCRM.Auth) {
                        window.EasyCRM.Auth.logout();
                    }
                }, 2000);
            } else if (error.message.includes('Parameter validation')) {
                errorMessage = 'Invalid request parameters. Resetting to first page.';
                shouldResetPage = true;
            } else if (error.message.includes('Invalid API response')) {
                errorMessage = 'Server returned invalid data. Please try again or contact support.';
            } else {
                errorMessage = error.message;
            }
        }
        
        // Reset to first page if parameter validation failed
        if (shouldResetPage) {
            this.currentPage = 1;
            this.validatePageState();
            // Retry with reset parameters
            setTimeout(() => {
                this.loadLeads();
            }, 1000);
            return;
        }
        
        // Show error in table
        this.showError(errorMessage, showRetry);
        
        // Also show toast notification
        window.EasyCRM.API.utils.handleError(error, 'loading leads');
    },

    // Show loading state with enhanced visual feedback
    showLoading: function() {
        console.log('🔍 Showing loading state');
        
        const tbody = document.getElementById('leads-tbody');
        const loadingState = document.getElementById('loading-state');
        const emptyState = document.getElementById('empty-state');

        // Clear table content
        if (tbody) {
            tbody.innerHTML = '';
        }
        
        // Show loading state
        if (loadingState) {
            loadingState.classList.remove('hidden');
        }
        
        // Hide empty state
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
        
        // Add loading skeleton in table for better UX
        if (tbody) {
            const skeletonRows = Array.from({ length: 5 }, (_, index) => `
                <tr class="animate-pulse">
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="h-4 bg-gray-200 rounded w-20"></div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="h-4 bg-gray-200 rounded w-24"></div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="h-4 bg-gray-200 rounded w-32"></div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="h-4 bg-gray-200 rounded w-28"></div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="h-4 bg-gray-200 rounded w-36"></div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="h-4 bg-gray-200 rounded w-24"></div>
                    </td>
                    <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex space-x-2">
                            <div class="h-4 w-4 bg-gray-200 rounded"></div>
                            <div class="h-4 w-4 bg-gray-200 rounded"></div>
                            <div class="h-4 w-4 bg-gray-200 rounded"></div>
                        </div>
                    </td>
                </tr>
            `).join('');
            
            tbody.innerHTML = skeletonRows;
        }
        
        // Add loading overlay to table container for additional visual feedback
        this.addLoadingOverlay();
    },

    // Add loading overlay to table container
    addLoadingOverlay: function() {
        const tableContainer = document.querySelector('.overflow-x-auto');
        if (tableContainer && !tableContainer.querySelector('.loading-overlay')) {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center z-10';
            overlay.innerHTML = `
                <div class="text-center">
                    <i class="fas fa-spinner fa-spin text-2xl text-blue-600 mb-2"></i>
                    <p class="text-sm text-gray-600">Loading leads...</p>
                </div>
            `;
            
            // Make container relative for absolute positioning
            tableContainer.style.position = 'relative';
            tableContainer.appendChild(overlay);
            
            console.log('🔍 Loading overlay added');
        }
    },

    // Remove loading overlay
    removeLoadingOverlay: function() {
        const overlay = document.querySelector('.loading-overlay');
        if (overlay) {
            overlay.remove();
            console.log('🔍 Loading overlay removed');
        }
    },

    // Show error state with enhanced retry options
    showError: function(message, showRetry = true) {
        console.log('🔍 Showing error state:', message, 'showRetry:', showRetry);
        
        const tbody = document.getElementById('leads-tbody');
        const loadingState = document.getElementById('loading-state');
        const emptyState = document.getElementById('empty-state');

        // Clear table and hide other states
        this.clearTable();
        
        const retryButton = showRetry ? `
            <button onclick="window.EasyCRM.Leads.retryLoad()" 
                    class="mt-4 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 mr-2">
                <i class="fas fa-redo mr-2"></i>Try Again
            </button>
            <button onclick="window.EasyCRM.Leads.resetAndReload()" 
                    class="mt-4 bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700">
                <i class="fas fa-refresh mr-2"></i>Reset & Reload
            </button>
        ` : `
            <button onclick="window.location.reload()" 
                    class="mt-4 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700">
                <i class="fas fa-refresh mr-2"></i>Reload Page
            </button>
        `;

        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-6 py-12 text-center">
                    <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
                    <p class="text-lg text-gray-600 mb-2">Error Loading Leads</p>
                    <p class="text-sm text-gray-500 mb-4">${window.EasyCRM.Utils.sanitizeHtml(message)}</p>
                    ${retryButton}
                </td>
            </tr>
        `;
        
        console.log('🔍 Error state displayed in table');
    },

    // Render leads in table with enhanced error handling
    renderLeads: function() {
        console.log('🔍 PAGINATION DEBUG: renderLeads() called with', this.leads.length, 'leads');
        
        try {
            const tbody = document.getElementById('leads-tbody');
            const loadingState = document.getElementById('loading-state');
            const emptyState = document.getElementById('empty-state');

            // Verify DOM elements exist
            if (!tbody) {
                throw new Error('Table body element not found');
            }

            // Hide loading state
            if (loadingState) {
                loadingState.classList.add('hidden');
            }

            // Handle empty results
            if (!this.leads || this.leads.length === 0) {
                console.log('🔍 No leads to render, showing empty state');
                tbody.innerHTML = '';
                if (emptyState) {
                    emptyState.classList.remove('hidden');
                }
                return;
            }

            console.log('🔍 Rendering', this.leads.length, 'leads in table');
            
            // Hide empty state
            if (emptyState) {
                emptyState.classList.add('hidden');
            }

            // Validate leads data before rendering
            const validLeads = this.leads.filter(lead => {
                if (!lead || typeof lead !== 'object') {
                    console.warn('🔍 Invalid lead object found, skipping:', lead);
                    return false;
                }
                if (!lead.leadId) {
                    console.warn('🔍 Lead missing leadId, skipping:', lead);
                    return false;
                }
                return true;
            });

            if (validLeads.length !== this.leads.length) {
                console.warn(`🔍 Filtered out ${this.leads.length - validLeads.length} invalid leads`);
            }

            // Generate table HTML with error handling for each lead
            const tableHTML = validLeads.map((lead, index) => {
                try {
                    return this.renderLeadRow(lead);
                } catch (error) {
                    console.error(`🔍 Error rendering lead at index ${index}:`, error, lead);
                    return this.renderErrorRow(index, error.message);
                }
            }).join('');
            
            // Update table content
            tbody.innerHTML = tableHTML;
            console.log('🔍 Table HTML updated, tbody now contains', tbody.children.length, 'rows');
            
            // Add loading state management for table interactions
            this.addTableInteractionHandlers();
            
        } catch (error) {
            console.error('🔍 Critical error in renderLeads():', error);
            this.showError(`Failed to render table: ${error.message}`);
        }
    },

    // Render individual lead row with error handling
    renderLeadRow: function(lead) {
        // Sanitize and validate lead data
        const safeData = {
            leadId: lead.leadId || 'unknown',
            firstName: window.EasyCRM.Utils.sanitizeHtml(lead.firstName || 'N/A'),
            lastName: window.EasyCRM.Utils.sanitizeHtml(lead.lastName || 'N/A'),
            title: window.EasyCRM.Utils.sanitizeHtml(lead.title || 'N/A'),
            company: window.EasyCRM.Utils.sanitizeHtml(lead.company || 'N/A'),
            email: lead.email && lead.email !== 'N/A' ? window.EasyCRM.Utils.sanitizeHtml(lead.email) : null,
            phone: lead.phone && lead.phone !== 'N/A' ? window.EasyCRM.Utils.sanitizeHtml(lead.phone) : null
        };

        return `
            <tr class="hover:bg-gray-50 cursor-pointer transition-colors duration-150" 
                onclick="window.EasyCRM.Leads.showLeadDetail('${safeData.leadId}')"
                data-lead-id="${safeData.leadId}">
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${safeData.firstName}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${safeData.lastName}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${safeData.title}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${safeData.company}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${safeData.email ? 
                        `<a href="mailto:${safeData.email}" class="text-blue-600 hover:text-blue-800 transition-colors duration-150" onclick="event.stopPropagation()">${safeData.email}</a>` : 
                        'N/A'
                    }
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${safeData.phone ? 
                        `<a href="tel:${safeData.phone}" class="text-blue-600 hover:text-blue-800 transition-colors duration-150" onclick="event.stopPropagation()">${safeData.phone}</a>` : 
                        'N/A'
                    }
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div class="flex items-center space-x-2">
                        <button onclick="event.stopPropagation(); window.EasyCRM.Leads.showLeadDetail('${safeData.leadId}')" 
                                class="text-blue-600 hover:text-blue-800 transition-colors duration-150" 
                                title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                        ${safeData.email ? 
                            `<button onclick="event.stopPropagation(); window.open('mailto:${safeData.email}', '_blank')" 
                                    class="text-green-600 hover:text-green-800 transition-colors duration-150" 
                                    title="Send Email">
                                <i class="fas fa-envelope"></i>
                            </button>` : 
                            ''
                        }
                        ${safeData.phone ? 
                            `<button onclick="event.stopPropagation(); window.open('tel:${safeData.phone}', '_blank')" 
                                    class="text-green-600 hover:text-green-800 transition-colors duration-150" 
                                    title="Call">
                                <i class="fas fa-phone"></i>
                            </button>` : 
                            ''
                        }
                    </div>
                </td>
            </tr>
        `;
    },

    // Render error row for leads that failed to render
    renderErrorRow: function(index, errorMessage) {
        return `
            <tr class="bg-red-50">
                <td colspan="7" class="px-6 py-4 text-center text-sm text-red-600">
                    <i class="fas fa-exclamation-triangle mr-2"></i>
                    Error rendering lead ${index + 1}: ${window.EasyCRM.Utils.sanitizeHtml(errorMessage)}
                </td>
            </tr>
        `;
    },

    // Add interaction handlers for table elements
    addTableInteractionHandlers: function() {
        // Add loading states for action buttons
        const actionButtons = document.querySelectorAll('#leads-tbody button');
        actionButtons.forEach(button => {
            button.addEventListener('click', function(event) {
                // Add loading state to clicked button
                const originalContent = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                this.disabled = true;
                
                // Restore button after a short delay (for visual feedback)
                setTimeout(() => {
                    this.innerHTML = originalContent;
                    this.disabled = false;
                }, 500);
            });
        });
    },

    // Handle filter changes
    handleFilterChange: function() {
        console.log('🔍 FILTER DEBUG: handleFilterChange() called');
        
        const filters = {};
        
        // Collect all filter values
        ['firstName', 'lastName', 'title', 'company', 'email', 'phone'].forEach(field => {
            const input = document.getElementById(`filter-${field}`);
            if (input && input.value.trim()) {
                filters[field] = input.value.trim();
            }
        });

        console.log('🔍 New filters collected:', filters);
        console.log('🔍 Previous filters:', this.currentFilters);
        
        // Check if filters actually changed
        const filtersChanged = JSON.stringify(filters) !== JSON.stringify(this.currentFilters);
        
        if (filtersChanged) {
            this.currentFilters = filters;
            this.currentPage = 1; // Reset to first page when filtering changes
            console.log('🔍 Filters changed, resetting to page 1 and reloading');
            this.loadLeads();
        } else {
            console.log('🔍 Filters unchanged, no reload needed');
        }
    },

    // Clear all filters
    clearFilters: function() {
        console.log('🔍 FILTER DEBUG: clearFilters() called');
        
        // Clear filter inputs
        ['firstName', 'lastName', 'title', 'company', 'email', 'phone'].forEach(field => {
            const input = document.getElementById(`filter-${field}`);
            if (input) {
                input.value = '';
            }
        });

        // Only reload if filters were actually set
        const hadFilters = Object.keys(this.currentFilters).length > 0;
        
        this.currentFilters = {};
        this.currentPage = 1;
        
        if (hadFilters) {
            console.log('🔍 Filters cleared, reloading data');
            this.loadLeads();
        } else {
            console.log('🔍 No filters to clear');
        }
    },

    // Handle column sorting
    handleSort: function(field) {
        console.log('🔍 SORT DEBUG: handleSort() called with field:', field);
        console.log('🔍 Current sort state:', this.currentSort);
        
        const previousSort = { ...this.currentSort };
        
        if (this.currentSort.field === field) {
            // Toggle sort order
            this.currentSort.order = this.currentSort.order === 'asc' ? 'desc' : 'asc';
        } else {
            // New field, default to ascending
            this.currentSort.field = field;
            this.currentSort.order = 'asc';
        }

        console.log('🔍 New sort state:', this.currentSort);
        
        // Reset to first page when sorting changes
        this.currentPage = 1;
        
        this.updateSortIndicators();
        
        // Only reload if sort actually changed
        const sortChanged = (
            previousSort.field !== this.currentSort.field ||
            previousSort.order !== this.currentSort.order
        );
        
        if (sortChanged) {
            console.log('🔍 Sort changed, reloading data');
            this.loadLeads();
        } else {
            console.log('🔍 Sort unchanged, no reload needed');
        }
    },

    // Update sort indicators in table headers
    updateSortIndicators: function() {
        // Reset all sort indicators
        const headers = document.querySelectorAll('[data-sort]');
        headers.forEach(header => {
            header.classList.remove('sort-asc', 'sort-desc');
        });

        // Set current sort indicator
        if (this.currentSort.field) {
            const currentHeader = document.querySelector(`[data-sort="${this.currentSort.field}"]`);
            if (currentHeader) {
                currentHeader.classList.add(this.currentSort.order === 'asc' ? 'sort-asc' : 'sort-desc');
            }
        }
    },

    // Update pagination controls
    updatePagination: function() {
        console.log('🔍 PAGINATION DEBUG: updatePagination() called');
        
        const showingFrom = document.getElementById('showing-from');
        const showingTo = document.getElementById('showing-to');
        const totalLeadsSpan = document.getElementById('total-leads');
        const pageInfo = document.getElementById('page-info');
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');

        // Calculate showing range
        const from = this.totalLeads === 0 ? 0 : ((this.currentPage - 1) * this.pageSize) + 1;
        const to = Math.min(this.currentPage * this.pageSize, this.totalLeads);

        console.log('🔍 Pagination calculations:', {
            from: from,
            to: to,
            currentPage: this.currentPage,
            pageSize: this.pageSize,
            totalLeads: this.totalLeads,
            totalPages: this.totalPages
        });

        // Update display
        showingFrom.textContent = from;
        showingTo.textContent = to;
        totalLeadsSpan.textContent = this.totalLeads;
        pageInfo.textContent = `Page ${this.currentPage} of ${this.totalPages}`;

        console.log('🔍 Updated pagination display:', {
            showingText: `${from} to ${to} of ${this.totalLeads}`,
            pageText: `Page ${this.currentPage} of ${this.totalPages}`
        });

        // Update button states (only if not currently loading)
        if (!this.isLoading) {
            this.setPaginationButtonsState(false);
        }
        
        console.log('🔍 Button states:', {
            prevDisabled: this.currentPage <= 1,
            nextDisabled: this.currentPage >= this.totalPages,
            isLoading: this.isLoading
        });
    },

    // Update export button state
    updateExportButton: function() {
        const exportBtn = document.getElementById('export-btn');
        exportBtn.disabled = this.totalLeads === 0;
    },

    // Show lead detail modal
    showLeadDetail: async function(leadId) {
        try {
            const modal = document.getElementById('lead-modal');
            const modalContent = document.getElementById('modal-content');
            
            // Show loading in modal
            modalContent.innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-spinner fa-spin text-2xl text-gray-400 mb-4"></i>
                    <p class="text-gray-600">Loading lead details...</p>
                </div>
            `;
            
            modal.classList.remove('hidden');

            // Find lead in current data or fetch from API
            let lead = this.leads.find(l => l.leadId === leadId);
            if (!lead) {
                lead = await window.EasyCRM.API.leads.getLead(leadId);
            }

            // Render lead details
            modalContent.innerHTML = `
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700">First Name</label>
                            <p class="mt-1 text-sm text-gray-900">${window.EasyCRM.Utils.sanitizeHtml(lead.firstName || 'N/A')}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Last Name</label>
                            <p class="mt-1 text-sm text-gray-900">${window.EasyCRM.Utils.sanitizeHtml(lead.lastName || 'N/A')}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Title</label>
                            <p class="mt-1 text-sm text-gray-900">${window.EasyCRM.Utils.sanitizeHtml(lead.title || 'N/A')}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Company</label>
                            <p class="mt-1 text-sm text-gray-900">${window.EasyCRM.Utils.sanitizeHtml(lead.company || 'N/A')}</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Email</label>
                            <p class="mt-1 text-sm text-gray-900">
                                ${lead.email && lead.email !== 'N/A' ? 
                                    `<a href="mailto:${window.EasyCRM.Utils.sanitizeHtml(lead.email)}" class="text-blue-600 hover:text-blue-800">${window.EasyCRM.Utils.sanitizeHtml(lead.email)}</a>` : 
                                    'N/A'
                                }
                            </p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Phone</label>
                            <p class="mt-1 text-sm text-gray-900">
                                ${lead.phone && lead.phone !== 'N/A' ? 
                                    `<a href="tel:${window.EasyCRM.Utils.sanitizeHtml(lead.phone)}" class="text-blue-600 hover:text-blue-800">${window.EasyCRM.Utils.sanitizeHtml(lead.phone)}</a>` : 
                                    'N/A'
                                }
                            </p>
                        </div>
                        <div class="col-span-2">
                            <label class="block text-sm font-medium text-gray-700">Remarks</label>
                            <p class="mt-1 text-sm text-gray-900 whitespace-pre-wrap">${window.EasyCRM.Utils.sanitizeHtml(lead.remarks || 'N/A')}</p>
                        </div>
                        ${lead.createdAt ? `
                        <div class="col-span-2">
                            <label class="block text-sm font-medium text-gray-700">Created</label>
                            <p class="mt-1 text-sm text-gray-900">${window.EasyCRM.Utils.formatDate(lead.createdAt)}</p>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;

        } catch (error) {
            console.error('Error loading lead details:', error);
            modalContent.innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-exclamation-triangle text-4xl text-red-400 mb-4"></i>
                    <p class="text-lg text-gray-600 mb-2">Error Loading Lead</p>
                    <p class="text-sm text-gray-500">${error.message}</p>
                </div>
            `;
        }
    },

    // Export leads as CSV
    exportLeads: async function() {
        try {
            const exportBtn = document.getElementById('export-btn');
            const originalText = exportBtn.innerHTML;
            
            exportBtn.disabled = true;
            exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Exporting...';

            const response = await window.EasyCRM.API.export.exportLeads(this.currentFilters);
            
            // Create and download file
            const blob = new Blob([atob(response.csvData)], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = response.filename || 'leads-export.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            window.EasyCRM.Utils.showToast('Export completed successfully!', 'success');

        } catch (error) {
            console.error('Export error:', error);
            window.EasyCRM.API.utils.handleError(error, 'exporting leads');
        } finally {
            const exportBtn = document.getElementById('export-btn');
            exportBtn.disabled = this.totalLeads === 0;
            exportBtn.innerHTML = '<i class="fas fa-download mr-2"></i>Export CSV';
        }
    },

    // Refresh leads data
    refreshLeads: function() {
        this.loadLeads();
        window.EasyCRM.Utils.showToast('Leads refreshed', 'info');
    },

    // Refresh lead table while maintaining current pagination and filter settings
    refreshLeadTable: function() {
        console.log('🔍 Refreshing lead table while maintaining current state');
        console.log('🔍 Current state before refresh:', {
            currentPage: this.currentPage,
            pageSize: this.pageSize,
            totalPages: this.totalPages,
            totalLeads: this.totalLeads,
            filters: this.currentFilters,
            sort: this.currentSort
        });

        // Store current state to ensure it's maintained
        const currentState = {
            page: this.currentPage,
            pageSize: this.pageSize,
            filters: { ...this.currentFilters },
            sort: { ...this.currentSort }
        };

        // Reload data with current parameters maintained
        this.loadLeads().then(() => {
            console.log('🔍 Lead table refreshed successfully');
            console.log('🔍 State after refresh:', {
                currentPage: this.currentPage,
                pageSize: this.pageSize,
                totalPages: this.totalPages,
                totalLeads: this.totalLeads,
                filters: this.currentFilters,
                sort: this.currentSort
            });

            // Show brief confirmation message
            if (window.EasyCRM.Utils && window.EasyCRM.Utils.showToast) {
                window.EasyCRM.Utils.showToast('Lead table updated with new data!', 'success', 3000);
            }
        }).catch((error) => {
            console.error('🔍 Error refreshing lead table:', error);
            
            // Show error message
            if (window.EasyCRM.Utils && window.EasyCRM.Utils.showToast) {
                window.EasyCRM.Utils.showToast('Failed to refresh lead table. Please try again.', 'error');
            }
        });
    },

    // Get current filter summary
    getFilterSummary: function() {
        const activeFilters = Object.keys(this.currentFilters).length;
        return {
            hasFilters: activeFilters > 0,
            filterCount: activeFilters,
            filters: { ...this.currentFilters }
        };
    },

    // Retry loading with current parameters
    retryLoad: function() {
        console.log('🔍 Retrying load with current parameters');
        this.loadLeads();
    },

    // Reset all parameters and reload
    resetAndReload: function() {
        console.log('🔍 Resetting parameters and reloading');
        
        // Reset pagination
        this.currentPage = 1;
        this.totalPages = 1;
        this.totalLeads = 0;
        
        // Clear filters
        this.currentFilters = {};
        ['firstName', 'lastName', 'title', 'company', 'email', 'phone'].forEach(field => {
            const input = document.getElementById(`filter-${field}`);
            if (input) {
                input.value = '';
            }
        });
        
        // Reset sorting
        this.currentSort = { field: null, order: 'asc' };
        this.updateSortIndicators();
        
        // Reload data
        this.loadLeads();
        
        window.EasyCRM.Utils.showToast('Parameters reset, reloading data...', 'info');
    }
};

// Global error handler for pagination debugging
window.addEventListener('error', function(event) {
    if (event.filename && event.filename.includes('leads.js')) {
        console.error('🔍 PAGINATION DEBUG: JavaScript error in leads.js:', {
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno,
            error: event.error
        });
    }
});

// Close modal when clicking outside or on close button
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('lead-modal');
    const closeBtn = document.getElementById('close-modal');

    closeBtn.addEventListener('click', () => {
        modal.classList.add('hidden');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
        }
    });
});