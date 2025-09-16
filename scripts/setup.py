#!/usr/bin/env python3
"""
Setup script for AI Chat Discord System.
Initializes configuration, generates encryption keys, and validates environment.
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared_lib.encryption import generate_encryption_key
from shared_lib.config import create_sample_env_file, ConfigurationError


def generate_keys():
    """Generate encryption keys for the system."""
    print("Generating encryption keys...")
    
    encryption_key = generate_encryption_key()
    jwt_secret = generate_encryption_key()  # Use same function for JWT secret
    
    print(f"Encryption Key: {encryption_key}")
    print(f"JWT Secret: {jwt_secret}")
    print("\nAdd these to your .env file:")
    print(f"SECURITY__ENCRYPTION_KEY={encryption_key}")
    print(f"SECURITY__JWT_SECRET={jwt_secret}")


def create_env_file():
    """Create sample .env file."""
    env_path = project_root / ".env"
    example_path = project_root / ".env.example"
    
    if env_path.exists():
        response = input(f"{env_path} already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Skipping .env file creation.")
            return
    
    create_sample_env_file(str(env_path))
    print(f"Created {env_path}")
    print("Please edit the .env file with your actual configuration values.")


def validate_config():
    """Validate current configuration."""
    try:
        from shared_lib.config import load_config
        config = load_config()
        print("✓ Configuration is valid")
        
        # Check for missing required vars
        missing_vars = config.validate_required_env_vars()
        if missing_vars:
            print("⚠ Missing required environment variables:")
            for var in missing_vars:
                print(f"  - {var}")
        else:
            print("✓ All required environment variables are set")
            
    except ConfigurationError as e:
        print(f"✗ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False
    
    return True


def setup_directories():
    """Create necessary directories."""
    directories = [
        "logs",
        "data",
        "backups",
        "client_bot/logs",
        "server/logs"
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {dir_path}")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup AI Chat Discord System")
    parser.add_argument("--keys", action="store_true", help="Generate encryption keys")
    parser.add_argument("--env", action="store_true", help="Create .env file")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--dirs", action="store_true", help="Create directories")
    parser.add_argument("--all", action="store_true", help="Run all setup steps")
    
    args = parser.parse_args()
    
    if args.all or not any([args.keys, args.env, args.validate, args.dirs]):
        print("Setting up AI Chat Discord System...")
        setup_directories()
        create_env_file()
        generate_keys()
        print("\nSetup complete! Next steps:")
        print("1. Edit .env file with your configuration")
        print("2. Run 'python scripts/setup.py --validate' to check configuration")
        print("3. Set up your database and Discord bot")
    else:
        if args.dirs:
            setup_directories()
        if args.env:
            create_env_file()
        if args.keys:
            generate_keys()
        if args.validate:
            validate_config()


if __name__ == "__main__":
    main()