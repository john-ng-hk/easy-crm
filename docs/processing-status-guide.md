# Processing Status Indicator User Guide

## Overview

The Processing Status Indicator provides real-time feedback during file upload and lead processing operations. This feature helps you understand what's happening with your data and provides control over long-running operations.

## Getting Started

### Uploading a File

1. **Select Your File**: Click "Choose File" or drag and drop your CSV/Excel file
2. **Start Upload**: Click "Upload File" to begin processing
3. **Monitor Progress**: The status indicator will automatically appear and show progress

### Status Display

The status indicator shows:
- **Current Stage**: What operation is currently running
- **Progress Bar**: Visual progress for batch processing
- **Estimated Time**: Time remaining for completion (for operations > 30 seconds)
- **Cancel Button**: Option to stop processing if needed

## Status Stages

### 1. File Uploading
- **What it means**: Your file is being uploaded to secure cloud storage
- **Duration**: Usually 1-5 seconds depending on file size
- **What you see**: "File Uploading..." with a spinner

### 2. File Uploaded
- **What it means**: Upload completed, file processing is starting
- **Duration**: Brief transition stage (1-2 seconds)
- **What you see**: "File Uploaded" confirmation

### 3. Leads Processing
- **What it means**: File is being read and split into batches for AI processing
- **Duration**: 5-30 seconds depending on file size and worksheet count
- **What you see**: "Leads Processing..." with progress updates

### 4. Batch Processing
- **What it means**: AI is standardizing your lead data in batches
- **Duration**: 30 seconds to several minutes for large files
- **What you see**: Progress bar showing "Processing batch X of Y" with estimated completion time

### 5. Completed
- **What it means**: All leads have been processed and added to your database
- **Duration**: Status shows for 3 seconds before auto-hiding
- **What you see**: "Processing Complete!" with total leads processed
- **Auto-action**: Lead table automatically refreshes to show new data

## Progress Information

### Progress Bar
- Shows percentage completion for batch processing
- Updates in real-time as each batch completes
- Includes visual animation for smooth progress indication

### Batch Information
- **Total Batches**: How many batches your file was split into
- **Completed Batches**: How many have finished processing
- **Processed Leads**: Running count of leads added to database

### Time Estimation
- **Appears**: For operations taking longer than 30 seconds
- **Calculation**: Based on current processing rate
- **Updates**: Refreshes as processing continues

## Cancellation

### When to Cancel
- File is taking too long to process
- You uploaded the wrong file
- You need to make changes to your data

### How to Cancel
1. Click the "Cancel" button in the status indicator
2. Confirm cancellation in the popup dialog
3. Wait for cancellation confirmation

### What Happens When You Cancel
- **In Progress**: Current batch finishes, but no new batches start
- **Partial Data**: Any completed batches remain in your database
- **Status Update**: Shows "Processing Cancelled" message
- **Cleanup**: Incomplete processing data is automatically cleaned up

## Error Handling

### Common Errors

#### File Format Errors
- **Cause**: Unsupported file format or corrupted file
- **Message**: "File format not supported" or "File could not be read"
- **Solution**: Check file format (CSV, .xlsx, .xls) and try re-saving

#### Processing Errors
- **Cause**: AI service temporarily unavailable or data format issues
- **Message**: "Processing failed" with specific error details
- **Solution**: Wait a few minutes and try again, or contact support

#### Network Errors
- **Cause**: Internet connection issues during upload or processing
- **Message**: "Connection error" or "Upload failed"
- **Solution**: Check internet connection and retry

### Error Recovery
- **Automatic Retry**: System automatically retries failed operations up to 3 times
- **Manual Retry**: You can retry failed uploads by uploading the file again
- **Partial Recovery**: If some batches succeed, only failed batches need to be retried

## Multi-Worksheet Files

### Enhanced Status for Excel Files
When uploading Excel files with multiple worksheets:
- **Worksheet Detection**: Status shows "Found X worksheets" during initial processing
- **Combined Processing**: All worksheets are processed together in batches
- **Worksheet Tracking**: Each lead will include its source worksheet information

### Example Status Flow
```
1. File Uploading...
2. File Uploaded
3. Found 3 worksheets: Sales, Marketing, Partners
4. Leads Processing... (Reading all worksheets)
5. Processing batch 1 of 8 (Mixed data from all worksheets)
6. Processing batch 2 of 8...
   ...
8. Processing Complete! 47 leads processed from 3 worksheets
```

## Duplicate Handling Status

### Duplicate Detection
- **During Processing**: Status may show "Checking for duplicates..."
- **Found Duplicates**: "Found X duplicates, updating existing leads"
- **No Duplicates**: Processing continues normally

### What Happens to Duplicates
- **Email Matching**: System uses email addresses to identify duplicates
- **Data Update**: Newer data overwrites existing lead information
- **Preserved Fields**: Original lead ID and creation date are kept
- **Status Tracking**: Duplicate actions are logged for audit purposes

## Best Practices

### File Preparation
1. **Clean Data**: Remove empty rows and columns before upload
2. **Consistent Headers**: Use clear, consistent column names
3. **File Size**: For files > 1000 leads, expect longer processing times
4. **Format**: Use .xlsx format for best compatibility with multi-worksheet support

### During Processing
1. **Stay Connected**: Keep your browser tab open during processing
2. **Don't Refresh**: Avoid refreshing the page while processing is active
3. **Monitor Progress**: Watch for error messages or unusual delays
4. **Be Patient**: Large files can take several minutes to process

### After Processing
1. **Review Results**: Check the lead table for your new data
2. **Verify Count**: Confirm the number of leads matches your expectations
3. **Check Quality**: Review a few leads to ensure data was standardized correctly
4. **Handle Errors**: Address any leads that couldn't be processed

## Troubleshooting

### Status Not Updating
- **Check Connection**: Ensure stable internet connection
- **Refresh Page**: Try refreshing if status seems stuck
- **Browser Issues**: Clear cache or try a different browser

### Processing Stuck
- **Wait Time**: Allow up to 5 minutes for large files
- **Cancel and Retry**: Use cancel button and try uploading again
- **File Issues**: Check if file is corrupted or too large

### Missing Leads
- **Check Filters**: Ensure lead table filters aren't hiding new data
- **Refresh Table**: Click refresh button on lead table
- **Processing Errors**: Check if any error messages appeared during upload

### Performance Issues
- **File Size**: Consider splitting very large files (>5000 leads)
- **Peak Times**: Processing may be slower during high usage periods
- **Browser Resources**: Close other tabs if browser becomes slow

## Technical Details

### Status Polling
- **Frequency**: Status updates every 2 seconds during processing
- **Authentication**: All status requests are authenticated with your login
- **Timeout**: Status polling stops after 30 minutes of inactivity

### Data Storage
- **Status Records**: Processing status is stored securely and expires after 24 hours
- **Privacy**: Status information is only accessible to you
- **Cleanup**: Old status records are automatically deleted

### Browser Compatibility
- **Modern Browsers**: Works with Chrome, Firefox, Safari, Edge (latest versions)
- **JavaScript Required**: Status indicator requires JavaScript to be enabled
- **Mobile Support**: Fully functional on mobile devices and tablets

## Support

If you encounter issues with the processing status indicator:

1. **Check This Guide**: Review the troubleshooting section above
2. **Browser Console**: Check for error messages in browser developer tools
3. **Contact Support**: Provide details about the file you were uploading and any error messages
4. **Include Information**: File size, format, browser type, and exact error messages help with diagnosis

The processing status indicator is designed to make file uploads transparent and manageable. With real-time feedback and control options, you can confidently upload files of any size and monitor their progress to completion.