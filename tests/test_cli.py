import pytest

from click.testing import CliRunner

from ved_capture.cli import update


class TestCli:
    @pytest.mark.skip("skip until we create a separate test env")
    def test_update(self):
        """"""
        runner = CliRunner()
        result = runner.invoke(update, "-l -v")

        assert result.exit_code == 0
