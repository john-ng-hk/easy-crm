# Easy CRM Frontend

A responsive web application for lead management built with vanilla HTML, CSS, and JavaScript.

## Features

- **File Upload**: Drag-and-drop CSV/Excel file upload with progress indication
- **Lead Management**: Sortable, filterable table with pagination
- **Natural Language Chat**: AI-powered chat interface for querying lead data
- **Data Export**: CSV export with filter awareness
- **Authentication**: AWS Cognito integration for secure access
- **Responsive Design**: Works on desktop, tablet, and mobile devices

## Architecture

### Technology Stack

- **HTML5**: Semantic markup with accessibility features
- **CSS3**: Tailwind CSS for responsive design and styling
- **JavaScript**: Vanilla ES6+ with modular architecture
- **AWS Cognito**: Authentication and user management
- **AWS SDK**: For Cognito integration

### File Structure

```
frontend/
├── index.html              # Main application page
├── config.json            # Configuration file (generated during deployment)
├── css/
│   └── styles.css         # Custom CSS styles and animations
├── js/
│   ├── config.js          # Application configuration and utilities
│   ├── auth.js            # AWS Cognito authentication
│   ├── api.js             # API communication layer
│   ├── upload.js          # File upload functionality
│   ├── leads.js           # Lead management and table operations
│   ├── chat.js            # Chat interface and AI integration
│   └── app.js             # Main application initialization
└── assets/                # Static assets (images, icons)
```

### Module Dependencies

```
app.js (main)
├── config.js (configuration & utilities)
├── auth.js (authentication)
│   └── AWS Cognito SDK
├── api.js (API communication)
│   └── auth.js (for tokens)
├── upload.js (file upload)
│   └── api.js (for presigned URLs)
├── leads.js (lead management)
│   └── api.js (for data operations)
└── chat.js (chat interface)
    └── api.js (for chatbot communication)
```

## Configuration

The application uses a `config.json` file that is generated during deployment with the actual AWS resource URLs and IDs:

```json
{
  "api": {
    "baseUrl": "https://your-api-gateway-url.execute-api.ap-southeast-1.amazonaws.com/prod"
  },
  "cognito": {
    "userPoolId": "ap-southeast-1_XXXXXXXXX",
    "clientId": "your-cognito-client-id",
    "region": "ap-southeast-1"
  },
  "app": {
    "name": "Easy CRM",
    "version": "1.0.0",
    "environment": "production"
  }
}
```

## Deployment

### Automatic Deployment

Use the deployment script to automatically deploy the frontend:

```bash
./scripts/deploy-frontend.sh
```

This script will:
1. Get the S3 bucket name from CloudFormation
2. Get API Gateway and Cognito configuration
3. Generate the configuration file
4. Upload all frontend files to S3
5. Display access URLs

### Manual Deployment

1. **Build Configuration**:
   ```bash
   # Get values from CloudFormation stack
   aws cloudformation describe-stacks --stack-name easy-crm --profile nch-prod
   
   # Update config.json with actual values
   ```

2. **Upload to S3**:
   ```bash
   # Upload files to S3 website bucket
   aws s3 sync frontend/ s3://your-website-bucket/ --profile nch-prod
   ```

## Development

### Local Development

For local development, you can serve the files using a simple HTTP server:

```bash
# Using Python
cd frontend
python3 -m http.server 8000

# Using Node.js
npx http-server frontend -p 8000

# Using PHP
cd frontend
php -S localhost:8000
```

Then update `config.json` to point to your development API endpoints.

### Testing

The application includes built-in error handling and debugging features:

- **Console Logging**: Detailed logs for debugging
- **Error Tracking**: Automatic error logging to localStorage
- **Performance Monitoring**: API request timing and page load metrics
- **Debug Interface**: Access via `window.EasyCRM.debug`

### Debug Commands

Open browser console and use these commands:

```javascript
// Get application status
window.EasyCRM.debug.getStatus()

// View error logs
window.EasyCRM.debug.getErrors()

// Clear error logs
window.EasyCRM.debug.clearErrors()

// Reinitialize application
window.EasyCRM.debug.reinitialize()
```

## Browser Support

- **Modern Browsers**: Chrome 70+, Firefox 65+, Safari 12+, Edge 79+
- **Mobile Browsers**: iOS Safari 12+, Chrome Mobile 70+
- **Features Used**: ES6+, Fetch API, CSS Grid, Flexbox

## Security Features

- **Content Security Policy**: Prevents XSS attacks
- **Input Sanitization**: All user inputs are sanitized
- **JWT Token Handling**: Secure token storage and refresh
- **HTTPS Only**: All communications over HTTPS
- **CORS Protection**: Proper CORS configuration

## Performance Optimizations

- **Lazy Loading**: Modules loaded on demand
- **Debounced Inputs**: Search and filter inputs are debounced
- **Efficient Rendering**: Virtual scrolling for large datasets
- **Caching**: Appropriate cache headers for static assets
- **Compression**: Gzip compression for text files

## Accessibility

- **WCAG 2.1 AA**: Compliant with accessibility standards
- **Keyboard Navigation**: Full keyboard support
- **Screen Readers**: ARIA labels and semantic HTML
- **Color Contrast**: Sufficient contrast ratios
- **Focus Management**: Proper focus handling

## Troubleshooting

### Common Issues

1. **Configuration Not Loading**:
   - Check that `config.json` exists and is valid
   - Verify API Gateway and Cognito URLs are correct

2. **Authentication Errors**:
   - Ensure Cognito User Pool and Client ID are correct
   - Check that the user pool allows the required authentication flows

3. **API Errors**:
   - Verify API Gateway URL and endpoints
   - Check CORS configuration
   - Ensure Lambda functions are deployed

4. **Upload Failures**:
   - Check file size limits
   - Verify S3 bucket permissions
   - Ensure presigned URL generation is working

### Browser Console Errors

Check the browser console for detailed error messages. The application logs all errors with context information.

### Network Issues

Use browser developer tools to inspect network requests and responses for API calls.

## Contributing

When making changes to the frontend:

1. **Test Locally**: Always test changes locally first
2. **Validate HTML**: Ensure HTML is valid and semantic
3. **Check Accessibility**: Test with screen readers and keyboard navigation
4. **Performance**: Monitor bundle size and loading times
5. **Browser Testing**: Test in multiple browsers and devices

## License

This project is licensed under the MIT License - see the LICENSE file for details.