import pytest

from geoportal import db


@pytest.fixture(scope="session", autouse=True)
def fechar_pool():
    yield
    db.fechar()
