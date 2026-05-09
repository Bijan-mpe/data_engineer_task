def test_core_imports():
    import src.core.config
    import src.core.constants
    import src.core.db
    import src.core.logging


def test_pipeline_imports():
    import src.pipeline.extractor
    import src.pipeline.validator
    import src.pipeline.pipeline


def test_models_imports():
    import src.models.orm
    import src.models.schemas
    import src.models.responses


def test_repository_imports():
    import src.repository.company_repository
    import src.repository.snapshot_repository
    import src.repository.upload_repository


def test_api_imports():
    import src.api.main
    import src.api.routers.v1.companies
    import src.api.routers.v1.snapshots
    import src.api.routers.v1.uploads
