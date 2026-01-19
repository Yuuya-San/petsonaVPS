"""
Quick setup script for Merchant Application System
Run this after installing dependencies to prepare the database
"""

import os
import sys
from pathlib import Path

def create_upload_directory():
    """Create merchant upload directory"""
    upload_dir = Path('app/static/uploads/merchants')
    upload_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Created upload directory: {upload_dir}")

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'flask_wtf',
        'wtforms',
        'email_validator',
        'requests',
        'flask_sqlalchemy',
        'flask_migrate',
        'werkzeug'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} is installed")
        except ImportError:
            missing.append(package)
            print(f"✗ {package} is NOT installed")
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False
    return True

def verify_files():
    """Verify all required files exist"""
    required_files = [
        'app/models/merchant.py',
        'app/merchant/forms.py',
        'app/merchant/routes.py',
        'app/templates/merchant/apply.html',
        'app/templates/admin/merchant_applications.html',
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - MISSING")
            all_exist = False
    
    return all_exist

def main():
    print("=" * 60)
    print("Merchant Application System - Setup Script")
    print("=" * 60)
    print()
    
    print("1. Checking dependencies...")
    print("-" * 60)
    if not check_dependencies():
        print("\n❌ Please install missing dependencies first")
        return False
    print()
    
    print("2. Verifying files...")
    print("-" * 60)
    if not verify_files():
        print("\n❌ Some files are missing. Please check your setup.")
        return False
    print()
    
    print("3. Creating upload directory...")
    print("-" * 60)
    create_upload_directory()
    print()
    
    print("=" * 60)
    print("✅ Setup verification complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Run database migrations:")
    print("   flask db migrate -m 'Add Merchant model'")
    print("   flask db upgrade")
    print()
    print("2. Start your Flask application:")
    print("   flask run")
    print()
    print("3. Test the form at:")
    print("   http://localhost:5000/merchant/apply")
    print()
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
