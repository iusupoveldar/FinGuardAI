from data_gen.etl.import_amlsim import FILES
from data_gen.etl.import_amlsim import source_checksum


def test_source_files_exist_and_checksum_is_stable() -> None:
    assert all(path.is_file() for path in FILES.values())
    first = source_checksum()
    second = source_checksum()
    assert first == second
    assert len(first) == 64
