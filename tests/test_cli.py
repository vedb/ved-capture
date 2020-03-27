import pytest

from click.testing import CliRunner

from ved_capture.cli import record, update


class TestCli:
    @pytest.mark.skip("skip until we figure out how to run this during CI")
    def test_record(self, config_dir):
        """"""
        runner = CliRunner()
        result = runner.invoke(
            record, f"-v -c {config_dir}/nometa_config.yaml"
        )

        assert result.exit_code == 0

    @pytest.mark.skip("skip until we figure out how to run this during CI")
    def test_update_cli(self):
        """"""
        runner = CliRunner()
        result = runner.invoke(update, "-l -v")

        assert result.exit_code == 0
