""""""
import io
import re

from blessed import Terminal
import multiprocessing_logging

from ved_capture.utils import beep
from ved_capture.cli.utils import (
    add_file_handler,
    init_logger,
    flush_log_buffer,
    raise_error,
)


def _format_log_buffer(t, log_buffer):
    """ Add pretty formatting to log messages. """
    log_buffer = log_buffer.replace("[ERROR]", t.bold(t.red2("[ERROR]")))
    log_buffer = log_buffer.replace(
        "[WARNING]", t.bold(t.goldenrod("[WARNING]"))
    )
    log_buffer = log_buffer.replace("[INFO]", t.bold(t.steelblue("[INFO]")))
    log_buffer = log_buffer.replace("[DEBUG]", t.bold("[DEBUG]"))

    return log_buffer


def refresh(t, log_buffer, status_buffer, timeout=0.1, num_empty_lines=1):
    """ Refresh terminal output and return user input. """
    if not hasattr(refresh, "last_log_line"):
        # last_log_line persists across calls and stores the line number of
        # the last line that was written from the log
        refresh.last_log_line = t.get_location()[0]

    # print log buffer
    if log_buffer is not None:
        log_buffer = _format_log_buffer(t, log_buffer)
        print(t.move_xy(0, refresh.last_log_line) + t.clear_eos + log_buffer)
    else:
        print(t.move_xy(0, refresh.last_log_line) + t.move_up)

    # print status buffer
    if status_buffer is not None:
        # compute the actual offset between cursor location and bottom of the
        # screen as well as the desired offset when printing the status buffer
        # and possibly empty lines between log and status
        num_status_lines = len(status_buffer.splitlines()) + 1
        refresh.last_log_line = t.get_location()[0]
        actual_offset = t.height - t.get_location()[0]
        desired_offset = num_status_lines + num_empty_lines

        # print empty lines if desired offset is smaller than actual offset
        if desired_offset > actual_offset:
            refresh.last_log_line -= desired_offset - actual_offset
            print("\n" * (desired_offset - 2))

        first_status_line = t.height - num_status_lines
        if not hasattr(refresh, "last_num_status_lines"):
            # last_num_status_lines persists across calls and stores number of
            # status lines from the previous call
            refresh.last_num_status_lines = num_status_lines

        status_line_diff = refresh.last_num_status_lines - num_status_lines
        refresh.last_num_status_lines = num_status_lines
        if status_line_diff > 0:
            print(
                t.move_y(first_status_line - status_line_diff)
                + t.clear_eos
                + "\n" * status_line_diff
                + status_buffer
            )
        else:
            print(t.move_y(first_status_line) + t.clear_eos + status_buffer)
    else:
        print(t.clear_eos + t.move_up)

    # wait for keypress
    with t.cbreak():
        key = t.inkey(timeout)
        if key.is_sequence:
            return key.name
        else:
            return key


