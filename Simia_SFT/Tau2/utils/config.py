#!/usr/bin/env python3
"""
Configuration Management Module
Handle configuration file loading, validation and processing
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime


class ConfigManager:
    """Configuration Manager"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = config_path
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ Successfully loaded configuration file: {self.config_path}")
                return config
        except FileNotFoundError:
            print(f"❌ Configuration file does not exist: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            print(f"❌ Configuration file format error: {e}")
            raise
    
    def get_azure_config(self) -> Dict[str, Any]:
        """Get Azure configuration"""
        return {
            'azure_endpoint': self.config.get('azure_endpoint', ''),
            'api_version': self.config.get('api_version', '2024-08-01-preview'),
            'deployment': self.config.get('deployment', 'gpt-4o'),
            'timeout': self.config.get('timeout', 30)
        }
    
    def get_generation_settings(self) -> Dict[str, Any]:
        """Get generation settings"""
        gen_settings = self.config.get('generation_settings', {})
        return {
            'max_conversations': gen_settings.get('max_conversations', 10),
            'temperature': gen_settings.get('temperature', 1),
            'max_tokens': gen_settings.get('max_tokens', 1000),
            'retry_attempts': gen_settings.get('retry_attempts', 3),
            'parallel_workers': gen_settings.get('parallel_workers', 8),
            'batch_size': gen_settings.get('batch_size', 20),
            'rate_limit_delay': gen_settings.get('rate_limit_delay', 0.1),
            'save_progress': gen_settings.get('save_progress', True)
        }
    
    def get_output_settings(self) -> Dict[str, Any]:
        """Get output settings"""
        output_settings = self.config.get('output_settings', {})
        

        output_file = output_settings.get('output_file', 'generated_conversations.json')
        if '{timestamp}' in output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = output_file.replace('{timestamp}', timestamp)
        
        return {
            'output_dir': output_settings.get('output_dir', '.'),
            'output_file': output_file,
            'save_intermediate': output_settings.get('save_intermediate', True),
            'backup_existing': output_settings.get('backup_existing', True)
        }
    
    def get_gpt_log_settings(self) -> Dict[str, Any]:
        log_settings = self.config.get('gpt_log_settings', {})
        

        log_file = log_settings.get('log_file', 'gpt_outputs.jsonl')
        if '{timestamp}' in log_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = log_file.replace('{timestamp}', timestamp)
        
        return {
            'enable_logging': log_settings.get('enable_logging', True),
            'log_file': log_file
        }
    
    def get_sample_data_path(self) -> str:
        return self.config.get('sample_data_path', "")
    
    def get_app_configs(self) -> Dict[str, Any]:
        return self.config.get('app_configs', {})
    
    def get_config_hash(self) -> str:
        """Get configuration hash value, used to detect configuration changes"""
        import hashlib
        key_config = {
            'temperature': self.get_generation_settings()['temperature'],
            'max_tokens': self.get_generation_settings()['max_tokens'],
            'model': self.get_azure_config()['deployment'],
            'sample_data_path': self.get_sample_data_path()
        }
        config_str = json.dumps(key_config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]
    
    def validate_config(self) -> bool:
        """Validate configuration integrity"""
        try:
            azure_config = self.get_azure_config()
            if not azure_config.get('azure_endpoint'):
                print("⚠️  Configuration missing azure_endpoint")
                return False
            
            gen_settings = self.get_generation_settings()
            if gen_settings.get('max_conversations', 0) <= 0:
                print("⚠️  Configuration max_conversations must be greater than 0")
                return False
            
            sample_data_path = self.get_sample_data_path()
            if not sample_data_path or not os.path.exists(sample_data_path):
                print(f"⚠️  Sample DataFile does not exist: {sample_data_path}")
                return False
            
            print("✅ Configuration validation passed")
            return True
            
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
            return False
    
    def get_full_output_path(self) -> str:
        """Get full output file path"""
        output_settings = self.get_output_settings()
        output_dir = output_settings['output_dir']
        output_file = output_settings['output_file']
        
        os.makedirs(output_dir, exist_ok=True)
        
        return os.path.join(output_dir, output_file)
    
    def get_full_gpt_log_path(self) -> str:
        """Get full GPT log file path"""
        output_settings = self.get_output_settings()
        log_settings = self.get_gpt_log_settings()
        
        output_dir = output_settings['output_dir']
        log_file = log_settings['log_file']
        
        os.makedirs(output_dir, exist_ok=True)
        
        return os.path.join(output_dir, log_file)


def load_config(config_path: str = 'config.json') -> ConfigManager:
    """Convenience function to load configuration"""
    return ConfigManager(config_path) 