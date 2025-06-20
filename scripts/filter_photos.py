import tomllib
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Literal, Optional, Tuple
import osxphotos
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from PIL import Image


class MacPhotosFilter:
    """
    Filter, display, and export photos and videos from macOS Photos
    by date, location, and media type, with config file support.
    """

    def __init__(
        self,
        start_date: datetime = datetime(1970, 1, 1),
        end_date: Optional[datetime] = None,
        target_location: Optional[Tuple[float, float]] = None,
        config_path: str = "config.toml",
        max_distance_km: Optional[float] = None,
    ):
        # Load config
        with open(config_path, "rb") as f:
            self.config = tomllib.load(f)
        defaults = self.config.get("defaults", {})
        self.home_address = defaults.get("home_address")
        self.max_distance_km = (
            float(max_distance_km)
            if max_distance_km is not None
            else float(defaults.get("max_distance_km", 2.0))
        )
        self.start_date = start_date
        self.end_date = (
            end_date if end_date is not None else datetime.now() - timedelta(days=1)
        )
        # Set target location
        if target_location:
            self.target_location = target_location
        elif defaults.get("target_latlon"):
            self.target_location = tuple(defaults["target_latlon"])
        elif self.home_address:
            coords = self.address_to_gps(self.home_address)
            if coords:
                self.target_location = coords
            else:
                raise ValueError("Could not geocode home_address")
        else:
            raise ValueError(
                "Must specify either target_location or home_address or target_latlon in config"
            )
        self.photosdb = osxphotos.PhotosDB()
        self.filtered_media: List[osxphotos.PhotoInfo] = []

    @staticmethod
    def address_to_gps(
        address: str, user_agent: str = "macphotosfilter"
    ) -> Optional[Tuple[float, float]]:
        geolocator = Nominatim(user_agent=user_agent)
        location = geolocator.geocode(address)
        if location:
            return (location.latitude, location.longitude)
        return None

    def set_date_range(
        self, start_date: datetime, end_date: Optional[datetime] = None
    ) -> None:
        self.start_date = start_date
        self.end_date = (
            end_date if end_date is not None else datetime.now() - timedelta(days=1)
        )

    def set_location_by_address(self, address: str) -> bool:
        coords = self.address_to_gps(address)
        if coords:
            self.target_location = coords
            return True
        return False

    def set_location_by_gps(self, lat: float, lon: float) -> None:
        self.target_location = (lat, lon)

    def set_distance_km(self, distance: float) -> None:
        self.max_distance_km = distance

    def filter_media(
        self, media_type: Literal["all", "photo", "video"] = "all"
    ) -> List[osxphotos.PhotoInfo]:
        media = [
            p
            for p in self.photosdb.photos()
            if self.start_date <= p.date <= self.end_date
            and (
                (media_type == "all")
                or (media_type == "photo" and p.isphoto)
                or (media_type == "video" and p.ismovie)
            )
        ]
        self.filtered_media = [
            m
            for m in media
            if m.location
            and geodesic(self.target_location, (m.location[0], m.location[1])).km
            <= self.max_distance_km
        ]
        return self.filtered_media

    def save_thumbnails(
        self,
        out_dir: str,
        thumb_size: Tuple[int, int] = (300, 300),
        max_media: int = 10,
    ) -> None:
        """
        Save thumbnails of filtered media to a directory.
        Args:
            out_dir (str): Directory to save thumbnails.
            thumb_size (Tuple[int, int]): Thumbnail size.
            max_media (int): Maximum number of thumbnails to save.
        """
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        count = 0
        for media in self.filtered_media:
            if count >= max_media:
                break
            try:
                img = Image.open(media.path)
                img.thumbnail(thumb_size)
                thumb_file = out_path / f"thumb_{count}_{media.filename}"
                img.save(thumb_file)
                count += 1
            except Exception as e:
                print(f"Error creating thumbnail for {media.filename}: {e}")

    def list_media_info(self) -> List[dict]:
        info_list = []
        for media in self.filtered_media:
            info = {
                "filename": media.filename,
                "date": media.date,
                "location": media.location,
                "path": media.path,
                "type": "photo" if media.isphoto else "video",
            }
            info_list.append(info)
        return info_list

    def save_filtered_media_paths(self, filepath: str) -> None:
        with open(filepath, "w") as f:
            for media in self.filtered_media:
                f.write(f"{media.path}\n")

    def export_filtered_media(
        self, export_dir: str, original: bool = True, edited: bool = False
    ) -> None:
        export_path = Path(export_dir)
        export_path.mkdir(parents=True, exist_ok=True)
        for media in self.filtered_media:
            media.export(str(export_path), original=original, edited=edited)

    def clear_filters(self) -> None:
        self.filtered_media = []


# Example main function
def main():
    target_latlon = (-33.848803, 151.153135)
    max_distance_km = 0.2
    export_dir = "/Users/mjboothaus/tmp/photos/seymour_st"
    thumb_dir = "/Users/mjboothaus/tmp/photos/seymour_st_thumbs"

    pf = MacPhotosFilter(
        target_location=target_latlon,
        max_distance_km=max_distance_km,
    )
    pf.filter_media(media_type="all")
    pf.export_filtered_media(export_dir)
    pf.save_thumbnails(thumb_dir)
    print(f"Exported {len(pf.filtered_media)} files to {export_dir}")
    print(f"Saved thumbnails to {thumb_dir}")


if __name__ == "__main__":
    main()
