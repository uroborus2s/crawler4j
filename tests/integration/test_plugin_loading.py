import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.core.plugins.loader import PluginLoader


async def test_module_loading():
    print("Testing PluginLoader...")
    loader = PluginLoader()
    loader.load_modules()
    
    ctrip = loader.get_module("ctrip")
    if ctrip:
        print(f"✅ Successfully loaded module: {ctrip.display_name}")
        print("Default Config Preview:")
        print(ctrip.get_default_config())
    else:
        print("❌ Failed to load 'ctrip' module.")

if __name__ == "__main__":
    asyncio.run(test_module_loading())
