from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base, CleaningAction, DataFile, LlmCallLog, Workspace

EXPECTED_TABLES = {
    "workspaces",
    "data_files",
    "pii_mappings",
    "cleaning_actions",
    "chat_messages",
    "query_cache",
    "ml_runs",
    "reports",
    "llm_call_logs",
}


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Base en memoire, recreee pour chaque test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as open_session:
        yield open_session

    await engine.dispose()


async def test_schema_creates_every_table():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
    await engine.dispose()

    assert EXPECTED_TABLES <= tables


async def test_identifiers_are_opaque_and_generated(session: AsyncSession):
    workspace = Workspace(name="Analyse RH")
    session.add(workspace)
    await session.commit()

    assert len(workspace.id) == 36
    assert "-" in workspace.id
    assert workspace.created_at is not None


async def test_a_freshly_uploaded_file_has_no_profile_yet(session: AsyncSession):
    workspace = Workspace(name="Analyse RH")
    session.add(workspace)
    await session.flush()

    data_file = DataFile(
        workspace_id=workspace.id,
        name="collaborateurs.csv",
        format="csv",
        size_bytes=2048,
        path="storage/8f14e45f.csv",
    )
    session.add(data_file)
    await session.commit()

    stored = (await session.execute(select(DataFile))).scalar_one()
    assert stored.profile is None
    assert stored.quality_score is None
    assert stored.pii_status == "unknown"


async def test_a_cleaning_action_is_active_by_default(session: AsyncSession):
    """Le rejeu ne considere que les actions actives : le defaut doit etre `True`."""
    workspace = Workspace(name="Analyse RH")
    session.add(workspace)
    await session.flush()
    data_file = DataFile(
        workspace_id=workspace.id,
        name="x.csv",
        format="csv",
        size_bytes=1,
        path="storage/x.csv",
    )
    session.add(data_file)
    await session.flush()

    action = CleaningAction(
        file_id=data_file.id,
        order_index=0,
        action_type="impute_mean",
        column_name="salaire",
        params={"value": 42000.0},
    )
    session.add(action)
    await session.commit()

    stored = (await session.execute(select(CleaningAction))).scalar_one()
    assert stored.enabled is True
    # La valeur calculee doit survivre au rejeu, sinon l'etat n'est pas reproductible.
    assert stored.params == {"value": 42000.0}


async def test_carbon_estimate_stays_empty_until_factors_are_sourced(session: AsyncSession):
    call = LlmCallLog(
        agent="analyst",
        provider="anthropic",
        model="claude-sonnet-5",
        tokens_in=1200,
        tokens_out=300,
        cost_cents=0.81,
        duration_ms=940,
    )
    session.add(call)
    await session.commit()

    stored = (await session.execute(select(LlmCallLog))).scalar_one()
    assert stored.co2e_mg is None
    assert stored.cached_tokens == 0


@pytest.mark.parametrize("table", sorted(EXPECTED_TABLES))
def test_no_sqlite_specific_column_type(table: str):
    """La migration PostgreSQL ne doit couter qu'un changement d'URL."""
    columns = Base.metadata.tables[table].columns
    for column in columns:
        dialect_specific = type(column.type).__module__.startswith("sqlalchemy.dialects")
        assert not dialect_specific, f"{table}.{column.name} depend d'un dialecte"
