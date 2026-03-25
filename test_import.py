#!/usr/bin/env python3
import sys
import traceback

print("Testing Feishu imports...")

try:
    print("1. Testing feishu module import...")
    import feishu
    print("✓ feishu module imported successfully")
    
    print("\n2. Testing FeishuClient import...")
    from feishu import FeishuClient
    print("✓ FeishuClient imported successfully")
    
    print("\n3. Testing domains imports...")
    from feishu.domains import (
        ImMixin,
        DocxMixin,
        BitableMixin,
        CalendarMixin,
        DriveMixin,
        TaskMixin,
        WikiMixin,
        TroubleshootMixin,
    )
    print("✓ All domain mixins imported successfully")
    
    print("\n✅ All imports successful!")
    sys.exit(0)
    
except Exception as e:
    print(f"\n❌ Import failed: {type(e).__name__}: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
