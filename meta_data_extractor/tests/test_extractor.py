"""Tests for meta_data_extractor.extractor – reverse-geocoding helpers."""

from unittest.mock import MagicMock, patch

from meta_data_extractor.extractor import get_adress_from_osm


def _make_location(address: dict):
    """Return a mock geopy Location whose .raw contains *address*."""
    loc = MagicMock()
    loc.raw = {"address": address}
    return loc


# -- georeference:state -------------------------------------------------------


class TestStateExtraction:
    """Verify that georeference:state is only set when a valid value exists."""

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_iso3166_lvl4_is_used(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "de", "ISO3166-2-lvl4": "DE-BY", "state": "Bayern"}
        )
        data: dict = {}
        assert get_adress_from_osm(data, 48.13, 11.58) is True
        assert data["georeference:state"] == "DE-BY"

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_iso3166_lvl3_fallback(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "gb", "ISO3166-2-lvl3": "GB-ENG"}
        )
        data: dict = {}
        assert get_adress_from_osm(data, 51.5, -0.1) is True
        assert data["georeference:state"] == "GB-ENG"

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_city_state_omits_field(self, mock_nom_cls):
        """Singapore has no state subdivision — the field must be absent."""
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "sg", "country": "Singapore"}
        )
        data: dict = {}
        assert get_adress_from_osm(data, 1.35, 103.81) is True
        assert "georeference:state" not in data

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_free_text_state_used_as_last_resort(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "jp", "state": "Tokyo"}
        )
        data: dict = {}
        assert get_adress_from_osm(data, 35.68, 139.76) is True
        assert data["georeference:state"] == "Tokyo"


# -- optional fields are omitted when empty ------------------------------------


class TestOptionalFieldsOmitted:
    """Empty optional georeference fields must not appear in the dict."""

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_empty_region_omitted(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "sg"}
        )
        data: dict = {}
        get_adress_from_osm(data, 1.35, 103.81)
        assert "georeference:region" not in data

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_empty_city_omitted(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "sg"}
        )
        data: dict = {}
        get_adress_from_osm(data, 1.35, 103.81)
        assert "georeference:city" not in data

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_country_still_set_when_available(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location(
            {"country_code": "sg"}
        )
        data: dict = {}
        get_adress_from_osm(data, 1.35, 103.81)
        assert data["georeference:country"] == "SG"

    @patch("meta_data_extractor.extractor.Nominatim")
    def test_country_omitted_when_unknown(self, mock_nom_cls):
        mock_nom_cls.return_value.reverse.return_value = _make_location({})
        data: dict = {}
        get_adress_from_osm(data, 0.0, 0.0)
        assert "georeference:country" not in data
