from pan.config.settings import DatabaseSettings, Settings


def test_database_async_url():
    db = DatabaseSettings(host="myhost", port=5433, user="u", password="p", name="mydb")  # noqa: S106
    assert db.async_url == "postgresql+asyncpg://u:p@myhost:5433/mydb"


def test_database_psycopg_url():
    db = DatabaseSettings(host="myhost", port=5433, user="u", password="p", name="mydb")  # noqa: S106
    assert db.psycopg_url == "postgresql://u:p@myhost:5433/mydb"


def test_settings_loads(test_settings: Settings):
    assert test_settings.debug is True
    assert test_settings.discord.guild_id == 123456789
    assert test_settings.portainer.endpoint_id == 1
