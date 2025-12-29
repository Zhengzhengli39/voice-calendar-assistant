"""
Authentication manager for handling Google login state
"""

import json
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, storage_dir="storage"):
        """
        Initialize authentication manager
        
        Args:
            storage_dir: Directory to store authentication state
        """
        self.storage_dir = Path(storage_dir)
        self.auth_state_file = self.storage_dir / "auth_state.json"
        
        # Create storage directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def get_auth_state_path(self):
        """Get path to authentication state file"""
        return str(self.auth_state_file)
    
    def auth_state_exists(self):
        """Check if authentication state exists"""
        return self.auth_state_file.exists()
    
    def save_auth_state(self, state_data):
        """
        Save authentication state
        
        Args:
            state_data: Authentication state data
        """
        try:
            with open(self.auth_state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            logger.info(f"Authentication state saved to {self.auth_state_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving auth state: {str(e)}")
            return False
    
    def load_auth_state(self):
        """Load authentication state"""
        try:
            if not self.auth_state_exists():
                return None
            
            with open(self.auth_state_file, 'r') as f:
                state_data = json.load(f)
            
            logger.info(f"Authentication state loaded from {self.auth_state_file}")
            return state_data
            
        except Exception as e:
            logger.error(f"Error loading auth state: {str(e)}")
            return None
    
    def clear_auth_state(self):
        """Clear authentication state"""
        try:
            if self.auth_state_exists():
                self.auth_state_file.unlink()
                logger.info("Authentication state cleared")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error clearing auth state: {str(e)}")
            return False
    
    def get_auth_status(self):
        """Get authentication status"""
        if self.auth_state_exists():
            state_data = self.load_auth_state()
            if state_data:
                return {
                    'authenticated': True,
                    'last_updated': os.path.getmtime(self.auth_state_file),
                    'file_path': str(self.auth_state_file)
                }
        
        return {
            'authenticated': False,
            'message': 'Authentication required'
        }