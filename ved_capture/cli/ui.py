""""""
import io

from blessed import Terminal
import multiprocessing_logging

from ved_capture.cli.utils import (
    init_logger,
    flush_log_buffer,
    print_log_buffer,
)


def refresh(t, stream_buffer, status_buffer, timeout=0.1, num_empty_lines=1):
    """ Refresh terminal output and return user input. """
    if not hasattr(refresh, "first_log_line"):
        refresh.first_log_line = t.get_location()[0]

    # print stream buffer
    if stream_buffer is not None:
        print(
            t.move_xy(0, refresh.first_log_line) + t.clear_eos + stream_buffer
        )
    else:
        print(t.move_xy(0, refresh.first_log_line) + t.move_up)

    # print status buffer
    if status_buffer is not None:
        num_status_lines = len(status_buffer.splitlines()) + 1
        refresh.first_log_line = t.get_location()[0]
        actual_offset = t.height - t.get_location()[0]
        desired_offset = num_status_lines + num_empty_lines

        if desired_offset > actual_offset:
            refresh.first_log_line -= desired_offset - actual_offset
            print("\n" * (desired_offset - 2))

        first_status_line = t.height - num_status_lines
        print(t.move_y(first_status_line) + t.clear_eos + status_buffer)
    else:
        print(t.clear_eos + t.move_up)

    # wait for keypress
    with t.cbreak():
        return t.inkey(timeout)


class TerminalUI:
    """ Terminal user interface for sub-commands. """

    def __init__(self, command_name, verbosity=0):
        """ Constructor. """
        self.command_name = command_name

        self.term = Terminal()
        self.f_stdout = io.StringIO()
        self.logger = init_logger(
            self.command_name,
            verbosity=verbosity,
            stream=self.f_stdout,
            stream_format="[%(levelname)s] %(message)s",
        )

        multiprocessing_logging.install_mp_handler()

        self.manager = None
        self.statusmap = {}
        self.keymap = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        refresh(self.term, flush_log_buffer(self.f_stdout), None)
        print(self.term.bold(self.term.firebrick("Stopped")))

    def _replace_key(self, key, desc, call_fn, new_key=None, new_desc=None):
        """ Replace a key in the keymap while maintaining its order. """
        self.keymap = {
            (new_key or key if k == key else k): (
                (new_desc or desc, call_fn) if k == key else v
            )
            for k, v in self.keymap.items()
        }

    def add_key(
        self,
        key,
        description,
        fn,
        args=tuple(),
        msg=None,
        alt_key=None,
        alt_description=None,
        alt_fn=None,
        alt_args=None,
        alt_msg=None,
        alt_default=False,
    ):
        """ Add a key to the keymap. """

        def call_fn():
            fn(self.manager, *args)
            if msg:
                self.logger.info(msg)
            if alt_fn:
                self._replace_key(
                    key, description, call_alt_fn, alt_key, alt_description
                )

        def call_alt_fn():
            alt_fn(self.manager, *(alt_args or args))
            if alt_msg or msg:
                self.logger.info(alt_msg or msg)
            self._replace_key(
                alt_key or key,
                alt_description or description,
                call_fn,
                key,
                description,
            )

        if alt_default:
            self.keymap[alt_key] = (
                alt_description or description,
                call_alt_fn,
            )
        else:
            self.keymap[key] = (description, call_fn)

    @classmethod
    def nop(cls):
        """ Placeholder method for keys that don't get handled via keymap. """

    def attach(self, manager, statusmap=None, keymap=None):
        """ Attach to a StreamManager. """
        self.manager = manager
        self.statusmap = statusmap or {}
        self.keymap = keymap or {}

        # Check keymap
        for key, tup in self.keymap.items():
            if not isinstance(tup, tuple) or len(tup) != 2:
                raise ValueError(
                    f"Key '{key}': value must be a tuple "
                    f"(description, callable)"
                )
            if not callable(tup[1]):
                raise ValueError(f"Key '{key}': value[1] is not callable")

    def _get_status_str(self):
        """ Get status and key mappings. """
        status_str = "\n".join(
            [
                self.term.bold(
                    self.manager.format_status(
                        val, format=fmt, max_cols=self.term.width
                    )
                )
                for val, fmt in self.statusmap.items()
            ]
        )

        key_str = " - ".join(
            [
                f"[{self.term.bold(key)}] {name}"
                for key, (name, _) in self.keymap.items()
            ]
            + [f"[{self.term.bold('ctrl+c')}] quit"]
        )
        if len(key_str):
            status_str += "\n" + key_str

        return status_str

    def spin(self):
        """ Main loop. """
        if self.manager is None:
            raise ValueError(
                "You need to call 'attach' to attach this UI to a "
                "StreamManager first"
            )

        while not self.manager.all_streams_running:
            # TODO not calling refresh here because C-level stdout writes
            #  are not handled
            print_log_buffer(self.f_stdout)

        while not self.manager.stopped:
            log_buffer = flush_log_buffer(self.f_stdout)
            status_str = self._get_status_str()
            with self.term.hidden_cursor():
                key = refresh(self.term, log_buffer, status_str)
                if key in self.keymap:
                    self.keymap[key][1]()
