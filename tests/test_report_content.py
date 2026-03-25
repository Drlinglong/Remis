import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scripts.core.proofreading_tracker import ProofreadingTracker

def test_csv_report_content():
    print("Testing ProofreadingTracker CSV content with validation data...")
    
    tracker = ProofreadingTracker("TestMod", "test_output")
    
    file_info = {
        'source_path': 'l_english/test.yml',
        'dest_path': 'l_russian/test.yml',
        'translated_lines': 10,
        'proofreading_progress': 'Errors: 5, Warnings: 2',
        'proofreading_notes': 'L10 | ERROR | Banned char\nL11 | WARNING | Missing space'
    }
    
    tracker.add_file_info(file_info)
    
    csv_content = tracker.generate_csv_content()
    print("\nGenerated CSV Content:")
    print(csv_content)
    
    assert "Errors: 5, Warnings: 2" in csv_content
    assert "Banned char" in csv_content
    assert "Missing space" in csv_content
    
    print("Test PASSED!")

if __name__ == "__main__":
    test_csv_report_content()