class TerminalUI:
    """ Terminal user interface for sub-commands. """

    def __init__(self, command_name, verbosity=0, temp_file_handler=False):
        """ Constructor.

        Parameters
        ----------
        command_name : str
            Name of the CLI command (e.g. "record").

        verbosity : int, default 0
            CLI logging level (0: INFO, 1: DEBUG).

        temp_file_handler : bool, default False
            If True, create the log file in a temporary folder instead
            of the application config folder. This is useful e.g. for the
            "record" command where the logs are saved to the folder created
            by the StreamManager but some information is already logged before
            the StreamManager is initialized. The logs are automatically moved
            to the correct folder upon calling ``attach``.
        """
        self.command_name = command_name

        self.term = Terminal()
        self.f_stdout = io.StringIO()
        self.logger, self.file_handler = init_logger(
            self.command_name,
            verbosity=verbosity,
            stream=self.f_stdout,
            stream_format="[%(levelname)s] %(message)s",
            temp_file_handler=temp_file_handler,
            return_file_handler=True,
        )
        self.temp_file_handler = temp_file_handler

        self.manager = None
        self.statusmap = {}
        self.keymap = {}
        self.fixed_status = None

        self._disconnect_map = {}

    def __enter__(self):
        multiprocessing_logging.install_mp_handler()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        multiprocessing_logging.uninstall_mp_handler()
        if exc_type:
            self.logger.debug(exc_val, exc_info=True)
            refresh(self.term, flush_log_buffer(self.f_stdout), None)
            raise_error(
                self.term.red2(self.term.bold(str(exc_val))), self.logger
            )
        else:
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
        """ Add a key to the keymap.

        Parameters
        ----------
        key : str
            Key to be mapped, e.g. "s" or "KEY_PGUP".

        description : str
            Description that is shown in the CLI, e.g. "show video streams".

        fn : callable
            Method to be called when pressing the key. The first argument
            passed to this function is the TerminalUI instance (i.e. ``self``).
            Additional arguments can be passed via the `args` parameter of this
            function, e.g.: ``lambda ui: ui.manager.send_notification(...)``.

        args : tuple, optional
            Additional arguments to be passed to `fn`.

        msg : str, optional
            Optional info message to be logged when pressing the key.

        alt_key : str, optional
            Alternative key to be mapped, e.g. "h". This key will replace
            the original key when the original key is pressed and vice-versa.

        alt_description : str, optional
            Alternative description, e.g. "hide video streams". This
            description will replace the original description when the original
            key is pressed and vice-versa.

        alt_fn : callable, optional
            Alternative method which will replace the original method when the
            original key is pressed and vice-versa.

        alt_args : tuple, optional
            Alternative arguments which will replace the original arguments
            when the original key is pressed and vice-versa.

        alt_msg : str, optional
            Alternative log message which will replace the original log message
            when the original key is pressed and vice-versa.

        alt_default : bool, default False
            If True, `alt_key` etc. will be the default mapping instead of
            `key`.
        """

        def call_fn():
            fn(self, *args)
            if msg:
                self.logger.info(msg)
            if alt_fn:
                self._replace_key(
                    key, description, call_alt_fn, alt_key, alt_description
                )

        def call_alt_fn():
            alt_fn(self, *(alt_args or args))
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

        # move log file to manager folder if it was temporary
        if self.temp_file_handler:
            add_file_handler(
                self.command_name, manager.folder, replace=self.file_handler
            )
            self.temp_file_handler = False

        def stop_manager():
            self.logger.info("Stopping...")
            self.manager.stopped = True

        self.keymap["q"] = ("quit", stop_manager)

        # Check keymap
        for key, tup in self.keymap.items():
            if not isinstance(tup, tuple) or len(tup) != 2:
                raise ValueError(
                    f"Key '{key}': value must be a tuple "
                    f"(description, callable)"
                )
            if not callable(tup[1]):
                raise ValueError(f"Key '{key}': value[1] is not callable")

        self._disconnect_map = {name: None for name in self.manager.streams}

    def _wrap(self, line):
        """ Wrap long lines. """
        return "\n".join(self.term.wrap(line, subsequent_indent=" "))

    def _format_status(self, val, fmt):
        """ Format stream statuses. """
        status = self.manager.format_status(val, format=fmt)
        if status is not None:
            if val == "fps":
                # TODO hacky coloring of fps
                for name, stream in self.manager.streams.items():
                    if hasattr(stream.device, "fps"):
                        pattern = re.compile(
                            f"{name}: "
                            + re.sub(r"{.*:.*}", r"([0-9]*\.?[0-9]*)", fmt)
                        )
                        fps_search = re.search(pattern, status)
                        if fps_search:
                            fps = float(fps_search.group(1))
                            ratio = fps / stream.device.fps
                            if ratio >= 0.95:
                                color = self.term.green
                            elif ratio >= 0.8:
                                color = self.term.goldenrod
                            else:
                                color = self.term.red2
                            status = status.replace(
                                f"{name}: {fmt.format(fps)}",
                                f"{name}: {color(fmt.format(fps))}",
                            )

            status = self._wrap(
                self.term.bold(
                    status.replace("no data", self.term.red2("no data"))
                )
            )

        return status

    def _get_status_str(self):
        """ Get status and key mappings. """
        if self.fixed_status is None:
            # format stream statuses
            status_list = [
                self._format_status(val, fmt)
                for val, fmt in self.statusmap.items()
            ]
            status_str = "\n".join(s for s in status_list if s is not None)
        else:
            status_str = self._wrap(self.term.bold(self.fixed_status))

        # format keymap
        keymap_str = " - ".join(
            [
                f"[{self.term.bold(key)}] {name}"
                for key, (name, _) in self.keymap.items()
            ]
        )
        if len(keymap_str):
            status_str += "\n" + self._wrap(keymap_str)

        return status_str

    def _check_for_disconnect(self):
        """ Check if a stream has been disconnected. """
        for name, was_disconnected in self._disconnect_map.copy().items():
            try:
                is_disconnected = not self.manager.status[name]["running"]
            except KeyError:
                continue
            if was_disconnected is None and not is_disconnected:
                self.logger.debug("Initial connect registered by UI.")
                self._disconnect_map[name] = False
            elif was_disconnected is False and is_disconnected:
                self.logger.debug("Disconnect registered by UI.")
                self._disconnect_map[name] = True
                beep([440, 0, 0], seconds=0.2)
            elif was_disconnected and not is_disconnected:
                self.logger.debug("Reconnect registered by UI.")
                self._disconnect_map[name] = False
                beep([880, 0, 880, 0, 0, 0], seconds=0.05)

    def spin(self):
        """ Main loop. """
        if self.manager is None:
            raise ValueError(
                "You need to call 'attach' to attach this UI to a "
                "StreamManager first"
            )

        while not self.manager.stopped:
            self._check_for_disconnect()
            log_buffer = flush_log_buffer(self.f_stdout)
            status_str = self._get_status_str()

            # get keypresses from manager
            if self.manager.keypresses._getvalue():
                key = self.manager.keypresses.popleft()
                if key in self.keymap:
                    self.keymap[key][1]()

            # get keypresses from terminal
            with self.term.hidden_cursor():
                key = refresh(self.term, log_buffer, status_str)
                if key in self.keymap:
                    self.keymap[key][1]()
