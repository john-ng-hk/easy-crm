// Configuration for Easy CRM application
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.Config = {
    // API Configuration
    API: {
        BASE_URL: '', // Will be set dynamically from CloudFormation outputs
        ENDPOINTS: {
            UPLOAD: '/upload',
            LEADS: '/leads',
            EXPORT: '/export',
            CHAT: '/chat',
            STATUS: '/status'
        },
        TIMEOUT: 30000 // 30 seconds
    },

    // AWS Cognito Configuration
    COGNITO: {
        USER_POOL_ID: '', // Will be set dynamically
        CLIENT_ID: '', // Will be set dynamically
        REGION: 'ap-southeast-1'
    },

    // Application Settings
    APP: {
        PAGE_SIZE: 50,
        MAX_FILE_SIZE: 10 * 1024 * 1024, // 10MB
        ALLOWED_FILE_TYPES: ['.csv', '.xlsx', '.xls'],
        UPLOAD_TIMEOUT: 300000, // 5 minutes
        CHAT_MAX_MESSAGES: 100
    },

    // UI Settings
    UI: {
        DEBOUNCE_DELAY: 300, // ms
        ANIMATION_DURATION: 300, // ms
        TOAST_DURATION: 5000, // ms
        RETRY_ATTEMPTS: 3
    }
};

// Initialize configuration from CloudFormation outputs or environment
window.EasyCRM.Config.init = function() {
    // Configuration is loaded by app.js from config.json
    console.log('EasyCRM Configuration initialized');
};

// Utility functions
window.EasyCRM.Utils = {
    // Debounce function for search inputs
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Format file size
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Format date
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    },

    // Validate email
    isValidEmail: function(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    // Generate UUID
    generateUUID: function() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },

    // Show toast notification
    showToast: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `fixed top-4 right-4 z-50 p-4 rounded-md shadow-lg max-w-sm ${this.getToastClasses(type)}`;
        toast.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${this.getToastIcon(type)} mr-3"></i>
                <span class="text-sm font-medium">${message}</span>
                <button class="ml-4 text-current opacity-70 hover:opacity-100" onclick="this.parentElement.parentElement.remove()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Auto remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, window.EasyCRM.Config.UI.TOAST_DURATION);
    },

    getToastClasses: function(type) {
        const classes = {
            success: 'bg-green-100 text-green-800 border border-green-200',
            error: 'bg-red-100 text-red-800 border border-red-200',
            warning: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
            info: 'bg-blue-100 text-blue-800 border border-blue-200'
        };
        return classes[type] || classes.info;
    },

    getToastIcon: function(type) {
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        return icons[type] || icons.info;
    },

    // Show loading spinner
    showLoading: function(element, message = 'Loading...') {
        element.innerHTML = `
            <div class="flex items-center justify-center py-8">
                <i class="fas fa-spinner fa-spin text-2xl text-gray-400 mr-3"></i>
                <span class="text-gray-600">${message}</span>
            </div>
        `;
    },

    // Sanitize HTML to prevent XSS
    sanitizeHtml: function(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};