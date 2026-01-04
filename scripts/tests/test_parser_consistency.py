import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from scripts.core.loc_parser import parse_loc_file
from scripts.utils.quote_extractor import QuoteExtractor

def test_consistency():
    # Create a dummy Paradox loc file
    test_file = "test_consistency_loc.yml"
    content = """l_english:
 key_1:0 "Normal text"
 key_2:1 "Text with $VAR$"
 key_var:0 "$PURE_VAR$"
 key_empty:0 ""
 key_self:0 "key_self"
 key_self_v:1 "key_self_v"
 # comment:0 "commented"
    """
    
    with open(test_file, "w", encoding="utf-8-sig") as f:
        f.write(content)
    
    try:
        # 1. Parse using loc_parser
        loc_results = parse_loc_file(Path(test_file))
        loc_texts = [text for key, text in loc_results]
        
        # 2. Parse using QuoteExtractor
        _, qe_texts, _ = QuoteExtractor.extract_from_file(test_file)
        
        print(f"Loc Parser Texts: {loc_texts}")
        print(f"QuoteExtractor Texts: {qe_texts}")
        
        assert loc_texts == qe_texts, f"Mismatch! \nLoc: {loc_texts} \nQE: {qe_texts}"
        print("✅ SUCCESS: Parsers are consistent.")
        
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

if __name__ == "__main__":
    test_consistency()
