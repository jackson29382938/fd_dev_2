"""
Tests for address utilities module.
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftid_gen.address_utils import generate_full_name, lookup_zipcode_info, generate_fake_address


class TestGenerateFullName:
    """Tests for generate_full_name function."""
    
    def test_returns_string(self):
        """Should return a string."""
        result = generate_full_name()
        assert isinstance(result, str)
    
    def test_has_first_and_last_name(self):
        """Should return a name with first and last name."""
        result = generate_full_name()
        parts = result.split()
        assert len(parts) == 2
    
    def test_names_are_capitalized(self):
        """Names should be capitalized."""
        result = generate_full_name()
        first, last = result.split()
        assert first[0].isupper()
        assert last[0].isupper()


class TestLookupZipcodeInfo:
    """Tests for lookup_zipcode_info function."""
    
    @patch('ftid_gen.address_utils.requests.get')
    def test_valid_zipcode_returns_dict(self, mock_get):
        """Should return dict with city and state for valid zip."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'places': [{'place name': 'New York', 'state abbreviation': 'NY'}]
        }
        mock_get.return_value = mock_response
        
        result = lookup_zipcode_info('10001')
        
        assert result is not None
        assert 'city' in result
        assert 'state' in result
        assert result['city'] == 'New York'
        assert result['state'] == 'NY'
    
    @patch('ftid_gen.address_utils.requests.get')
    def test_invalid_zipcode_returns_none(self, mock_get):
        """Should return None for invalid zip."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = lookup_zipcode_info('00000')
        
        assert result is None


class TestGenerateFakeAddress:
    """Tests for generate_fake_address function."""
    
    @patch('ftid_gen.address_utils.get_zipcode_info_from_file_or_api')
    def test_returns_dict_with_required_fields(self, mock_lookup):
        """Should return dict with all required address fields."""
        mock_lookup.return_value = {'city': 'Test City', 'state': 'TC'}
        
        result = generate_fake_address('12345')
        
        assert isinstance(result, dict)
        assert 'name' in result
        assert 'address' in result
        assert 'city' in result
        assert 'state' in result
        assert 'zip_code' in result
    
    @patch('ftid_gen.address_utils.get_zipcode_info_from_file_or_api')
    def test_address_has_valid_format(self, mock_lookup):
        """Address should have number and street."""
        mock_lookup.return_value = {'city': 'Test City', 'state': 'TC'}
        
        result = generate_fake_address('12345')
        
        # Address should match pattern: number streetname streettype
        parts = result['address'].split()
        assert len(parts) >= 3
        assert parts[0].isdigit()  # Street number should be numeric


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
