"""Async utilities module.

Provides helpers for running blocking operations in executors to maintain
main thread responsiveness.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Global executor for blocking I/O operations (DB, Network)
# Use a reasonable max_workers (e.g., 20) to match potential concurrency
_io_executor = ThreadPoolExecutor(max_workers=32)


async def run_blocking(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking function in a separate thread.
    
    Args:
        func: The blocking function to run.
        *args: Positional arguments for func.
        **kwargs: Keyword arguments for func.
        
    Returns:
        The result of func.
    """
    loop = asyncio.get_running_loop()
    
    # partial to handle kwargs if necessary, though run_in_executor doesn't support them directly
    if kwargs:
        from functools import partial
        func = partial(func, **kwargs)
        
    return await loop.run_in_executor(_io_executor, func, *args)
