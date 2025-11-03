"""
Runtime configuration utilities.
Loads environment variables and configuration files.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from dotenv import load_dotenv


# Load .env file if it exists
load_dotenv()

# Global config cache
_config: Optional[Dict[str, Any]] = None


def load_config(config_path: str = "configs/config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config.yaml file
        
    Returns:
        Configuration dictionary
    """
    global _config
    
    if _config is None:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            _config = yaml.safe_load(f)
    
    return _config


def get_config(key: str = None, default: Any = None) -> Any:
    """
    Get configuration value by key path (supports dot notation).
    
    Args:
        key: Configuration key (e.g., 'llm.provider' or 'ncbi.email')
        default: Default value if key not found
        
    Returns:
        Configuration value or full config dict if key is None
    """
    config = load_config()
    
    if key is None:
        return config
    
    # Support dot notation for nested keys
    keys = key.split('.')
    value = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    # Expand environment variables in string values
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        value = os.getenv(env_var, default)
    
    return value if value is not None else default

