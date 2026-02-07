
import sys
import os

def check_file_size(filepath):
    """
    Check file size in characters and bytes.
    Useful for PushPlus limit verification.
    """
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        return

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            char_count = len(content)
            byte_count = len(content.encode('utf-8'))
            
        print(f"\n📊 File Analysis: {filepath}")
        print(f"{'-'*40}")
        print(f"📝 Characters: {char_count:,} chars")
        print(f"💾 Bytes:      {byte_count:,} bytes ({byte_count/1024:.2f} KB)")
        print(f"{'-'*40}")
        
        limit_chars = 19800
        if char_count > limit_chars:
            print(f"⚠️  WARNING: Exceeds 19,800 Chars limit by {char_count - limit_chars} chars!")
        else:
            print(f"✅ OK: Within 19,800 Char limit ({char_count/limit_chars*100:.1f}%)")
            
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_size.py <filepath>")
        # Default to damai if no arg provided
        default_file = "output/damai/latest.html"
        if os.path.exists(default_file):
            print(f"\nNo file specified, checking default: {default_file}")
            check_file_size(default_file)
    else:
        check_file_size(sys.argv[1])
