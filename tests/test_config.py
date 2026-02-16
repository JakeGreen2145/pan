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
    assert "main" in test_settings.portainer.instances
    assert test_settings.portainer.instances["main"].endpoint_id == 1
    assert test_settings.truenas.base_url == "https://truenas.test/api/v2.0"
    assert test_settings.proxmox.node_name == "pve"
    assert test_settings.unifi.base_url == "https://unifi.test"
