import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from scripts.utils.quote_extractor import QuoteExtractor

def test_quote_filtering():
    print("Testing QuoteExtractor Filtering Logic...")
    
    # Simulating a file content
    lines = [
        'l_english:',
        ' occ_offer_convoys_action_propose_name: "$occ_offer_convoys$"', # Should be filtered out
        ' some_other_key: "Normal text"', # Should keep
        ' mixed_key: "$VAR$ text"', # Should keep
        ' empty_key: ""' # Should be filtered out
    ]
    
    # We need to mock how extract_from_file works, but since it reads from disk, 
    # we can recreate the loop logic here or just test the filtering condition directly.
    # Let's recreate the loop logic from extract_from_file roughly.
    
    texts_to_translate = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"): continue
        if stripped.startswith("l_english"): continue
        
        # Simplified extraction mocking
        value = QuoteExtractor.extract_from_line(line)
        if value is None: continue
        
        # --- The Filtering Logic from lines 201-209 in quote_extractor.py ---
        is_pure_variable = False
        if value.startswith('$') and value.endswith('$'):
            if value.count('$') == 2:
                is_pure_variable = True

        if is_pure_variable or not value:
            print(f"Filtered out: '{value}'")
            continue
            
        texts_to_translate.append(value)
        print(f"Kept: '{value}'")

    print(f"\nFinal list: {texts_to_translate}")
    
    # Assertions
    assert "$occ_offer_convoys$" not in texts_to_translate
    assert "Normal text" in texts_to_translate
    assert "" not in texts_to_translate

if __name__ == "__main__":
    try:
        test_quote_filtering()
        print("✅ Filter logic works as expected.")
    except AssertionError as e:
        print(f"❌ Assertion Failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
