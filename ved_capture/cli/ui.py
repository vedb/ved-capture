""""""


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
        print(t.move_xy(0, refresh.first_log_line) + t.clear_eos + t.move_up)

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
    first_status_line = t.height - num_status_lines
    print(t.move_y(first_status_line) + status_buffer)

    # wait for keypress
    with t.cbreak():
        return t.inkey(timeout)
