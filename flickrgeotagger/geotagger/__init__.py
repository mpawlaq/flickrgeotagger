from datetime import datetime
from django.conf import settings
import gpxpy
import gpxpy.gpx
from pytz import timezone

from .utils import cache, CACHE_ATTRIBUTES_LIST


class Backend(object):

    def get_start_time(self):
        raise NotImplementedError()

    def get_end_time(self):
        raise NotImplementedError()

    def get_points(self):
        raise NotImplementedError()

    def get_location_at(self, time):
        raise NotImplementedError()


class BackendException(Exception):
    pass


class GpxBackend(Backend):

    def __init__(self, data):
        self.gpx_file = data
        try:
            self.gpx = gpxpy.parse(data)
        except gpxpy.gpx.GPXXMLSyntaxException:
            raise BackendException()
        self.start_time, self.end_time = self.gpx.get_time_bounds()

    def get_points(self):
        points = []
        for track in self.gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    points.append({"latitude": point.latitude,
                                   "longitude": point.longitude})
        return points

    def get_location_at(self, time):
        gpx_locations = self.gpx.get_location_at(time)
        if gpx_locations:
            return gpx_locations.pop()


class GeoTagger(object):

    utc = timezone('UTC')

    def __init__(self, api, coordinates, user_timezone=None):
        self.api = api
        self.coordinates = coordinates
        self.timezone = timezone(user_timezone or settings.TIME_ZONE)

    def __repr__(self):
        return (u"GeoTagger (api=%s, coordinates=%s)" %
                (self.api, self.coordinates))

    def get_time_from_string(self, time_as_string,
                             date_format="%Y-%m-%d %H:%M:%S"):
        return datetime.strptime(time_as_string, date_format)

    def _utc_to_user_timezone(self, time, user_timezone):
        return self.utc.localize(time).astimezone(user_timezone)

    def _user_timezone_to_utc(self, time, user_timezone):
        return user_timezone.localize(time).astimezone(self.utc)

    def clear_cache(self):
        cache_attributes = getattr(self, CACHE_ATTRIBUTES_LIST, [])
        for attribute in cache_attributes:
            if hasattr(self, attribute):
                delattr(self, attribute)

    def set_timezone(self, timezone):
        self.clear_cache()
        self.timezone = timezone

    @cache('_get_localized_photos')
    def get_localized_photos(self):
        localized_photos = []

        start_time = self._utc_to_user_timezone(self.coordinates.start_time,
                                                self.timezone)
        end_time = self._utc_to_user_timezone(self.coordinates.end_time,
                                              self.timezone)
        photos = (self.api
                  .get('flickr.photos.search',
                       params={
                           'user_id': 'me',
                           'min_taken_date': start_time,
                           'max_taken_date': end_time,
                           'per_page': 500,
                           'extras': "geo,url_t,url_s,date_taken,path_alias"})
                  .get('photos'))

        for photo in photos.get('photo'):
            taken = self.get_time_from_string(photo.get('datetaken'))
            taken = (self._user_timezone_to_utc(taken, self.timezone)
                     .replace(tzinfo=None))
            location = self.coordinates.get_location_at(taken)
            if location:
                flickr_url = ("http://flickr.com/photos/%s/%s" %
                              (photo.get('pathalias'), photo.get('id')))
                localized_photos.append({
                    'id': photo.get('id'),
                    'title': photo.get('title'),
                    'taken': taken,
                    'url': photo.get('url_s'),
                    'flickr_url': flickr_url,
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'has_geo': all([photo.get('latitude'),
                                    photo.get('longitude')])
                })

        return localized_photos

    @property
    @cache('_number_of_geotagged_photos')
    def number_of_geotagged_photos(self):
        return len(filter(lambda x: x['has_geo'], self.get_localized_photos()))

    @property
    @cache('_number_of_not_geotagged_photos')
    def number_of_not_geotagged_photos(self):
        return (len(self.get_localized_photos())
                - self.number_of_geotagged_photos)
        
    def save_location(self, photos=None, override_geo=False):

        if photos is None:
            photos = self.get_localized_photos()

        for photo in photos:
            if not override_geo and photo['has_geo']:
                continue
            self.api.get('flickr.photos.geo.setLocation', params={
                'photo_id': photo['id'],
                'lat': photo['latitude'],
                'lon': photo['longitude']})
