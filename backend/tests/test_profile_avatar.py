"""The profile picture is stored inline, so its size has to be bounded.

The browser scales a chosen picture to 320px and sends a data: URL, which
avoids a storage bucket and a public object entirely. What it does not avoid is
somebody posting straight to the API with a 12 megapixel photograph in the
field, so the column has a ceiling.
"""

from app.routers.profile import ProfileUpdate

import pytest
from pydantic import ValidationError


class TestAvatarSize:
    def test_a_scaled_picture_fits(self):
        # A 320px JPEG data URL is roughly 20KB; this is generous.
        update = ProfileUpdate(avatar_url="data:image/jpeg;base64," + "A" * 60_000)
        assert update.avatar_url is not None

    def test_a_full_size_photograph_is_refused(self):
        with pytest.raises(ValidationError):
            ProfileUpdate(avatar_url="data:image/jpeg;base64," + "A" * 400_000)

    def test_no_picture_is_fine(self):
        assert ProfileUpdate().avatar_url is None
