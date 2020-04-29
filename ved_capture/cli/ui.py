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

    # check bottom offset
    num_status_lines = len(status_buffer.splitlines()) + 1
    refresh.first_log_line = t.get_location()[0]
    actual_offset = t.height - t.get_location()[0]
    desired_offset = num_status_lines + num_empty_lines

    # adjust if necessary
    if desired_offset > actual_offset:
        refresh.first_log_line -= desired_offset - actual_offset
        print("\n" * (desired_offset - 2))

    # print status buffer
    # TODO handle no status (=clear previous status)
    first_status_line = t.height - num_status_lines
    print(t.move_y(first_status_line) + t.clear_eos + status_buffer)

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

        while not self.manager.stopped:
            if self.manager.all_streams_running:
                log_buffer = flush_log_buffer(self.f_stdout)
                status_str = self._get_status_str()
                with self.term.hidden_cursor():
                    key = refresh(self.term, log_buffer, status_str)
                    if key in self.keymap:
                        self.keymap[key][1]()
            else:
                print_log_buffer(self.f_stdout)

        print_log_buffer(self.f_stdout)
        print(self.term.bold(self.term.firebrick("Stopped")))
