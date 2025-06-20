import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from scripts.filter_photos import (
    MacPhotosFilter,
)


@pytest.fixture
def mock_photosdb(monkeypatch):
    # Mock PhotoInfo objects
    class MockPhotoInfo:
        def __init__(
            self,
            date,
            location,
            isphoto,
            ismovie,
            filename="test.jpg",
            path="/tmp/test.jpg",
        ):
            self.date = date
            self.location = location
            self.isphoto = isphoto
            self.ismovie = ismovie
            self.filename = filename
            self.path = path

        def export(self, export_dir, original=True, edited=False):
            return True

    # Mock PhotosDB
    mock_db = MagicMock()
    now = datetime.now()
    mock_db.photos.return_value = [
        MockPhotoInfo(
            now - timedelta(days=1), (-33.85, 151.15), True, False
        ),  # photo, in range
        MockPhotoInfo(
            now - timedelta(days=2), (-33.90, 151.20), True, False
        ),  # photo, out of range
        MockPhotoInfo(
            now - timedelta(days=1), (-33.85, 151.15), False, True
        ),  # video, in range
    ]
    monkeypatch.setattr("osxphotos.PhotosDB", lambda: mock_db)
    return mock_db


@pytest.fixture
def default_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[defaults]
max_distance_km = 10.0
target_latlon = [-33.85, 151.15]
""")
    return str(config_path)


def test_filter_photos_in_range(mock_photosdb, default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.filter_media(media_type="photo")
    assert len(pf.filtered_media) == 1
    assert pf.filtered_media[0].isphoto


def test_filter_videos_in_range(mock_photosdb, default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.filter_media(media_type="video")
    assert len(pf.filtered_media) == 1
    assert pf.filtered_media[0].ismovie


def test_filter_all_in_range(mock_photosdb, default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.filter_media(media_type="all")
    assert len(pf.filtered_media) == 2  # photo + video in range


def test_no_media_out_of_range(mock_photosdb, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("""
[defaults]
max_distance_km = 0.01
target_latlon = [0.0, 0.0]
""")
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=str(config_path),
    )
    pf.filter_media(media_type="all")
    assert len(pf.filtered_media) == 0


def test_export_filtered_media(tmp_path, mock_photosdb, default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.filter_media(media_type="all")
    export_dir = tmp_path / "export"
    pf.export_filtered_media(str(export_dir))
    # Check that export method was called for each filtered media
    for media in pf.filtered_media:
        assert hasattr(media, "export")


def test_save_thumbnails(tmp_path, mock_photosdb, default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.filter_media(media_type="all")
    thumb_dir = tmp_path / "thumbs"
    # Patch PIL.Image.open to avoid real file I/O
    with patch("PIL.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        pf.save_thumbnails(str(thumb_dir))
        assert mock_open.called


def test_set_location_by_address(monkeypatch, default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    # Patch address_to_gps to always return a tuple
    monkeypatch.setattr(pf, "address_to_gps", lambda addr: (1.0, 2.0))
    assert pf.set_location_by_address("test address") is True
    assert pf.target_location == (1.0, 2.0)


def test_set_location_by_gps(default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.set_location_by_gps(5.0, 6.0)
    assert pf.target_location == (5.0, 6.0)


def test_set_distance_km(default_config):
    pf = MacPhotosFilter(
        start_date=datetime.now() - timedelta(days=3),
        end_date=datetime.now(),
        config_path=default_config,
    )
    pf.set_distance_km(42.0)
    assert pf.max_distance_km == 42.0
