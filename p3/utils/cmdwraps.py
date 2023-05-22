import argparse
import shlex
from collections.abc import Callable
from functools import wraps
from typing import Any

CMD_FUNC_TYPE = Callable[[Any, str], None]
PARSED_FUNC_TYPE = Callable[[Any, argparse.Namespace], None]


def cmdwraps(
    additional_args: list[tuple[list[Any], dict[str, Any]]]
) -> Callable[[PARSED_FUNC_TYPE], CMD_FUNC_TYPE]:

    def wrapper(parsed_func: PARSED_FUNC_TYPE) -> CMD_FUNC_TYPE:

        @wraps(parsed_func)
        def cmd_func(self: Any, cmd_args: str):
            try:
                parser = argparse.ArgumentParser(
                    prog=parsed_func.__name__.removeprefix('do_'),
                    add_help=False,
                    exit_on_error=False,
                )
                parser.add_argument('-h', '--help', action='store_true')
                for args, kwargs in additional_args:
                    parser.add_argument(*args, **kwargs)
                parsed_args = parser.parse_args(shlex.split(cmd_args))
                if parsed_args.help:
                    parser.print_help()
                else:
                    parsed_func(self, parsed_args)
            except Exception as e:
                print('except:', e)

        return cmd_func

    return wrapper
