// Chat interface functionality
window.EasyCRM = window.EasyCRM || {};

window.EasyCRM.Chat = {
    isOpen: false,
    messages: [],
    isProcessing: false,
    
    // Initialize chat functionality
    init: function() {
        this.attachEventHandlers();
        this.loadChatHistory();
    },

    // Attach event handlers
    attachEventHandlers: function() {
        const chatFab = document.getElementById('chat-fab');
        const chatToggle = document.getElementById('chat-toggle');
        const chatInput = document.getElementById('chat-input');
        const chatSend = document.getElementById('chat-send');

        // Chat FAB click
        chatFab.addEventListener('click', () => {
            this.toggleChat();
        });

        // Chat toggle button
        chatToggle.addEventListener('click', () => {
            this.toggleChat();
        });

        // Chat input enter key
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Send button click
        chatSend.addEventListener('click', () => {
            this.sendMessage();
        });

        // Auto-resize chat input
        chatInput.addEventListener('input', () => {
            this.autoResizeInput(chatInput);
        });
    },

    // Toggle chat widget visibility
    toggleChat: function() {
        const chatWidget = document.getElementById('chat-widget');
        const chatFab = document.getElementById('chat-fab');
        const chatToggle = document.getElementById('chat-toggle');

        if (this.isOpen) {
            // Close chat
            chatWidget.classList.add('hidden');
            chatFab.classList.remove('hidden');
            chatToggle.innerHTML = '<i class="fas fa-minus"></i>';
            this.isOpen = false;
        } else {
            // Open chat
            chatWidget.classList.remove('hidden');
            chatFab.classList.add('hidden');
            chatToggle.innerHTML = '<i class="fas fa-times"></i>';
            this.isOpen = true;
            
            // Focus on input
            setTimeout(() => {
                document.getElementById('chat-input').focus();
            }, 100);
        }
    },

    // Send message to chatbot
    sendMessage: async function() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();

        if (!message || this.isProcessing) {
            return;
        }

        // Clear input
        chatInput.value = '';
        this.autoResizeInput(chatInput);

        // Add user message to chat
        this.addMessage('user', message);

        // Show typing indicator
        this.showTypingIndicator();

        try {
            this.isProcessing = true;
            
            // Send to API
            const response = await window.EasyCRM.API.chat.sendMessage(
                message, 
                window.EasyCRM.Auth.currentUser?.username || 'anonymous'
            );

            // Remove typing indicator
            this.hideTypingIndicator();

            // Add bot response
            this.addMessage('bot', response.response || 'I apologize, but I couldn\'t process your request. Please try rephrasing your question.');

            // If the response includes lead data, offer to show it
            if (response.leads && response.leads.length > 0) {
                this.addLeadResults(response.leads);
            }

        } catch (error) {
            console.error('Chat error:', error);
            this.hideTypingIndicator();
            this.addMessage('bot', 'I\'m sorry, I\'m having trouble processing your request right now. Please try again later.');
        } finally {
            this.isProcessing = false;
        }
    },

    // Add message to chat
    addMessage: function(sender, content, timestamp = null) {
        const messagesContainer = document.getElementById('chat-messages');
        const messageTime = timestamp || new Date();
        
        const messageElement = document.createElement('div');
        messageElement.className = 'flex items-start space-x-2 chat-message';

        if (sender === 'user') {
            messageElement.innerHTML = `
                <div class="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <i class="fas fa-user text-white text-sm"></i>
                </div>
                <div class="bg-blue-600 text-white rounded-lg p-3 max-w-xs">
                    <p class="text-sm">${window.EasyCRM.Utils.sanitizeHtml(content)}</p>
                    <p class="text-xs opacity-75 mt-1">${this.formatTime(messageTime)}</p>
                </div>
            `;
        } else {
            messageElement.innerHTML = `
                <div class="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center flex-shrink-0">
                    <i class="fas fa-robot text-white text-sm"></i>
                </div>
                <div class="bg-gray-100 rounded-lg p-3 max-w-xs">
                    <p class="text-sm text-gray-800">${this.formatBotMessage(content)}</p>
                    <p class="text-xs text-gray-500 mt-1">${this.formatTime(messageTime)}</p>
                </div>
            `;
        }

        messagesContainer.appendChild(messageElement);
        this.scrollToBottom();

        // Store message
        this.messages.push({
            sender,
            content,
            timestamp: messageTime.toISOString()
        });

        // Limit message history
        if (this.messages.length > window.EasyCRM.Config.APP.CHAT_MAX_MESSAGES) {
            this.messages = this.messages.slice(-window.EasyCRM.Config.APP.CHAT_MAX_MESSAGES);
        }

        this.saveChatHistory();
    },

    // Format bot message content (handle markdown-like formatting)
    formatBotMessage: function(content) {
        // Simple formatting for bot responses
        let formatted = window.EasyCRM.Utils.sanitizeHtml(content);
        
        // Bold text
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Italic text
        formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
        
        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');
        
        return formatted;
    },

    // Show typing indicator
    showTypingIndicator: function() {
        const messagesContainer = document.getElementById('chat-messages');
        
        const typingElement = document.createElement('div');
        typingElement.id = 'typing-indicator';
        typingElement.className = 'flex items-start space-x-2';
        typingElement.innerHTML = `
            <div class="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-robot text-white text-sm"></i>
            </div>
            <div class="bg-gray-100 rounded-lg p-3">
                <div class="flex space-x-1">
                    <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                    <div class="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                </div>
            </div>
        `;

        messagesContainer.appendChild(typingElement);
        this.scrollToBottom();
    },

    // Hide typing indicator
    hideTypingIndicator: function() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    },

    // Add lead results to chat
    addLeadResults: function(leads) {
        const messagesContainer = document.getElementById('chat-messages');
        
        const resultsElement = document.createElement('div');
        resultsElement.className = 'flex items-start space-x-2 chat-message';
        
        const leadsList = leads.slice(0, 5).map(lead => `
            <div class="border-b border-gray-200 pb-2 mb-2 last:border-b-0 last:mb-0">
                <div class="font-medium text-sm">${window.EasyCRM.Utils.sanitizeHtml(lead.firstName || '')} ${window.EasyCRM.Utils.sanitizeHtml(lead.lastName || '')}</div>
                <div class="text-xs text-gray-600">${window.EasyCRM.Utils.sanitizeHtml(lead.company || 'N/A')}</div>
                <div class="text-xs text-gray-600">${window.EasyCRM.Utils.sanitizeHtml(lead.email || 'N/A')}</div>
            </div>
        `).join('');

        resultsElement.innerHTML = `
            <div class="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-robot text-white text-sm"></i>
            </div>
            <div class="bg-gray-100 rounded-lg p-3 max-w-sm">
                <div class="text-sm text-gray-800 mb-2">
                    <strong>Found ${leads.length} lead${leads.length !== 1 ? 's' : ''}:</strong>
                </div>
                <div class="text-xs space-y-2">
                    ${leadsList}
                </div>
                ${leads.length > 5 ? `
                    <div class="text-xs text-gray-500 mt-2">
                        And ${leads.length - 5} more...
                    </div>
                ` : ''}
                <button onclick="window.EasyCRM.Chat.applyLeadFilter(${JSON.stringify(leads).replace(/"/g, '&quot;')})" 
                        class="mt-2 text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700">
                    View in Table
                </button>
            </div>
        `;

        messagesContainer.appendChild(resultsElement);
        this.scrollToBottom();
    },

    // Apply lead filter based on chat results
    applyLeadFilter: function(leads) {
        // This would integrate with the leads table to show these specific results
        // For now, we'll just show a message
        window.EasyCRM.Utils.showToast(`Found ${leads.length} leads matching your query`, 'info');
        
        // Close chat and focus on leads table
        if (this.isOpen) {
            this.toggleChat();
        }
    },

    // Auto-resize chat input
    autoResizeInput: function(input) {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 100) + 'px';
    },

    // Scroll chat to bottom
    scrollToBottom: function() {
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    },

    // Format time for display
    formatTime: function(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },

    // Load chat history from localStorage
    loadChatHistory: function() {
        try {
            const stored = localStorage.getItem('easyCRM_chatHistory');
            if (stored) {
                this.messages = JSON.parse(stored);
                this.renderChatHistory();
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
            this.messages = [];
        }
    },

    // Save chat history to localStorage
    saveChatHistory: function() {
        try {
            localStorage.setItem('easyCRM_chatHistory', JSON.stringify(this.messages));
        } catch (error) {
            console.error('Error saving chat history:', error);
        }
    },

    // Render existing chat history
    renderChatHistory: function() {
        const messagesContainer = document.getElementById('chat-messages');
        
        // Clear existing messages (except welcome message)
        const welcomeMessage = messagesContainer.querySelector('.chat-message');
        messagesContainer.innerHTML = '';
        if (welcomeMessage) {
            messagesContainer.appendChild(welcomeMessage);
        }

        // Render stored messages
        this.messages.forEach(message => {
            this.addMessage(message.sender, message.content, new Date(message.timestamp));
        });
    },

    // Clear chat history
    clearHistory: function() {
        this.messages = [];
        localStorage.removeItem('easyCRM_chatHistory');
        
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.innerHTML = `
            <div class="flex items-start space-x-2">
                <div class="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center">
                    <i class="fas fa-robot text-white text-sm"></i>
                </div>
                <div class="bg-gray-100 rounded-lg p-3 max-w-xs">
                    <p class="text-sm">Hi! I'm your lead assistant. Ask me anything about your leads, like "Show me all leads from tech companies" or "How many leads do we have?"</p>
                </div>
            </div>
        `;
        
        window.EasyCRM.Utils.showToast('Chat history cleared', 'info');
    },

    // Get suggested questions based on current data
    getSuggestedQuestions: function() {
        return [
            "How many leads do we have?",
            "Show me leads from tech companies",
            "Who are our most recent leads?",
            "Find leads without email addresses",
            "Show me leads by company size",
            "What companies have the most leads?"
        ];
    },

    // Add suggested questions to chat
    showSuggestedQuestions: function() {
        const suggestions = this.getSuggestedQuestions();
        const messagesContainer = document.getElementById('chat-messages');
        
        const suggestionsElement = document.createElement('div');
        suggestionsElement.className = 'flex items-start space-x-2 chat-message';
        suggestionsElement.innerHTML = `
            <div class="w-8 h-8 bg-gray-600 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-robot text-white text-sm"></i>
            </div>
            <div class="bg-gray-100 rounded-lg p-3 max-w-sm">
                <p class="text-sm text-gray-800 mb-2">Here are some things you can ask me:</p>
                <div class="space-y-1">
                    ${suggestions.map(question => `
                        <button onclick="document.getElementById('chat-input').value='${question}'; window.EasyCRM.Chat.sendMessage();" 
                                class="block w-full text-left text-xs bg-white border border-gray-200 rounded px-2 py-1 hover:bg-gray-50">
                            ${question}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;

        messagesContainer.appendChild(suggestionsElement);
        this.scrollToBottom();
    }
};