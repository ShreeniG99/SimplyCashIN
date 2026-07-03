import pytest
from sqlalchemy import select, func

from app.db.models import BuyerRow, CashEventRow
from app.db.repositories import OwnerRepo
from app.db.seed import seed


@pytest.mark.db
async def test_seed_loads_fixture(session):
    await seed(session)
    owner = await OwnerRepo(session).get("ramesh")
    assert owner.business == "Sri Vinayaga Motors"
    n_buyers = (await session.execute(select(func.count()).select_from(BuyerRow))).scalar_one()
    assert n_buyers == 5
    n_events = (await session.execute(select(func.count()).select_from(CashEventRow))).scalar_one()
    assert n_events >= 4
