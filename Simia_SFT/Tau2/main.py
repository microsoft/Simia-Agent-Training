#!/usr/bin/env python3

"""
Conversation generator
Generate multi-turn Agent conversations based on AgentTuning data samples
"""

import argparse
import sys
import os
import subprocess
from pathlib import Path

from utils.main_generator import create_share_gpt_generator


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Agent trajectory conversation generator')
    parser.add_argument('--config', default='config.json', help='Config file path')
    parser.add_argument('--auto-resume', action='store_true', help='Auto resume from checkpoint')
    parser.add_argument('--force-new', action='store_true', help='Force start new generation')
    parser.add_argument('--status', action='store_true', help='Show progress status')
    parser.add_argument('--clean', action='store_true', help='Clean progress files')
    parser.add_argument('--list', action='store_true', help='List all progress files')
    parser.add_argument('--force-complete', action='store_true', help='Force complete with existing progress')
    parser.add_argument('--merge', nargs='+', help='Merge multiple progress files')
    parser.add_argument('--gpt-stats', action='store_true', help='Show GPT call statistics')
    parser.add_argument('--export-gpt-log', action='store_true', help='Export GPT log summary')
    parser.add_argument('--sample-stats', action='store_true', help='Show sample data statistics')
    parser.add_argument('--system-info', action='store_true', help='Show system information')
    parser.add_argument('--interactive', action='store_true', help='Enter interactive mode')
    parser.add_argument('--validate-samples', action='store_true', help='Validate sample data')
    parser.add_argument('--backup', action='store_true', help='Backup important files')
    
    args = parser.parse_args()
    
    # Create generator
    try:
        generator = create_share_gpt_generator(args.config)
    except Exception as e:
        print(f"Initialization failed: {e}")
        sys.exit(1)
    
    # Handle command-line options
    if args.system_info:
        generator.show_system_info()
        return
    
    if args.status:
        generator.show_progress_status()
        return
    
    if args.clean:
        generator.clean_progress_files()
        return
    
    if args.list:
        generator.show_all_progress_files()
        return
    
    if args.force_complete:
        conversations = generator.force_complete_from_progress()
        if conversations:
            generator.save_conversations(conversations)
            print(f"Saved {len(conversations)} conversations")
        return
    
    if args.merge:
        conversations = generator.merge_progress_files(args.merge)
        if conversations:
            generator.save_conversations(conversations)
            print(f"Merged and saved {len(conversations)} conversations")
        return
    
    if args.gpt_stats:
        generator.show_gpt_log_stats()
        return
    
    if args.export_gpt_log:
        generator.export_gpt_log_summary()
        return
    
    if args.sample_stats:
        generator.show_sample_statistics()
        return
    
    if args.validate_samples:
        if generator.validate_sample_data():
            print("Sample data validation passed")
        else:
            print("Sample data validation failed")
        return
    
    if args.backup:
        generator.backup_files()
        return
    
    if args.interactive:
        conversations = generator.run_interactive_mode()
        if conversations:
            generator.show_processing_summary(conversations)
        return
    
    # Main generation logic
    print("Agent conversation generator started")
    print(f"Output file: {generator.full_output_path}")
    print(f"Target count: {generator.max_conversations}")
    
    conversations = []
    
    if args.auto_resume:
        conversations = generator.auto_resume_or_start()
    elif args.force_new:
        print("Force starting new generation...")
        conversations = generator.generate_conversations()
    else:
        # Interactive mode
        if generator.has_progress():
            print("\nProgress file detected. Choose an option:")
            print("1. Resume from checkpoint")
            print("2. Start new generation")
            print("3. Show progress status")
            print("4. Clean progress files")
            print("5. Enter interactive mode")
            
            while True:
                choice = input("Select mode (1/2/3/4/5): ").strip()
                if choice == '1':
                    print("Resuming from checkpoint...")
                    conversations = generator.resume_generation()
                    break
                elif choice == '2':
                    print("Starting new generation...")
                    conversations = generator.generate_conversations()
                    break
                elif choice == '3':
                    generator.show_progress_status()
                    continue
                elif choice == '4':
                    generator.clean_progress_files()
                    return
                elif choice == '5':
                    conversations = generator.run_interactive_mode()
                    break
                else:
                    print("Invalid choice, please try again")
        else:
            print("Starting new generation...")
            conversations = generator.generate_conversations()
    
    # Save results
    if conversations:
        generator.save_conversations(conversations)
        generator.show_processing_summary(conversations)
        
        print(f"\nTask completed! Generated {len(conversations)} Agent conversations")
        
        # Show completion statistics
        completion_rate = generator.get_completion_rate()
        print(f"Completion rate: {completion_rate:.1%}")
        
        if completion_rate >= 1.0:
            print("All target conversations generated!")
        else:
            remaining = generator.get_remaining_count()
            print(f"Remaining: {remaining} conversations")
        
        # Post-processing
        print("\nStarting post-processing...")
        try:
            processed_file = generator.full_output_path.replace('.json', '_processed.json')
            print(f"Post-processing completed")
            print(f"Original file: {generator.full_output_path}")
            
        except Exception as e:
            print(f"Post-processing error: {e}")
            import traceback
            traceback.print_exc()
            
    else:
        print("No conversations generated")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nProgram error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 