# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Run ``blender_ext`` commands on a thread, for platforms that can't start processes (iOS).

Desktop Blender runs each repository command as a child Python process and reads its messages
from a pipe. Here the same command runs in this process and its messages go through a queue,
so callers see the same message stream and can request an exit the same way.
"""

__all__ = (
    "command_output_from_json_0",
)

import json
import queue
import threading
import traceback

from collections.abc import (
    Generator,
    Sequence,
)
from typing import Any


# Matches `bl_extension_utils.IDLE_WAIT_ON_READ`.
IDLE_WAIT_ON_READ = 0.05

# Only meaningful for a child process whose parent may close the pipe.
# It also replaces `sys.unraisablehook`, which would affect all of Blender here.
_ARGS_PROCESS_ONLY = {"--force-exit-ok"}


def command_output_from_json_0(
        args: Sequence[str],
        use_idle: bool,
) -> Generator[list[tuple[str, Any]], bool, None]:
    from .cli import blender_ext

    messages: queue.SimpleQueue[tuple[str, Any]] = queue.SimpleQueue()
    request_exit = threading.Event()

    def msg_fn(ty: str, data: Any) -> bool:
        # Round trip through JSON so callers receive the same types as from a child process.
        ty, data = json.loads(json.dumps([ty, data]))
        messages.put((ty, data))
        return request_exit.is_set()

    def run() -> None:
        try:
            parser = blender_ext.argparse_create()
            namespace = parser.parse_args([arg for arg in args if arg not in _ARGS_PROCESS_ONLY])
            namespace.msg_fn = msg_fn
            namespace.func(namespace)
        except BaseException:
            # A child process would print this to the console and exit, report it instead.
            msg_fn("FATAL_ERROR", traceback.format_exc())

    thread = threading.Thread(target=run, name="blender_ext", daemon=True)
    thread.start()

    while True:
        # Check before reading, so messages sent just before the thread finished are still read.
        is_alive = thread.is_alive()
        json_messages = []
        if use_idle and is_alive:
            try:
                json_messages.append(messages.get(timeout=IDLE_WAIT_ON_READ))
            except queue.Empty:
                pass
        while True:
            try:
                json_messages.append(messages.get_nowait())
            except queue.Empty:
                break

        if not json_messages and not is_alive:
            break

        # Yield even when `json_messages` is empty, otherwise this generator can block.
        if (yield json_messages):
            request_exit.set()
