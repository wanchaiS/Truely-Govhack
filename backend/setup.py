#!/usr/bin/env python3
"""
Setup script for fact-checking database system
Helps with environment setup, testing, and initial configuration
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    else:
        print(f"✅ Python version: {sys.version.split()[0]}")
        return True

def create_virtual_environment():
    """Create virtual environment if it doesn't exist"""
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    try:
        print("🔨 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False

def install_requirements():
    """Install required packages"""
    try:
        print("📦 Installing requirements...")
        
        # Determine pip path based on OS
        if os.name == 'nt':  # Windows
            pip_path = "venv/Scripts/pip"
        else:  # Unix/Linux/Mac
            pip_path = "venv/bin/pip"
        
        subprocess.run([pip_path, "install", "-r", "requirements.txt"], check=True)
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False
    except FileNotFoundError:
        print("❌ Virtual environment not found. Please create it first.")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["documents", "data", "logs"]
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {dir_name}")
        else:
            print(f"✅ Directory exists: {dir_name}")

def test_installation():
    """Test if installation is working"""
    try:
        print("🧪 Testing installation...")
        
        # Determine python path
        if os.name == 'nt':  # Windows
            python_path = "venv/Scripts/python"
        else:  # Unix/Linux/Mac
            python_path = "venv/bin/python"
        
        # Test database setup
        subprocess.run([python_path, "src/database.py"], 
                      check=True, cwd=".", capture_output=True)
        print("✅ Database test passed")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation test failed: {e}")
        return False

def show_usage_instructions():
    """Show usage instructions"""
    print("\n" + "="*60)
    print("🎉 Setup completed successfully!")
    print("="*60)
    
    if os.name == 'nt':  # Windows
        activate_cmd = "venv\\Scripts\\activate"
        python_cmd = "venv\\Scripts\\python"
    else:  # Unix/Linux/Mac
        activate_cmd = "source venv/bin/activate"
        python_cmd = "venv/bin/python"
    
    print("\n📋 Next steps:")
    print(f"1. Activate virtual environment: {activate_cmd}")
    print("2. Add your documents to the 'documents' folder")
    print("3. Process documents:")
    print(f"   {python_cmd} src/document_processor.py --input_dir documents")
    print("4. Test the database:")
    print(f"   {python_cmd} src/database.py")
    
    print("\n🔧 Available commands:")
    print(f"• Process documents: {python_cmd} src/document_processor.py --input_dir <folder>")
    print(f"• Clear database: {python_cmd} src/document_processor.py --clear_db")
    print(f"• Test database: {python_cmd} src/database.py")
    
    print("\n📁 Project structure:")
    print("├── documents/     # Put your source documents here")
    print("├── data/          # ChromaDB data will be stored here")
    print("├── src/           # Source code")
    print("├── venv/          # Virtual environment")
    print("└── requirements.txt")

def main():
    """Main setup function"""
    print("🚀 Setting up Fact-Checking Database System")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        return False
    
    # Create virtual environment
    if not create_virtual_environment():
        return False
    
    # Install requirements
    if not install_requirements():
        return False
    
    # Create directories
    create_directories()
    
    # Test installation
    if not test_installation():
        print("⚠️ Installation test failed, but basic setup is complete")
    
    # Show usage instructions
    show_usage_instructions()
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)