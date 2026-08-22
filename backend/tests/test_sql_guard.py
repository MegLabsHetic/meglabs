"""Le garde-fou est la seule chose entre un modele de langage et les donnees.

On le teste donc sur ce qu'il doit laisser passer autant que sur ce qu'il doit
refuser : un garde-fou qui refuse tout protege parfaitement et ne sert a rien.
"""

import pytest

from app.core.sql_guard import GardeFouSql, SqlRefuse

TABLES = {"collaborateurs", "transactions"}


@pytest.fixture
def garde() -> GardeFouSql:
    return GardeFouSql()


# --- Ce qui doit passer ---------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM collaborateurs",
        "SELECT service, AVG(salaire_annuel) FROM collaborateurs GROUP BY service",
        "SELECT COUNT(*) FROM collaborateurs WHERE a_quitte = 1",
        # Une jointure entre deux fichiers de l'espace : c'est la question de demo.
        "SELECT c.service, SUM(t.montant) FROM transactions t "
        "JOIN collaborateurs c ON c.id_collaborateur = t.id_collaborateur "
        "GROUP BY c.service",
        # Une CTE nomme ses propres tables : elles ne doivent pas etre prises pour
        # des sources etrangeres.
        "WITH moyennes AS (SELECT service, AVG(salaire_annuel) AS m FROM collaborateurs "
        "GROUP BY service) SELECT * FROM moyennes ORDER BY m DESC",
        "SELECT * FROM collaborateurs UNION SELECT * FROM collaborateurs",
        "SELECT * FROM (SELECT service FROM collaborateurs) AS s",
    ],
)
def test_legitimate_reads_are_allowed(garde: GardeFouSql, sql: str) -> None:
    assert garde.verifier(sql, TABLES)


def test_the_returned_query_is_executable(garde: GardeFouSql) -> None:
    """Ce qui sort du garde-fou est du SQL, pas la chaine d'origine recopiee."""
    sortie = garde.verifier("select  service ,count(*) from collaborateurs group by 1", TABLES)
    assert sortie.upper().startswith("SELECT")
    assert "collaborateurs" in sortie


# --- Ce qui doit etre refuse ----------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM collaborateurs",
        "DROP TABLE collaborateurs",
        "UPDATE collaborateurs SET salaire_annuel = 0",
        "INSERT INTO collaborateurs VALUES (1)",
        "TRUNCATE TABLE collaborateurs",
        "CREATE TABLE fuite AS SELECT * FROM collaborateurs",
        "ALTER TABLE collaborateurs DROP COLUMN salaire_annuel",
    ],
)
def test_writes_are_refused(garde: GardeFouSql, sql: str) -> None:
    with pytest.raises(SqlRefuse):
        garde.verifier(sql, TABLES)


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA database_list",
        "ATTACH 'ailleurs.db'",
        "SET memory_limit = '1GB'",
        "INSTALL httpfs",
    ],
)
def test_engine_statements_are_refused(garde: GardeFouSql, sql: str) -> None:
    with pytest.raises(SqlRefuse):
        garde.verifier(sql, TABLES)


def test_a_write_hidden_in_a_cte_is_refused(garde: GardeFouSql) -> None:
    """DuckDB accepte le DML en CTE : la requete se presente alors comme un SELECT."""
    with pytest.raises(SqlRefuse):
        garde.verifier(
            "WITH parties AS (DELETE FROM collaborateurs RETURNING *) SELECT * FROM parties",
            TABLES,
        )


def test_two_statements_are_refused(garde: GardeFouSql) -> None:
    with pytest.raises(SqlRefuse):
        garde.verifier("SELECT 1; DROP TABLE collaborateurs", TABLES)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM read_parquet('/data/secret.parquet')",
        "SELECT * FROM glob('/**')",
        "SELECT * FROM read_csv_auto('/etc/shadow')",
    ],
)
def test_file_reads_are_refused(garde: GardeFouSql, sql: str) -> None:
    with pytest.raises(SqlRefuse):
        garde.verifier(sql, TABLES)


def test_a_table_outside_the_workspace_is_refused(garde: GardeFouSql) -> None:
    with pytest.raises(SqlRefuse) as refus:
        garde.verifier("SELECT * FROM salaires_direction", TABLES)
    assert "collaborateurs" in refus.value.alternative


def test_an_empty_query_is_refused(garde: GardeFouSql) -> None:
    with pytest.raises(SqlRefuse):
        garde.verifier("   ", TABLES)


def test_text_that_is_not_sql_is_refused(garde: GardeFouSql) -> None:
    with pytest.raises(SqlRefuse):
        garde.verifier("montre moi les salaires", TABLES)


# --- La forme du refus ----------------------------------------------------


def test_the_refusal_offers_an_alternative(garde: GardeFouSql) -> None:
    """C'est la demonstration de securite : le refus doit rester serviable."""
    with pytest.raises(SqlRefuse) as refus:
        garde.verifier("DELETE FROM collaborateurs", TABLES)

    assert "SELECT" in refus.value.raison
    assert refus.value.alternative
    assert refus.value.message.startswith(refus.value.raison)
    assert refus.value.code_http == 400
