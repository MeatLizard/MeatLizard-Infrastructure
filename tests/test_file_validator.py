import pytest
from unittest.mock import MagicMock, patch
from server.web.app.services.file_validator import FileValidator
import pyclamd

@pytest.fixture
def mock_magic():
    with patch('magic.from_file') as mock:
        yield mock

@pytest.fixture
def mock_clamd_socket():
    with patch('pyclamd.ClamdUnixSocket') as mock_unix_socket, \
         patch('pyclamd.ClamdNetworkSocket') as mock_network_socket:
        yield mock_unix_socket, mock_network_socket

def test_file_validator_init_success(mock_clamd_socket):
    mock_unix_socket, mock_network_socket = mock_clamd_socket
    mock_unix_socket.return_value.ping.return_value = None
    mock_network_socket.return_value.ping.return_value = None
    validator = FileValidator(allowed_content_types=[], clamd_socket="/tmp/clamd.sock")
    assert validator.clamd is not None

def test_file_validator_init_connection_error():
    with patch('pyclamd.ClamdUnixSocket', side_effect=pyclamd.ConnectionError), \
         patch('pyclamd.ClamdNetworkSocket', side_effect=pyclamd.ConnectionError):
        with pytest.raises(RuntimeError):
            FileValidator(allowed_content_types=[], clamd_socket="/tmp/clamd.sock")

def test_validate_file_type_allowed(mock_magic, mock_clamd_socket):
    mock_magic.return_value = "image/jpeg"
    validator = FileValidator(allowed_content_types=["image/jpeg"], clamd_socket="/tmp/clamd.sock")
    assert validator.validate_file_type("dummy_path") is True

def test_validate_file_type_disallowed(mock_magic, mock_clamd_socket):
    mock_magic.return_value = "application/zip"
    validator = FileValidator(allowed_content_types=["image/jpeg"], clamd_socket="/tmp/clamd.sock")
    assert validator.validate_file_type("dummy_path") is False

def test_scan_for_malware_clean(mock_clamd_socket):
    mock_unix_socket, _ = mock_clamd_socket
    mock_unix_socket.return_value.scan_file.return_value = None
    validator = FileValidator(allowed_content_types=[], clamd_socket="/tmp/clamd.sock")
    assert validator.scan_for_malware("dummy_path") is True

def test_scan_for_malware_infected(mock_clamd_socket):
    mock_unix_socket, _ = mock_clamd_socket
    mock_unix_socket.return_value.scan_file.return_value = {'dummy_path': ('FOUND', 'Eicar-Test-Signature')}
    validator = FileValidator(allowed_content_types=[], clamd_socket="/tmp/clamd.sock")
    assert validator.scan_for_malware("dummy_path") is False
