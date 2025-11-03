#!/usr/bin/env python3
"""
ShareGPT Conversation Generator Toolkit
"""

from .config import ConfigManager, load_config
from .gpt_logger import GPTLogger, create_gpt_logger
from .data_loader import DataLoader, create_data_loader
from .conversation_generator import ConversationGenerator, create_conversation_generator
from .progress_manager import ProgressManager, create_progress_manager
from .file_operations import FileOperations, create_file_operations
from .parallel_processor import ParallelProcessor, create_parallel_processor
from .main_generator import ShareGPTGenerator, create_share_gpt_generator

__version__ = "1.0.0"
__author__ = "ShareGPT Generator Team"
__description__ = "Generate new multi-turn conversation data based on existing data samples"


__all__ = [

    'ShareGPTGenerator',
    'ConfigManager',
    'GPTLogger',
    'DataLoader',
    'ConversationGenerator',
    'ProgressManager',
    'FileOperations',
    'ParallelProcessor',
    

    'create_share_gpt_generator',
    'load_config',
    'create_gpt_logger',
    'create_data_loader',
    'create_conversation_generator',
    'create_progress_manager',
    'create_file_operations',
    'create_parallel_processor',
]


def get_version():
    """Get version information"""
    return __version__

def get_info():
    """Get package information"""
    return {
        'name': 'ShareGPT Generator Utils',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'modules': [
            'config - Configuration management',
            'gpt_logger - GPT logging',
            'data_loader - Data loading',
            'conversation_generator - Conversation generation',
            'progress_manager - Progress management',
            'file_operations - File operations',
            'parallel_processor - Parallel processing',
            'main_generator - Main generator'
        ]
    }

def show_info():
    """Display package information"""
    info = get_info()
    print(f"📦 {info['name']} v{info['version']}")
    print(f"👤 Author: {info['author']}")
    print(f"📝 Description: {info['description']}")
    print(f"🔧 Modules:")
    for module in info['modules']:
        print(f"   - {module}") 