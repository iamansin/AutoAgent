import os
import logging
from typing import Optional, Any
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv
load_dotenv()


class SecureStore:
    """
    A secure credential store with encryption capabilities.
    
    This implementation supports both environment variables and encrypted local storage,
    with fallback mechanisms and proper error handling.
    """
    _instance = None
    _logger = logging.getLogger(__name__)
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SecureStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._encryption_key = os.getenv("SECURE_STORE_KEY")
        self._storage_path = os.getenv("SECURE_STORE_PATH", "./.secure_storage")
        self._cached_credentials = {}
        
        # Initialize encryption if key is available
        self._fernet = None
        if self._encryption_key:
            try:
                # Generate key from password
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'static_salt_for_demo',  # In production, use a proper salt strategy
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(self._encryption_key.encode()))
                self._fernet = Fernet(key)
            except Exception as e:
                self._logger.error(f"Failed to initialize encryption: {str(e)}")
        
        # Load cached credentials if available
        self._load_cached_credentials()
    
    def _load_cached_credentials(self) -> None:
        """Load credentials from encrypted storage if available."""
        if not os.path.exists(self._storage_path):
            return
            
        try:
            with open(self._storage_path, 'rb') as f:
                encrypted_data = f.read()
                
            if self._fernet:
                decrypted_data = self._fernet.decrypt(encrypted_data).decode('utf-8')
                self._cached_credentials = json.loads(decrypted_data)
                self._logger.info(f"Loaded {len(self._cached_credentials)} credentials from secure storage")
        except Exception as e:
            self._logger.error(f"Failed to load cached credentials: {str(e)}")
    
    def _save_cached_credentials(self) -> None:
        """Save credentials to encrypted storage."""
        if not self._fernet:
            self._logger.warning("Encryption key not available, skipping credential caching")
            return
            
        try:
            encrypted_data = self._fernet.encrypt(json.dumps(self._cached_credentials).encode('utf-8'))
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            
            with open(self._storage_path, 'wb') as f:
                f.write(encrypted_data)
                
            self._logger.info(f"Saved {len(self._cached_credentials)} credentials to secure storage")
        except Exception as e:
            self._logger.error(f"Failed to save cached credentials: {str(e)}")
    
    @classmethod
    def get_credential(cls, key: str, default: Optional[Any] = None) -> str:
        """
        Retrieve a credential securely.
        
        Args:
            key (str): The key identifying the credential.
            default (Optional[Any]): Default value if credential not found.
            
        Returns:
            str: The credential value.
            
        Raises:
            ValueError: If credential not found and no default provided.
        """
        instance = cls()
        
        # Try to get from cache first
        if key in instance._cached_credentials:
            return instance._cached_credentials[key]
        
        # Then try environment variables
        value = os.getenv(key)
        if value is not None:
            # Cache the value if encryption is available
            if instance._fernet:
                instance._cached_credentials[key] = value
                instance._save_cached_credentials()
            return value
        
        # Return default or raise error
        if default is not None:
            return default
            
        raise ValueError(f"Credential '{key}' not found in environment variables or secure storage.")
    
    @classmethod
    def store_credential(cls, key: str, value: str) -> bool:
        """
        Store a credential securely.
        
        Args:
            key (str): The key identifying the credential.
            value (str): The credential value to store.
            
        Returns:
            bool: True if stored successfully, False otherwise.
        """
        instance = cls()
        
        if not instance._fernet:
            instance._logger.warning(f"Encryption not available, credential '{key}' not stored")
            return False
        
        try:
            instance._cached_credentials[key] = value
            instance._save_cached_credentials()
            return True
        except Exception as e:
            instance._logger.error(f"Failed to store credential '{key}': {str(e)}")
            return False