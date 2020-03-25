import pytest

from click.testing import CliRunner

from ved_capture.cli import update


class TestCli:
    def test_update(self):
        """"""
        runner = CliRunner()
        result = runner.invoke(update, "-l -v")

        assert result.exit_code == 0
