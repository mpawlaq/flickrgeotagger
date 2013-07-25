from django.utils.decorators import method_decorator
from django.views.generic import RedirectView
from django.conf import settings

from flickrgeotagger.flickr.decorators import require_flickr_auth

import flickrapi


class FlickrAuthRequiredMixin(object):

    @method_decorator(require_flickr_auth)
    def dispatch(self, request, *args, **kwargs):
        return (super(FlickrAuthRequiredMixin, self)
                .dispatch(request, *args, **kwargs))


class CallbackView(RedirectView):

    def get(self, request, *args, **kwargs):
        flickr_api = flickrapi.FlickrAPI(
            settings.FLICKR_API_KEY,
            settings.FLICKR_API_SECRET,
            store_token=False)

        request.session['token'] = (flickr_api
                                    .get_token(request.GET.get('frob')))

        return super(CallbackView, self).get(request, *args, **kwargs)
