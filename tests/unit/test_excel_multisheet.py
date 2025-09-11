"""
Unit tests for Excel multi-worksheet processing in Lead Splitter.
Tests the enhanced Excel file processing that handles multiple worksheets.
"""

import pytest
import pandas as pd
from io import BytesIO
import sys
import os
from unittest.mock import patch, MagicMock

# Mock AWS clients before importing
with patch('boto3.client') as mock_boto3_client:
    mock_boto3_client.return_value = MagicMock()
    
    # Add the lambda function path
    lead_splitter_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'lead-splitter')
    shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'lambda', 'shared')
    sys.path.insert(0, lead_splitter_path)
    sys.path.insert(0, shared_path)

    from lambda_function import FileProcessor
    from error_handling import FileProcessingError


class TestExcelMultiWorksheet:
    """Test Excel multi-worksheet processing functionality."""
    
    def create_test_excel_with_multiple_sheets(self):
        """Create a test Excel file with multiple worksheets."""
        # Create test data for different sheets
        sheet1_data = {
            'Name': ['John Doe', 'Jane Smith'],
            'Email': ['john@example.com', 'jane@example.com'],
            'Phone': ['+1-555-0123', '+1-555-0124'],
            'Company': ['Tech Corp', 'Data Inc']
        }
        
        sheet2_data = {
            'Full Name': ['Bob Johnson', 'Alice Brown'],
            'Email Address': ['bob@company.com', 'alice@startup.com'],
            'Contact Number': ['+1-555-0125', '+1-555-0126'],
            'Organization': ['Big Corp', 'Small LLC']
        }
        
        sheet3_data = {
            'First Name': ['Charlie'],
            'Last Name': ['Wilson'],
            'Work Email': ['charlie@business.com'],
            'Mobile': ['+1-555-0127'],
            'Employer': ['Wilson & Associates']
        }
        
        # Create Excel file with multiple sheets
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(sheet1_data).to_excel(writer, sheet_name='Sales Leads', index=False)
            pd.DataFrame(sheet2_data).to_excel(writer, sheet_name='Marketing Contacts', index=False)
            pd.DataFrame(sheet3_data).to_excel(writer, sheet_name='Referrals', index=False)
        
        return excel_buffer.getvalue()
    
    def create_test_excel_with_empty_sheet(self):
        """Create a test Excel file with one empty worksheet."""
        sheet1_data = {
            'Name': ['John Doe'],
            'Email': ['john@example.com'],
            'Phone': ['+1-555-0123'],
            'Company': ['Tech Corp']
        }
        
        # Create Excel file with one populated sheet and one empty sheet
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(sheet1_data).to_excel(writer, sheet_name='Valid Data', index=False)
            pd.DataFrame().to_excel(writer, sheet_name='Empty Sheet', index=False)
        
        return excel_buffer.getvalue()
    
    def create_test_excel_single_sheet(self):
        """Create a test Excel file with single worksheet for comparison."""
        sheet_data = {
            'Name': ['John Doe', 'Jane Smith'],
            'Email': ['john@example.com', 'jane@example.com'],
            'Phone': ['+1-555-0123', '+1-555-0124'],
            'Company': ['Tech Corp', 'Data Inc']
        }
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(sheet_data).to_excel(writer, sheet_name='Sheet1', index=False)
        
        return excel_buffer.getvalue()
    
    def test_multi_worksheet_processing(self):
        """Test processing Excel file with multiple worksheets."""
        # Create test Excel file
        excel_content = self.create_test_excel_with_multiple_sheets()
        
        # Process the file
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Verify results
        assert len(leads) == 5  # 2 + 2 + 1 leads from three sheets
        
        # Check that worksheet information is preserved
        worksheet_names = set(lead['_worksheet'] for lead in leads)
        expected_sheets = {'Sales Leads', 'Marketing Contacts', 'Referrals'}
        assert worksheet_names == expected_sheets
        
        # Verify data from each sheet
        sales_leads = [lead for lead in leads if lead['_worksheet'] == 'Sales Leads']
        marketing_leads = [lead for lead in leads if lead['_worksheet'] == 'Marketing Contacts']
        referral_leads = [lead for lead in leads if lead['_worksheet'] == 'Referrals']
        
        assert len(sales_leads) == 2
        assert len(marketing_leads) == 2
        assert len(referral_leads) == 1
        
        # Verify specific data
        assert sales_leads[0]['Name'] == 'John Doe'
        assert sales_leads[0]['Email'] == 'john@example.com'
        assert marketing_leads[0]['Full Name'] == 'Bob Johnson'
        assert referral_leads[0]['First Name'] == 'Charlie'
    
    def test_excel_with_empty_worksheet(self):
        """Test processing Excel file with empty worksheets."""
        # Create test Excel file with empty sheet
        excel_content = self.create_test_excel_with_empty_sheet()
        
        # Process the file
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Verify results - should only get data from non-empty sheet
        assert len(leads) == 1
        assert leads[0]['_worksheet'] == 'Valid Data'
        assert leads[0]['Name'] == 'John Doe'
    
    def test_single_worksheet_compatibility(self):
        """Test that single worksheet files still work correctly."""
        # Create test Excel file with single sheet
        excel_content = self.create_test_excel_single_sheet()
        
        # Process the file
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Verify results
        assert len(leads) == 2
        assert all(lead['_worksheet'] == 'Sheet1' for lead in leads)
        assert leads[0]['Name'] == 'John Doe'
        assert leads[1]['Name'] == 'Jane Smith'
    
    def test_all_empty_worksheets(self):
        """Test handling of Excel file with all empty worksheets."""
        # Create Excel file with only empty sheets
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame().to_excel(writer, sheet_name='Empty1', index=False)
            pd.DataFrame().to_excel(writer, sheet_name='Empty2', index=False)
        
        excel_content = excel_buffer.getvalue()
        
        # Should raise FileProcessingError
        with pytest.raises(FileProcessingError, match="Excel file contains no processable data"):
            FileProcessor.read_excel_file(excel_content)
    
    def test_worksheet_with_invalid_data(self):
        """Test handling of worksheets with problematic data."""
        # Create Excel file where one sheet has issues
        sheet1_data = {
            'Name': ['John Doe'],
            'Email': ['john@example.com'],
            'Phone': ['+1-555-0123'],
            'Company': ['Tech Corp']
        }
        
        # Create a sheet with problematic data (all NaN)
        sheet2_data = pd.DataFrame({
            'Col1': [None, None],
            'Col2': [None, None]
        })
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(sheet1_data).to_excel(writer, sheet_name='Good Data', index=False)
            sheet2_data.to_excel(writer, sheet_name='Bad Data', index=False)
        
        excel_content = excel_buffer.getvalue()
        
        # Process the file - should get data from good sheet only
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Should only get the valid lead
        assert len(leads) == 1
        assert leads[0]['_worksheet'] == 'Good Data'
        assert leads[0]['Name'] == 'John Doe'
    
    def test_worksheet_field_mapping(self):
        """Test that different field names across worksheets are preserved."""
        # Create sheets with different field naming conventions
        sheet1_data = {
            'Name': ['John Doe'],
            'Email': ['john@example.com']
        }
        
        sheet2_data = {
            'Full Name': ['Jane Smith'],
            'Email Address': ['jane@example.com']
        }
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            pd.DataFrame(sheet1_data).to_excel(writer, sheet_name='Format1', index=False)
            pd.DataFrame(sheet2_data).to_excel(writer, sheet_name='Format2', index=False)
        
        excel_content = excel_buffer.getvalue()
        
        # Process the file
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Verify that different field names are preserved
        assert len(leads) == 2
        
        format1_lead = next(lead for lead in leads if lead['_worksheet'] == 'Format1')
        format2_lead = next(lead for lead in leads if lead['_worksheet'] == 'Format2')
        
        assert 'Name' in format1_lead
        assert 'Email' in format1_lead
        assert 'Full Name' in format2_lead
        assert 'Email Address' in format2_lead
    
    def test_large_multi_worksheet_file(self):
        """Test processing of Excel file with many worksheets and records."""
        excel_buffer = BytesIO()
        
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            # Create 5 sheets with 10 records each
            for sheet_num in range(1, 6):
                sheet_data = {
                    'Name': [f'Person {i}' for i in range(1, 11)],
                    'Email': [f'person{i}@sheet{sheet_num}.com' for i in range(1, 11)],
                    'Phone': [f'+1-555-{sheet_num:02d}{i:02d}' for i in range(1, 11)],
                    'Company': [f'Company {sheet_num}-{i}' for i in range(1, 11)]
                }
                
                pd.DataFrame(sheet_data).to_excel(
                    writer, 
                    sheet_name=f'Sheet{sheet_num}', 
                    index=False
                )
        
        excel_content = excel_buffer.getvalue()
        
        # Process the file
        leads = FileProcessor.read_excel_file(excel_content)
        
        # Verify results
        assert len(leads) == 50  # 5 sheets × 10 records
        
        # Check worksheet distribution
        worksheet_counts = {}
        for lead in leads:
            worksheet = lead['_worksheet']
            worksheet_counts[worksheet] = worksheet_counts.get(worksheet, 0) + 1
        
        assert len(worksheet_counts) == 5
        assert all(count == 10 for count in worksheet_counts.values())
        
        # Verify data integrity
        sheet1_leads = [lead for lead in leads if lead['_worksheet'] == 'Sheet1']
        assert sheet1_leads[0]['Name'] == 'Person 1'
        assert sheet1_leads[0]['Email'] == 'person1@sheet1.com'
        assert sheet1_leads[9]['Name'] == 'Person 10'